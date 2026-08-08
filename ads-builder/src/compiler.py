"""brief + blueprint -> Plan.

The only place that knows how a client's answers turn into account structure.
Deliberately boring: no network, no state, no side effects. Same inputs always
produce the same plan, which is what makes diffing a rebuild against a live
account meaningful.
"""

import re
from pathlib import Path
from typing import Any

import yaml

from .model import (
    MAX_DESCRIPTION,
    MAX_HEADLINE,
    RSA_MAX_DESCRIPTIONS,
    RSA_MAX_HEADLINES,
    RSA_MIN_HEADLINES,
    AdGroup,
    Asset,
    display_length,
    Campaign,
    Keyword,
    NegativeKeyword,
    Plan,
    ResponsiveSearchAd,
    ScheduleSlot,
)

TRADE_CODES = {"moving": "MOV", "cleaning": "CLN", "restoration": "RST", "local": "LOC"}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


class BriefError(Exception):
    """The brief is missing something the build cannot invent."""


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open() as handle:
        return yaml.safe_load(handle)


def require(data: dict, path: str) -> Any:
    """Fetch a dotted key or fail loudly. Silence here becomes waste later."""
    node: Any = data
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node or node[part] is None:
            raise BriefError(f"brief is missing required field `{path}`")
        node = node[part]
    return node


# Google's own ad-customiser and ValueTrack tokens. These look exactly like our
# placeholders and must reach the ad untouched — `{KeyWord:Moving Papa}` is what
# makes dynamic keyword insertion work, and substituting it would break the ad.
VALUETRACK = {
    "keyword", "campaignid", "adgroupid", "creative", "lpurl", "escapedlpurl",
    "unescapedlpurl", "targetid", "matchtype", "network", "device", "devicemodel",
    "adposition", "placement", "random", "loc_physical_ms", "loc_interest_ms",
    "feeditemid", "extensionid", "merchant_id", "product_id", "ifmobile",
    "ifsearch", "ifcontent", "ignore",
}
_FIELD = re.compile(r"\{(\w+)\}")


def render(template: str, context: dict[str, str]) -> str:
    """Fill our {placeholders}, leaving Google's alone.

    Anything with a colon or parenthesis — `{KeyWord:Fallback}`,
    `{LOCATION(City):Your Area}` — is not matched at all, so it passes through
    verbatim. A bare `{word}` we do not recognise is a blueprint bug and raises.
    """
    def substitute(match: re.Match) -> str:
        key = match.group(1)
        if key in context:
            return str(context[key])
        if key.lower() in VALUETRACK or key.startswith("_"):
            return match.group(0)
        raise BriefError(f"unknown placeholder {{{key}}} in template {template!r}")

    return tidy(_FIELD.sub(substitute, template or ""))


def tidy(text: str) -> str:
    """Clean up after a placeholder rendered empty.

    "Flat pricing. {min_job_value}. Nothing added." with a blank minimum job
    leaves "Flat pricing. . Nothing added." — punctuation that belonged to the
    missing value. Without this it goes live in the ad exactly like that.
    """
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)          # space before punctuation
    text = re.sub(r"([.,!?;:])(?:\s*\1)+", r"\1", text)   # ". ." -> "."
    return text.strip(" ,;:")


def compile_plan(brief_path: Path, blueprint_dir: Path) -> Plan:
    """Compile from a brief on disk. Thin wrapper — the UI calls compile_brief
    directly with a dict, so both paths run identical logic."""
    return compile_brief(load_yaml(brief_path), blueprint_dir)


def available_trades(blueprint_dir: Path) -> list[str]:
    return sorted(p.stem for p in blueprint_dir.glob("*.yaml"))


