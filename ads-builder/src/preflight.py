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
