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


def render(template: str, context: dict[str, str]) -> str:
    """Fill {placeholders}. An unknown placeholder is a blueprint bug, not a
    runtime condition, so let the KeyError surface with the template attached."""
    try:
        return tidy(template.format(**context))
    except KeyError as exc:
        raise BriefError(f"unknown placeholder {exc} in template {template!r}") from exc


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

    budgets = _allocate_budget(plan, specs, brief, blueprint)
    account_negatives = _account_negatives(blueprint, blueprint_dir)
    schedules = blueprint.get("schedules", {})

    for spec in specs:
        campaign = Campaign(
            key=spec["key"],
            name=_campaign_name(
                trade,
                spec["label"],
                defaults.get("campaign_name_format", "{code} | Search | {label} | EN"),
            ),
            campaign_type=defaults.get("campaign_type", "Search"),
            daily_budget=budgets[spec["key"]],
            bid_strategy=spec.get("bid_strategy", defaults.get("bid_strategy")),
            max_cpc=spec.get("max_cpc"),
            status=defaults.get("status", "Paused"),
            networks=defaults.get("networks", "Google search"),
            language=defaults.get("language", "English"),
            locations=list(geo_targets),
            excluded_locations=list(brief.get("service_area", {}).get("exclude") or []),
            location_target_type=defaults.get("location_target_type", "presence"),
            schedule=_build_schedule(spec.get("schedule"), schedules, brief),
            negatives=list(account_negatives)
            + _theme_negatives(spec.get("negative_themes", []), themes)
            + _literal_negatives(spec.get("negative_keywords", []), base_context),
        )

        final_url = _final_url(brief, spec["key"])
        default_matches = defaults.get("match_types", ["phrase", "exact"])

        for group_spec in spec.get("ad_groups", []):
            targets = cities if group_spec.get("per_city") else [cities[0]]
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
                    status=campaign.status,
                )
                if group:
                    campaign.ad_groups.append(group)

        plan.campaigns.append(campaign)

    return plan


def _campaign_name(trade: str, label: str, fmt: str) -> str:
    """Names are the join key between the plan, the account and every report we
    ever run against it, so the shape is fixed by the blueprint rather than by
    each campaign. Extracted blueprints set `{label}` to keep the source
    account's own naming untouched."""
    code = TRADE_CODES.get(trade, trade[:3].upper())
    return render(fmt, {"code": code, "label": label, "trade": trade})


def _allocate_budget(plan: Plan, specs: list[dict], brief: dict, blueprint: dict) -> dict[str, float]:
    """Blueprint weights, overridable per client, normalised across whatever is
    switched on — so dropping a campaign redistributes rather than under-spends."""
    budget_cfg = blueprint.get("budget", {})
    days = float(budget_cfg.get("days_per_month", 30.4))
    min_daily = float(budget_cfg.get("min_daily", 0))
    overrides = (brief.get("budget", {}).get("weights") or {})

    weights = {s["key"]: float(overrides.get(s["key"], s.get("budget_weight", 1))) for s in specs}
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
    return negatives


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
        elif len(text) > limit:
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