def compile_brief(brief: dict[str, Any], blueprint_dir: Path) -> Plan:
    trade = require(brief, "trade")
    if not (blueprint_dir / f"{trade}.yaml").exists():
        raise BriefError(
            f"no blueprint for trade {trade!r} — have: {', '.join(available_trades(blueprint_dir))}"
        )
    blueprint = load_yaml(blueprint_dir / f"{trade}.yaml")

    defaults = blueprint.get("defaults", {})
    themes: dict[str, list[str]] = blueprint.get("themes", {})

    business = require(brief, "client.business_name")
    currency = require(brief, "client.currency")
    monthly_budget = float(require(brief, "budget.monthly_total"))
    cities: list[str] = require(brief, "service_area.cities")
    geo_targets: list[str] = require(brief, "service_area.targets")
    enabled: list[str] = require(brief, "services")

    plan = Plan(
        client_slug=require(brief, "client.slug"),
        business_name=business,
        trade=trade,
        blueprint_version=str(blueprint.get("version", "0")),
        currency=currency,
        monthly_budget=monthly_budget,
    )

    base_context = {
        "business": business,
        "phone": require(brief, "client.phone"),
        "offer": brief.get("positioning", {}).get("offer", ""),
        "min_job_value": brief.get("positioning", {}).get("min_job_value", ""),
        "city": cities[0],
        "term": "",
    }

    specs = [c for c in blueprint["campaigns"] if c["key"] in enabled]
    if not specs:
        raise BriefError(f"none of the requested services {enabled} exist in the {trade} blueprint")

    unknown = set(enabled) - {c["key"] for c in blueprint["campaigns"]}
    if unknown:
        plan.warn(f"brief requests services with no blueprint campaign: {sorted(unknown)}")

    if not brief.get("tracking", {}).get("call_tracking_number"):
        plan.warn("the call asset is using the public phone number — calls from ads "
                  "will not be attributable until a tracking number is set")

    account_negatives = _account_negatives(blueprint, blueprint_dir)
    schedules = blueprint.get("schedules", {})

    # The account this is modelled on builds a campaign set per market, named
    # `{market} | Search | {theme}`. A brief with no explicit markets is treated
    # as one market covering every city, which is the single-city case.
    markets = brief.get("markets") or [{"name": cities[0], "cities": cities}]
    fmt = defaults.get("campaign_name_format", "{code} | Search | {label} | EN")

    # Budget is allocated market first, then split inside each market across the
    # themes that market actually runs. Doing it the other way round leaves a
    # market's money unspent whenever it skips a theme.
    def theme_weight(spec) -> float:
        """A theme's share of the whole account, not of one market.

        `typical_daily_budget` is what ONE market spent on that theme, so a theme
        running in eight markets carries eight times the weight of one that runs
        once. Comparing the per-market figures directly hands an account-wide
        campaign like Brand a market's entire share — it took 17% here, where the
        source account gives it under 2%.
        """
        if spec.get("budget_weight"):
            return float(spec["budget_weight"])
        base = float(spec.get("typical_daily_budget") or 1)
        return base * max(1, len(spec.get("markets_seen") or []))

    days = float(blueprint.get("budget", {}).get("days_per_month", 30.4))
    min_daily = float(blueprint.get("budget", {}).get("min_daily", 0))

    global_specs = [s for s in specs if s.get("all_markets")]
    market_specs = [s for s in specs if not s.get("all_markets")]

    # Account-wide campaigns take their share off the top; the markets divide
    # what is left.
    total_weight = sum(theme_weight(s) for s in specs) or 1
    global_fraction = sum(theme_weight(s) for s in global_specs) / total_weight
    account_daily = monthly_budget / days

    stated = {}
    for market in markets:
        name = market["name"] if isinstance(market, dict) else str(market)
        stated[name] = float(market.get("monthly_budget") or 0) if isinstance(market, dict) else 0.0

    if sum(stated.values()) and abs(sum(stated.values()) - monthly_budget) > 1:
        plan.warn(f"per-market budgets total {sum(stated.values()):,.0f} but "
                  f"budget.monthly_total says {monthly_budget:,.0f} — using the "
                  f"per-market figures")

    def allocate(daily: float, chosen: list) -> dict:
        weights = {s["key"]: theme_weight(s) for s in chosen}
        total = sum(weights.values()) or 1
        out = {}
        for key, weight in weights.items():
            amount = round(daily * weight / total, 2)
            if min_daily and amount < min_daily:
                plan.warn(f"{key}: raised to the {min_daily:.0f}/day floor")
                amount = min_daily
            out[key] = amount
        return out

    for market in markets:
        market_name = market["name"] if isinstance(market, dict) else str(market)
        market_cities = (market.get("cities") if isinstance(market, dict) else None) or cities
        market_geo = (market.get("targets") if isinstance(market, dict) else None) or geo_targets
        skip = set((market.get("skip_campaigns") if isinstance(market, dict) else None) or [])

        chosen = [s for s in market_specs if s["key"] not in skip]
        if not chosen:
            continue

        if stated.get(market_name):
            market_daily = (stated[market_name] / days) * (1 - global_fraction)
        else:
            market_daily = (account_daily * (1 - global_fraction)) / len(markets)

        allocations = allocate(market_daily, chosen)
        for spec in chosen:
            plan.campaigns.append(_build_campaign(
                spec=spec, plan=plan, brief=brief, blueprint=blueprint, themes=themes,
                defaults=defaults, schedules=schedules, trade=trade, fmt=fmt,
                market_name=market_name, market_cities=market_cities,
                geo_targets=market_geo, base_context=base_context,
                daily_budget=allocations[spec["key"]],
                account_negatives=account_negatives,
                market_tcpa=(market.get("target_cpa") if isinstance(market, dict) else None),
            ))

    if global_specs:
        allocations = allocate(account_daily * global_fraction, global_specs)
        for spec in global_specs:
            plan.campaigns.append(_build_campaign(
                spec=spec, plan=plan, brief=brief, blueprint=blueprint, themes=themes,
                defaults=defaults, schedules=schedules, trade=trade, fmt=fmt,
                market_name="All Markets", market_cities=cities,
                geo_targets=geo_targets, base_context=base_context,
                daily_budget=allocations[spec["key"]],
                account_negatives=account_negatives,
            ))

    _dedupe_keywords(plan)
    return plan


