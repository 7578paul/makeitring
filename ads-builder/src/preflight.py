"""Pre-flight safety checks — run before anything is exported.

The negative wall is the most valuable thing in the account and the most
dangerous thing to reuse. A list mined from one client carries that client's
cities and brand inside it, and pasted into a new account it silently blocks
the new client from their own market. It fails quietly: campaigns run, spend
money, and simply never show for the searches that matter.

So the rule is that no negative list is trusted. Every negative is tested
against the keywords we are actually about to build, using Google's real match
semantics, and anything that would block our own traffic is an error.

Five checks:
  1. self-block      — a negative blocks a keyword we are building
  2. own-city        — a negative blocks the client's own market
  3. own-brand       — a negative blocks the client's own name
  4. cannibalisation — two ad groups bidding on the same keyword
  5. market bleed    — markets that fail to exclude each other, or overlap
"""

import re
from dataclasses import dataclass

from .model import NegativeKeyword

# Google treats these as the same query.
_PUNCT = re.compile(r"[^\w\s]")


def normalise(text: str) -> str:
    return " ".join(_PUNCT.sub(" ", (text or "").lower()).split())


def blocks(negative: str, match_type: str, query: str) -> bool:
    """Would this negative stop this query from serving?

    Mirrors Google's semantics rather than doing substring matching, which
    would over-report wildly: negative "art" does not block "apartment movers".
    """
    n, q = normalise(negative), normalise(query)
    if not n or not q:
        return False

    if match_type == "exact":
        return n == q
    if match_type == "phrase":
        # a contiguous run of whole words
        return f" {n} " in f" {q} "
    # broad: every word present, in any order
    q_words = set(q.split())
    return all(word in q_words for word in n.split())


@dataclass
class Conflict:
    severity: str
    kind: str
    detail: str
    fix: str = ""

    def __str__(self) -> str:
        line = f"[{self.severity.upper():7}] {self.kind}: {self.detail}"
        return f"{line}\n{'':10}fix: {self.fix}" if self.fix else line


def check(
    *,
    keywords: list[tuple[str, str, str]],   # (campaign, ad_group, keyword_text)
    negatives: list[tuple[str, str]],       # (text, match_type)
    brand_terms: list[str],
    cities: list[str],
    markets: dict[str, list[str]] | None = None,   # market -> cities it targets
) -> list[Conflict]:
    out: list[Conflict] = []

    # ---- 1. would any negative block a keyword we are about to build? -------
    # This is the check that catches an inherited list carrying someone else's
    # geography. Report per negative rather than per keyword, or one bad term
    # produces a hundred identical lines.
    blocked_by: dict[tuple[str, str], list[str]] = {}
    for text, match_type in negatives:
        for _campaign, group, keyword in keywords:
            if blocks(text, match_type, keyword):
                blocked_by.setdefault((text, match_type), []).append(f"{group} › {keyword}")

    for (text, match_type), hits in sorted(blocked_by.items(), key=lambda kv: -len(kv[1])):
        sample = "; ".join(hits[:3]) + (f" (+{len(hits) - 3} more)" if len(hits) > 3 else "")
        out.append(Conflict(
            "error", "self-block",
            f'negative "{text}" [{match_type}] blocks {len(hits)} of our own '
            f"keywords — {sample}",
            f'remove "{text}" from the negative list for this client',
        ))

    # ---- 2. does a negative block the client's own city? -------------------
    for text, match_type in negatives:
        for city in cities:
            if blocks(text, match_type, city):
                out.append(Conflict(
                    "error", "own-city",
                    f'negative "{text}" [{match_type}] blocks the client\'s own '
                    f'market "{city}"',
                    f'remove "{text}" — it belongs to the account this list came from',
                ))

    # ---- 3. does a negative block the client's own brand? ------------------
    for text, match_type in negatives:
        for brand in brand_terms:
            if blocks(text, match_type, brand):
                out.append(Conflict(
                    "error", "own-brand",
                    f'negative "{text}" [{match_type}] blocks the client\'s own '
                    f'name "{brand}"',
                    f'remove "{text}" — the Brand campaign needs this term',
                ))

    # ---- 4. two ad groups bidding on the same keyword ----------------------
    where: dict[str, list[str]] = {}
    for campaign, group, keyword in keywords:
        where.setdefault(normalise(keyword), []).append(f"{campaign} › {group}")
    for keyword, places in where.items():
        unique = sorted(set(places))
        if len(unique) > 1:
            out.append(Conflict(
                "warning", "cannibalisation",
                f'"{keyword}" is in {len(unique)} ad groups — {", ".join(unique[:3])}',
                "keep it in the most specific ad group and negative it out of the others",
            ))

    # ---- 5. market separation ---------------------------------------------
    if markets and len(markets) > 1:
        for market, own in markets.items():
            others = {c for m, cs in markets.items() if m != market for c in cs}
            overlap = sorted(set(own) & others)
            if overlap:
                out.append(Conflict(
                    "warning", "market-bleed",
                    f'"{market}" targets {", ".join(overlap)}, which another market '
                    f"also targets",
                    "give the city to one market only, or the two campaigns bid "
                    "against each other",
                ))

            # The Moving Papa technique: each market blocks the others' cities.
            missing = [
                city for city in sorted(others - set(own))
                if not any(blocks(t, m, city) for t, m in negatives)
            ]
            if missing:
                out.append(Conflict(
                    "warning", "market-bleed",
                    f'"{market}" does not exclude {len(missing)} other market(s): '
                    f"{', '.join(missing[:5])}",
                    "add them as phrase negatives on this market's campaigns",
                ))

    return out