def _dedupe_keywords(plan) -> None:
    """One keyword, one ad group.

    The source account carries the same term in more than one place — "movers
    toronto" sits in both the core and GEO ad groups, and a Last Mile Delivery
    ad group exists under two campaigns. Copying that faithfully means the
    account bids against itself and splits one query's data in two.

    The owner is the ad group whose campaign theme its own name matches: a
    "Last Mile Delivery" group belongs to Last-mile, not to Commercial &
    Office. Where nothing matches, the first occurrence keeps it.
    """
    def affinity(group_name: str, campaign_name: str) -> int:
        words = set(re.findall(r"[a-z]+", group_name.lower()))
        theme = set(re.findall(r"[a-z]+", campaign_name.lower()))
        return len(words & theme)

    # Scoped to a market. Toronto and Vancouver can both bid on "local movers"
    # without competing, because presence-based geo targeting separates them —
    # deduping across markets would strip every city but the first.
    placements: dict[tuple[str, str], list[tuple]] = {}
    for campaign in plan.campaigns:
        for group in campaign.ad_groups:
            for keyword in group.keywords:
                placements.setdefault((campaign.market, keyword.text.lower()),
                                      []).append((campaign, group, keyword))

    moved = 0
    for (market, text), spots in placements.items():
        if len(spots) < 2:
            continue
        # Affinity first; then the more specific campaign, measured by how many
        # segments its name carries. "General Moving | GEOs" is narrower than
        # "General Moving", and a city term belongs in the narrower one — the
        # GEO campaigns are the highest converting type in the source account,
        # and first-wins would have emptied them completely.
        best = max(spots, key=lambda s: (affinity(s[1].name, s[0].name),
                                         s[0].name.count("|")))
        for campaign, group, keyword in spots:
            if (campaign, group) != (best[0], best[1]):
                group.keywords = [k for k in group.keywords if k is not keyword]
                moved += 1
        plan.warn(f'"{text}" kept in {best[0].name} › {best[1].name}, '
                  f"removed from {len(spots) - 1} other ad group(s) in {market}")

    # An ad group whose every keyword belonged somewhere else has nothing left
    # to do, and an empty ad group cannot serve.
    emptied = 0
    for campaign in plan.campaigns:
        keep = [g for g in campaign.ad_groups if g.keywords]
        emptied += len(campaign.ad_groups) - len(keep)
        campaign.ad_groups = keep

    if moved:
        plan.warn(f"{moved} duplicate keyword placement(s) removed so the account "
                  f"does not bid against itself"
                  + (f", leaving {emptied} empty ad group(s) which were dropped"
                     if emptied else ""))


def _build_campaign(*, spec, plan, brief, blueprint, themes, defaults, schedules, trade,
                    fmt, market_name, market_cities, geo_targets, base_context,
                    daily_budget, account_negatives, market_tcpa=None):
        campaign = Campaign(
            key=spec["key"],
            name=spec.get("fixed_name") or _campaign_name(
                trade, spec["label"], spec.get("name_format") or fmt, market_name),
            market=market_name,
            campaign_type=spec.get("campaign_type", defaults.get("campaign_type", "Search")),
            daily_budget=daily_budget,
            bid_strategy=spec.get("bid_strategy", defaults.get("bid_strategy")),
            max_cpc=spec.get("max_cpc"),
            status=defaults.get("status", "Paused"),
            networks=defaults.get("networks", "Google search"),
            language=defaults.get("language", "en"),
            locations=list(geo_targets),
            excluded_locations=list(brief.get("service_area", {}).get("exclude") or []),
            location_target_type=defaults.get("location_target_type", "Location of presence"),
            location_exclusion_type=defaults.get("location_exclusion_type", "Location of presence"),
            # A market can tier its own target CPA — the live account runs
            # Calgary at 67, Edmonton at 75, everywhere else 70. A campaign on a
            # clicks strategy carries no target at all.
            target_cpa=(None if "click" in str(spec.get("bid_strategy", "")).lower()
                        else market_tcpa or spec.get("target_cpa")),
            tracking_template=defaults.get("tracking_template", ""),
            ad_rotation=defaults.get("ad_rotation", "Optimize for clicks"),
            # No explicit schedule means answering hours, not always-on. Calls
            # only convert when someone picks up.
            schedule=_build_schedule(spec.get("schedule") or "business_hours",
                                     schedules, brief),
            asset_group=spec.get("asset_group"),
            negatives=list(account_negatives)
            + _theme_negatives(spec.get("negative_themes", []), themes)
            + _literal_negatives(spec.get("negative_keywords", []), base_context),
            assets=_build_assets(blueprint, brief),
            audience_segments=list(blueprint.get("assets", {}).get("audience_segments", [])),
        )

        if campaign.asset_group:
            ag = campaign.asset_group
            campaign.asset_group = {
                "name": ag.get("name", "Asset Group 1"),
                "headlines": [render(h, base_context) for h in ag.get("headlines", [])],
                "long_headlines": [render(h, base_context) for h in ag.get("long_headlines", [])],
                "descriptions": [render(d, base_context) for d in ag.get("descriptions", [])],
                "final_url": _final_url(brief, spec["key"]),
                "audience_signal": ag.get("audience_signal", ""),
            }

        final_url = _final_url(brief, spec["key"])
        default_matches = defaults.get("match_types", ["phrase", "exact"])

        for group_spec in spec.get("ad_groups", []):
            targets = market_cities if group_spec.get("per_city") else [market_cities[0]]
            for index, city in enumerate(targets):
                context = dict(base_context, city=city)
                group = _build_ad_group(
                    plan=plan,
                    group_spec=group_spec,
                    brief=brief,
                    themes=themes,
                    context=context,
                    city=city,
                    per_city=bool(group_spec.get("per_city")),
                    is_home_city=(index == 0),
                    default_matches=default_matches,
                    final_url=final_url,
                    max_cpc=spec.get("max_cpc"),
                    status="Enabled",
                )
                if group:
                    campaign.ad_groups.append(group)

        return campaign