def errors(conflicts: list[Conflict]) -> list[Conflict]:
    return [c for c in conflicts if c.severity == "error"]


def resolve(
    negatives: list[tuple[str, str]],
    *,
    keywords: list[tuple[str, str, str]],
    brand_terms: list[str],
    cities: list[str],
) -> tuple[list[tuple[str, str]], list[str]]:
    """Drop the negatives that would block this client, and say which.

    Refusing to build is the safe answer but not a useful one — an inherited
    list will always carry some terms that are wrong for a new client, and
    that is expected rather than exceptional. So remove exactly the offenders,
    keep everything else, and report it. The build proceeds; the human sees
    what changed and why.
    """
    targets = [k for _c, _g, k in keywords] + list(cities) + list(brand_terms)
    kept: list[tuple[str, str]] = []
    removed: list[str] = []

    for text, match_type in negatives:
        hit = next((t for t in targets if blocks(text, match_type, t)), None)
        if hit is None:
            kept.append((text, match_type))
        else:
            removed.append(f'"{text}" [{match_type}] — would have blocked "{hit}"')

    return kept, removed


def apply_wall(plan, brief: dict) -> dict:
    """Resolve the negative wall per campaign, with explicit precedence.

    Three kinds of term need three different treatments, and v2 got them wrong
    by treating the wall as one global list:

    * A negative that blocks a client city is FENCING — the source account puts
      "calgary" on its Toronto campaigns so a Toronto searcher typing "movers
      calgary" never triggers Toronto's ads. It belongs on every campaign
      except the market it names, and deleting it globally (v2) or applying it
      globally (which would block the Calgary campaign's own keywords) are both
      wrong. Fences that the wall is missing are generated from the brief.

    * A negative that blocks a campaign's own keyword is a CONFLICT between the
      template and the account. Who wins depends on whose account this is:
      rebuilding the same account (`respect_account_negatives`), the mined
      negative is the client's own "we don't want these jobs" and the template
      keyword is deleted; for a new client, the previous client's exclusion
      gives way. Either way the decision is logged for a human, not silent.

    * Everything else stays, on every campaign.
    """
    markets = brief.get("markets") or []
    cities_by_market = {m["name"]: [c.lower() for c in (m.get("cities") or [])]
                        for m in markets if isinstance(m, dict)}
    if not cities_by_market:
        cities_by_market = {"": [c.lower() for c in
                                 brief.get("service_area", {}).get("cities", [])]}
    all_cities = sorted({c for cs in cities_by_market.values() for c in cs})
    brand_terms = [b.lower() for b in
                   (brief.get("positioning", {}).get("brand_terms") or [])]
    rebuild = bool(brief.get("respect_account_negatives"))

    conflicts: list[str] = []
    dropped_negs: list[str] = []
    fenced = 0

    for campaign in plan.campaigns:
        own = cities_by_market.get(campaign.market) or all_cities
        own_kws = [k.text for g in campaign.ad_groups for k in g.keywords]
        kept, fences_present = [], set()

        for neg in campaign.negatives:
            wall = neg.source in ("universal", "competitor-wall")
            city_hits = [c for c in all_cities if blocks(neg.text, neg.match_type, c)]
            brand_hit = any(blocks(neg.text, neg.match_type, b) for b in brand_terms)

            if brand_hit:
                dropped_negs.append(f"\"{neg.text}\" — blocks the client\'s own brand")
                continue
            if city_hits:
                # fencing: keep unless it names this campaign's own market
                if any(c in own for c in city_hits):
                    continue
                fences_present.update(city_hits)
                kept.append(neg)
                continue

            kw_hits = [kw for kw in own_kws if blocks(neg.text, neg.match_type, kw)]
            if kw_hits and wall:
                if rebuild:
                    # the account's own exclusion beats the template's keyword
                    doomed = set(kw_hits)
                    for g in campaign.ad_groups:
                        g.keywords = [k for k in g.keywords if k.text not in doomed]
                    kept.append(neg)
                    conflicts.append(
                        f"`{neg.text}` [{neg.match_type}] is the account's own negative, "
                        f'and the template wanted to bid on {sorted(doomed)} in '
                        f"{campaign.name} — the keyword(s) were removed. If the account "
                        f"should target this, delete the negative deliberately.")
                else:
                    conflicts.append(
                        f'`{neg.text}` [{neg.match_type}] came from a previous account and '
                        f'would block {kw_hits[:2]} in {campaign.name} — the negative was '
                        f'dropped for this client.')
                continue
            kept.append(neg)

        # fences the wall does not already carry, from the brief's own markets
        if campaign.campaign_type == "Search" and campaign.market in cities_by_market:
            for market_name, market_cities in cities_by_market.items():
                if market_name == campaign.market:
                    continue
                for city in market_cities:
                    if city not in fences_present and city not in own:
                        kept.append(NegativeKeyword(city, "phrase", source="market-fence"))
                        fences_present.add(city)
                        fenced += 1
        campaign.negatives = kept

    # ad groups emptied by conflict resolution cannot serve
    emptied = []
    for campaign in plan.campaigns:
        keep = [g for g in campaign.ad_groups if g.keywords]
        emptied += [f"{campaign.name} › {g.name}" for g in campaign.ad_groups if not g.keywords]
        campaign.ad_groups = keep
    doomed_campaigns = [c for c in plan.campaigns
                        if not c.ad_groups and not c.asset_group]
    plan.campaigns = [c for c in plan.campaigns if c.ad_groups or c.asset_group]

    return {"conflicts": conflicts, "dropped_negatives": dropped_negs,
            "fence_terms": fenced, "emptied_groups": emptied,
            "dropped_campaigns": [c.name for c in doomed_campaigns]}


def load_negatives(*paths) -> list[tuple[str, str]]:
    """Read negative files. `.csv` with a Match type column keeps its match
    types; a plain `.txt` is one phrase negative per line."""
    import csv

    out: list[tuple[str, str]] = []
    for path in paths:
        if not path or not path.exists():
            continue
        if path.suffix.lower() == ".csv":
            with path.open(encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    text = (row.get("Keyword") or "").strip()
                    if text:
                        out.append((text, (row.get("Match type") or "phrase").strip().lower()))
        else:
            default = "exact" if "competitor" in path.name else "phrase"
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.split("#")[0].strip()
                if line:
                    out.append((line, default))
    return out