def _campaign_name(trade: str, label: str, fmt: str, market: str = "") -> str:
    """Names are the join key between the plan, the account and every report we
    ever run against it, so the shape is fixed by the blueprint rather than by
    each campaign. Extracted blueprints set `{label}` to keep the source
    account's own naming untouched."""
    code = TRADE_CODES.get(trade, trade[:3].upper())
    return render(fmt, {"code": code, "label": label, "trade": trade, "market": market})


def _allocate_budget(plan: Plan, specs: list[dict], brief: dict, blueprint: dict) -> dict[str, float]:
    """Blueprint weights, overridable per client, normalised across whatever is
    switched on — so dropping a campaign redistributes rather than under-spends."""
    budget_cfg = blueprint.get("budget", {})
    days = float(budget_cfg.get("days_per_month", 30.4))
    min_daily = float(budget_cfg.get("min_daily", 0))
    overrides = (brief.get("budget", {}).get("weights") or {})

    # An extracted blueprint has no hand-set weights, so fall back to what the
    # source account actually spent on each theme.
    weights = {s["key"]: float(overrides.get(s["key"],
               s.get("budget_weight") or s.get("typical_daily_budget") or 1)) for s in specs}
    total_weight = sum(weights.values())
    if total_weight <= 0:
        raise BriefError("all campaign budget weights are zero")

    daily_pool = float(brief["budget"]["monthly_total"]) / days
    allocations = {k: round(daily_pool * w / total_weight, 2) for k, w in weights.items()}

    for key, amount in allocations.items():
        if amount < min_daily:
            plan.warn(
                f"{key}: daily budget {amount:.2f} is under the {min_daily:.2f} floor "
                f"and was raised — total spend will exceed the monthly figure"
            )
            allocations[key] = min_daily

    return allocations


def _account_negatives(blueprint: dict, blueprint_dir: Path) -> list[NegativeKeyword]:
    spec = blueprint.get("negatives", {}).get("account_level", {})
    match_type = spec.get("match_type", "phrase")
    negatives: list[NegativeKeyword] = []

    if "from_file" in spec:
        path = blueprint_dir / spec["from_file"]
        for line in path.read_text().splitlines():
            line = line.split("#")[0].strip()
            if line:
                negatives.append(NegativeKeyword(line, match_type, source="universal"))

    themes = blueprint.get("themes", {})
    negatives += _theme_negatives(spec.get("themes", []), themes)

    # The exact-match competitor wall. It was declared in the blueprint and read
    # by nothing — 605 negatives mined from real spend, silently absent from
    # every build until a benchmark against the live account caught it.
    wall = blueprint.get("negatives", {}).get("competitor_wall", {})
    if "from_file" in wall:
        path = blueprint_dir / wall["from_file"]
        if path.exists():
            match = wall.get("match_type", "exact")
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.split("#")[0].strip()
                if line:
                    negatives.append(NegativeKeyword(line, match, source="competitor-wall"))
    return negatives


def _build_assets(blueprint: dict, brief: dict) -> list[Asset]:
    """Sitelinks, callouts, snippets and the call asset, on every campaign.

    Google flags a Search campaign without these, and it is right to: they are
    extra lines on the results page that competitors will be using. The source
    account carries all of them.

    Callouts come from the blueprint because they say nothing client-specific.
    Sitelinks and snippet values come from the client's own services, because
    linking one client to another's service pages would be worse than useless.
    """
    spec = blueprint.get("assets", {})
    assets: list[Asset] = []

    for text in spec.get("callouts", [])[:6]:
        if text:
            assets.append(Asset("callout", text=text[:25]))

    pages = brief.get("landing_pages", {})
    default_url = pages.get("default", "")
    services = brief.get("landing", {}).get("services") or []

    for service in services[:6]:
        key = re.sub(r"[^a-z0-9]+", "_", service.lower()).strip("_")
        assets.append(Asset(
            "sitelink",
            text=service[:25],
            description1=f"{service} done properly"[:35],
            description2="Free quote, no obligation"[:35],
            final_url=pages.get(key) or default_url,
        ))
    if services and default_url:
        assets.append(Asset("sitelink", text="Get a Quote"[:25],
                            description1="Tell us about your job"[:35],
                            description2="We reply the same day"[:35],
                            final_url=default_url))

    values = services or spec.get("snippet_values", [])
    if values:
        assets.append(Asset("snippet", header=spec.get("snippet_header", "Service catalog"),
                            values=[v[:25] for v in values[:10]]))

    tracking = brief.get("tracking", {})
    client = brief.get("client", {})
    # Only a tracking number ships. The checklist says in bold not to use the
    # public number, so emitting it anyway made the deliverable argue with
    # itself — and calls from ads would be unattributable.
    phone = tracking.get("call_tracking_number")
    if phone:
        # Country follows the currency unless stated. Getting this wrong makes
        # Google reject the call asset outright.
        country = client.get("country") or {"USD": "US", "CAD": "CA", "GBP": "GB",
                                            "AUD": "AU", "EUR": "IE"}.get(
                                                client.get("currency", ""), "CA")
        assets.append(Asset("call", phone=phone, country=country))

    return assets


def _literal_negatives(entries: list[dict], context: dict) -> list[NegativeKeyword]:
    """Negatives lifted verbatim from an extracted account."""
    return [
        NegativeKeyword(
            render(entry["text"], dict(context, term="")),
            entry.get("match_type", "phrase"),
            source="extracted",
        )
        for entry in entries
    ]


def _theme_negatives(theme_names: list[str], themes: dict[str, list[str]]) -> list[NegativeKeyword]:
    """Cross-campaign exclusion. Every campaign blocks the vocabularies that
    belong to its siblings, so the account never bids against itself."""
    out: list[NegativeKeyword] = []
    for name in theme_names:
        for term in themes.get(name, []):
            out.append(NegativeKeyword(term, "phrase", source=f"theme:{name}"))
    return out


def _build_ad_group(
    *,
    plan: Plan,
    group_spec: dict,
    brief: dict,
    themes: dict,
    context: dict,
    city: str,
    per_city: bool,
    is_home_city: bool,
    default_matches: list[str],
    final_url: str,
    max_cpc: float | None,
    status: str,
) -> AdGroup | None:
    label = render(group_spec["label"], context)
    name = f"{label} | {city}" if per_city else label

    # Two ways to specify keywords. `keywords` is a literal, already-parameterised
    # list — what extract.py emits, because a proven account's keywords should be
    # carried over as-is rather than re-derived. `keyword_themes` + `patterns` is
    # the generative form, used by hand-written blueprints.
    if literal := group_spec.get("keywords"):
        terms, patterns = [""], literal
    else:
        terms = _group_terms(group_spec, brief, themes)
        patterns = group_spec.get("patterns", ["{term}"])

    if not terms or not patterns:
        plan.warn(f"{name}: no keyword terms resolved — ad group skipped")
        return None

    matches = group_spec.get("match_types", default_matches)

    seen: set[tuple[str, str]] = set()
    keywords: list[Keyword] = []
    for term in terms:
        for pattern in patterns:
            # A pattern with no {city} ("movers near me") renders identically in
            # every city's ad group. Keep it in the home city only, or the same
            # keyword competes with itself and splits its own performance data.
            if per_city and not is_home_city and "{city}" not in pattern:
                continue
            text = " ".join(render(pattern, dict(context, term=term)).split()).lower()
            for match_type in matches:
                if (text, match_type) not in seen:
                    seen.add((text, match_type))
                    keywords.append(Keyword(text, match_type, final_url))

    ad = _build_rsa(plan, group_spec.get("rsa", {}), context, final_url, name)

    return AdGroup(
        name=name,
        keywords=keywords,
        ads=[ad] if ad else [],
        max_cpc=max_cpc,
        status=status,
    )


def _group_terms(group_spec: dict, brief: dict, themes: dict) -> list[str]:
    """Terms come either from blueprint vocabularies or straight from the brief
    (brand terms are the client's own, so they can't live in a shared template)."""
    source = group_spec.get("keyword_source")
    if source == "brand_terms":
        return list(brief.get("positioning", {}).get("brand_terms") or [])

    terms: list[str] = []
    for theme in group_spec.get("keyword_themes", []):
        terms.extend(themes.get(theme, []))
    return terms


def _build_rsa(
    plan: Plan, rsa_spec: dict, context: dict, final_url: str, where: str
) -> ResponsiveSearchAd | None:
    if not rsa_spec:
        return None

    # Render first, measure second. A template that fits for "Vaughan" can
    # overflow for "Mississauga", so length is only knowable per city.
    headlines, long_h, empty_h = _fit(rsa_spec.get("headlines", []), context, MAX_HEADLINE)
    descriptions, long_d, empty_d = _fit(rsa_spec.get("descriptions", []), context, MAX_DESCRIPTION)

    # Distinguish the two causes: one is a copywriting problem, the other means
    # the brief left a field blank. Reporting both as "too long" sends whoever
    # reads this to the wrong file.
    for label, too_long, empty in (
        ("headline", long_h, empty_h),
        ("description", long_d, empty_d),
    ):
        if too_long:
            plan.warn(
                f"{where}: {too_long} {label}(s) dropped — over the limit once "
                f"'{context['city']}' was substituted in"
            )
        if empty:
            plan.warn(
                f"{where}: {empty} {label}(s) dropped — a placeholder rendered "
                f"empty, so a brief field is blank"
            )

    if len(headlines) < RSA_MIN_HEADLINES:
        plan.warn(f"{where}: only {len(headlines)} headlines survived — ad not built")
        return None

    return ResponsiveSearchAd(
        headlines=headlines[:RSA_MAX_HEADLINES],
        descriptions=descriptions[:RSA_MAX_DESCRIPTIONS],
        final_url=final_url,
        path1=render(rsa_spec.get("path1", ""), context)[:15],
        path2=render(rsa_spec.get("path2", ""), context)[:15],
    )


def _fit(templates: list[str], context: dict, limit: int) -> tuple[list[str], int, int]:
    """Render templates and keep the ones that fit. Returns the survivors plus
    how many fell out for each reason, so the two can be reported apart."""
    kept: list[str] = []
    too_long = empty = 0

    for template in templates:
        text = render(template, context).strip()
        if not text:
            empty += 1
        elif display_length(text) > limit:
            too_long += 1
        elif text not in kept:
            kept.append(text)

    return kept, too_long, empty


def _final_url(brief: dict, campaign_key: str) -> str:
    pages = brief.get("landing_pages", {})
    return pages.get(campaign_key) or require(brief, "landing_pages.default")


def _build_schedule(name: str | None, schedules: dict, brief: dict) -> list[ScheduleSlot]:
    spec = schedules.get(name or "", {})
    kind = spec.get("kind")

    if kind == "all_week" or brief.get("hours", {}).get("always"):
        return [ScheduleSlot(day, "00:00", "24:00") for day in WEEKDAYS + ["Saturday", "Sunday"]]
    if kind != "from_brief":
        return []

    hours = brief.get("hours", {}).get("open", {})
    extend = int(spec.get("extend_evening_hours", 0))
    slots: list[ScheduleSlot] = []

    def add(days: list[str], window: list[str] | None) -> None:
        if not window:
            return
        start, end = window
        if extend:
            hour = min(23, int(end.split(":")[0]) + extend)
            end = f"{hour:02d}:{end.split(':')[1]}"
        slots.extend(ScheduleSlot(day, start, end) for day in days)

    add(WEEKDAYS, hours.get("mon_fri"))
    add(["Saturday"], hours.get("sat"))
    add(["Sunday"], hours.get("sun"))
    return slots
