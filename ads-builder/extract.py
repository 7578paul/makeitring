#!/usr/bin/env python3
"""Google Ads Editor export -> blueprint YAML.

The blueprint should encode what an expert actually built and proved, not what
anyone guessed. This reads an Editor CSV export of a real account and turns it
back into a reusable template: city names become {city}, the business name
becomes {business}, the phone becomes {phone}, and everything else is preserved
verbatim — their keywords, their ad copy, their negatives, their budget split.

    python extract.py --export ./export.zip \\
        --trade moving \\
        --business "Moving Papa" \\
        --phone "833-351-1791" \\
        --cities Toronto Vancouver Ottawa Calgary Edmonton \\
        --out blueprints/moving.yaml

Column matching is deliberately loose: Editor's headers vary by version and
account language, so every lookup tries several spellings and the run reports
anything it could not classify rather than dropping it silently.
"""

import argparse
import csv
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import yaml

# Each logical field maps to the header spellings Editor is known to use.
FIELDS = {
    "campaign": ["campaign"],
    "ad_group": ["ad group", "adgroup", "ad group name"],
    "keyword": ["keyword", "criterion", "keyword text"],
    "criterion_type": ["criterion type", "match type", "type"],
    "budget": ["budget", "campaign daily budget", "daily budget"],
    "bid_strategy": ["bid strategy type", "bid strategy", "campaign bid strategy type"],
    "max_cpc": ["max cpc", "default max cpc", "cpc bid", "ad group max cpc"],
    "final_url": ["final url", "final urls", "destination url"],
    "ad_type": ["ad type", "ad_type"],
    "path1": ["path 1", "path1"],
    "path2": ["path 2", "path2"],
    "status": ["status", "campaign status", "ad group status"],
    "campaign_type": ["campaign type"],
}

MATCH_TYPES = {
    "broad": "broad", "phrase": "phrase", "exact": "exact",
    "broad match": "broad", "phrase match": "phrase", "exact match": "exact",
}


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def get(row: dict[str, str], field: str) -> str:
    """Fetch a logical field from a row whose headers we do not control."""
    for candidate in FIELDS[field]:
        if candidate in row and norm(row[candidate]):
            return norm(row[candidate])
    return ""


def decode(raw: bytes) -> str | None:
    """Editor writes UTF-16 with a BOM on some platforms and UTF-8 on others."""
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return None


def parse_table(name: str, text: str, rows: list[dict[str, str]]) -> None:
    first = text.split("\n", 1)[0]
    delimiter = "\t" if (name.lower().endswith(".tsv") or "\t" in first) else ","
    count = 0
    for raw in csv.DictReader(text.splitlines(), delimiter=delimiter):
        rows.append({(k or "").strip().lower(): (v or "") for k, v in raw.items()})
        count += 1
    print(f"  read {count:>7} rows from {name}")


def read_rows(export: Path) -> list[dict[str, str]]:
    """Accepts a directory, a single CSV, or a zip of them.

    A whole-account export runs to tens of megabytes, mostly location criteria,
    and zips to a small fraction of that — so taking the zip directly saves
    everyone a step.
    """
    rows: list[dict[str, str]] = []

    if export.is_file() and export.suffix.lower() == ".zip":
        with zipfile.ZipFile(export) as archive:
            members = [m for m in archive.namelist()
                       if m.lower().endswith((".csv", ".tsv")) and not m.startswith("__MACOSX")]
            if not members:
                raise SystemExit(f"no CSV/TSV files inside {export.name}")
            for member in sorted(members):
                text = decode(archive.read(member))
                if text is None:
                    print(f"  ! could not decode {member}, skipped", file=sys.stderr)
                    continue
                parse_table(Path(member).name, text, rows)
        return rows

    files = [export] if export.is_file() else sorted(
        p for p in export.rglob("*") if p.suffix.lower() in (".csv", ".tsv")
    )
    if not files:
        raise SystemExit(f"no CSV/TSV files under {export}")

    for path in files:
        text = decode(path.read_bytes())
        if text is None:
            print(f"  ! could not decode {path.name}, skipped", file=sys.stderr)
            continue
        parse_table(path.name, text, rows)

    return rows


class Parameteriser:
    """Swaps client-specific strings for placeholders, longest match first so
    'Moving Papa Toronto' does not half-match on 'Toronto'."""

    def __init__(self, business: str, phone: str, cities: list[str]):
        self.cities = cities
        self.rules: list[tuple[re.Pattern, str]] = []

        if business:
            self.rules.append((self._word_re(business), "{business}"))
        for city in sorted(cities, key=len, reverse=True):
            self.rules.append((self._word_re(city), "{city}"))
        if phone:
            self.rules.append((self._phone_re(phone), "{phone}"))

    @staticmethod
    def _word_re(value: str) -> re.Pattern:
        return re.compile(rf"(?<![\w]){re.escape(value)}(?![\w])", re.IGNORECASE)

    @staticmethod
    def _phone_re(phone: str) -> re.Pattern:
        digits = re.sub(r"\D", "", phone)[-10:]
        # Match the same 10 digits however they are punctuated.
        return re.compile(r"[\+\d][\d\s\-\(\)\.]{7,}\d") if not digits else re.compile(
            r"\+?1?[\s\-\.\(]*" + r"[\s\-\.\)\(]*".join(digits) + r""
        )

    def apply(self, text: str) -> str:
        out = text
        for pattern, token in self.rules:
            out = pattern.sub(token, out)
        return norm(out)

    def city_of(self, text: str) -> str | None:
        for city in sorted(self.cities, key=len, reverse=True):
            if self._word_re(city).search(text):
                return city
        return None


def classify(row: dict[str, str]) -> str:
    """Work out what an Editor row is from which of its cells are filled."""
    keyword = get(row, "keyword")
    criterion = get(row, "criterion_type").lower()

    if keyword and "negative" in criterion:
        return "negative"
    if keyword and any(m in criterion for m in MATCH_TYPES):
        return "keyword"
    if any(h.startswith("headline") and norm(v) for h, v in row.items()):
        return "ad"
    if get(row, "ad_type"):
        return "ad"
    if get(row, "ad_group"):
        return "ad_group"
    if get(row, "campaign"):
        return "campaign"
    return "unknown"


def match_type_of(criterion: str) -> str:
    lowered = criterion.lower().replace("campaign negative", "").replace("negative", "").strip()
    return MATCH_TYPES.get(lowered, "phrase")


def extract(rows: list[dict[str, str]], param: Parameteriser) -> tuple[dict, Counter]:
    """Fold flat Editor rows into a nested account model, parameterised."""
    campaigns: dict[str, dict[str, Any]] = {}
    tally: Counter = Counter()

    def campaign_of(name: str) -> dict[str, Any]:
        return campaigns.setdefault(
            name,
            {
                "raw_name": name,
                "label": param.apply(name),
                "budget": 0.0,
                "bid_strategy": None,
                "max_cpc": None,
                "ad_groups": {},
                "negatives": [],
            },
        )

    for row in rows:
        kind = classify(row)
        tally[kind] += 1

        campaign_name = get(row, "campaign")
        if not campaign_name:
            continue
        campaign = campaign_of(campaign_name)

        if kind == "campaign":
            budget = get(row, "budget").replace(",", "")
            if budget:
                try:
                    campaign["budget"] = float(re.sub(r"[^\d.]", "", budget) or 0)
                except ValueError:
                    pass
            campaign["bid_strategy"] = campaign["bid_strategy"] or get(row, "bid_strategy") or None
            continue

        if kind == "negative":
            campaign["negatives"].append(
                {"text": param.apply(get(row, "keyword")),
                 "match_type": match_type_of(get(row, "criterion_type"))}
            )
            continue

        group_name = get(row, "ad_group")
        if not group_name:
            continue

        group = campaign["ad_groups"].setdefault(
            group_name,
            {
                "raw_name": group_name,
                "label": param.apply(group_name),
                "city": param.city_of(group_name),
                "keywords": [],
                "match_types": set(),
                "headlines": [],
                "descriptions": [],
                "paths": [],
                "final_urls": [],
            },
        )

        if kind == "keyword":
            group["keywords"].append(param.apply(get(row, "keyword")))
            group["match_types"].add(match_type_of(get(row, "criterion_type")))
            if url := get(row, "final_url"):
                group["final_urls"].append(url)

        elif kind == "ad":
            for header, value in row.items():
                value = norm(value)
                if not value:
                    continue
                if header.startswith("headline"):
                    group["headlines"].append(param.apply(value))
                elif header.startswith("description"):
                    group["descriptions"].append(param.apply(value))
            group["paths"].append((param.apply(get(row, "path1")), param.apply(get(row, "path2"))))
            if url := get(row, "final_url"):
                group["final_urls"].append(url)

        elif kind == "ad_group":
            if cpc := get(row, "max_cpc"):
                try:
                    group.setdefault("max_cpc", float(re.sub(r"[^\d.]", "", cpc) or 0))
                except ValueError:
                    pass

    return campaigns, tally


def dedupe(values: Iterable[str]) -> list[str]:
    """Order-preserving dedupe. Order carries meaning: Editor exports assets in
    the order the expert entered them, and headline order is a real signal."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "campaign"


def to_blueprint(campaigns: dict, trade: str, cities: list[str]) -> dict:
    total_budget = sum(c["budget"] for c in campaigns.values()) or 1.0
    out_campaigns = []

    for campaign in campaigns.values():
        # Ad groups whose names collapse to the same label once the city is
        # swapped out are one templated group, not N separate ones.
        clusters: dict[str, list[dict]] = defaultdict(list)
        for group in campaign["ad_groups"].values():
            clusters[group["label"]].append(group)

        group_specs = []
        for label, members in clusters.items():
            per_city = len(members) > 1 or any(m["city"] for m in members)
            keywords = dedupe(k for m in members for k in m["keywords"])
            headlines = dedupe(h for m in members for h in m["headlines"])
            descriptions = dedupe(d for m in members for d in m["descriptions"])
            match_types = sorted({mt for m in members for mt in m["match_types"]}) or ["phrase"]
            paths = [p for m in members for p in m["paths"] if any(p)]

            if not keywords:
                continue

            spec: dict[str, Any] = {
                "key": slug(label),
                "label": label,
                "per_city": per_city,
                "match_types": match_types,
                "keywords": keywords,
            }
            if headlines or descriptions:
                spec["rsa"] = {
                    "headlines": headlines[:15],
                    "descriptions": descriptions[:4],
                }
                if paths:
                    spec["rsa"]["path1"], spec["rsa"]["path2"] = paths[0]
            group_specs.append(spec)

        if not group_specs:
            continue

        spec = {
            "key": slug(campaign["label"]),
            "label": campaign["label"],
            "budget_weight": round(campaign["budget"] / total_budget * 100, 1),
            "ad_groups": group_specs,
        }
        if campaign["bid_strategy"]:
            spec["bid_strategy"] = campaign["bid_strategy"]
        if campaign["negatives"]:
            seen: set[tuple[str, str]] = set()
            negatives = []
            for negative in campaign["negatives"]:
                key = (negative["text"], negative["match_type"])
                if key not in seen:
                    seen.add(key)
                    negatives.append(negative)
            spec["negative_keywords"] = negatives
        out_campaigns.append(spec)

    return {
        "trade": trade,
        "version": "1.0-extracted",
        "source": "extracted from a Google Ads Editor export of a live account",
        "defaults": {
            "campaign_type": "Search",
            "networks": "Google search",
            "language": "English",
            "bid_strategy": "Maximize conversions",
            "location_target_type": "presence",
            "status": "Paused",
            "match_types": ["phrase", "exact"],
            # Preserve the source account's campaign names verbatim rather than
            # imposing our own convention on someone else's proven structure.
            "campaign_name_format": "{label}",
        },
        "budget": {"min_daily": 5.0, "days_per_month": 30.4},
        "themes": {},
        "negatives": {"account_level": {"from_file": "_shared/negatives-universal.txt",
                                        "match_type": "phrase", "themes": []}},
        "campaigns": out_campaigns,
        "schedules": {"always": {"kind": "all_week"},
                      "business_hours": {"kind": "from_brief"}},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--export", "--export-dir", dest="export", type=Path, required=True,
                        help="a directory of CSVs, a single CSV, or a .zip of them")
    parser.add_argument("--trade", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--business", default="", help="business name to replace with {business}")
    parser.add_argument("--phone", default="", help="phone to replace with {phone}")
    parser.add_argument("--cities", nargs="*", default=[], help="cities to replace with {city}")
    args = parser.parse_args()

    print(f"reading {args.export}")
    rows = read_rows(args.export)

    param = Parameteriser(args.business, args.phone, args.cities)
    campaigns, tally = extract(rows, param)

    print("\nrow types found:")
    for kind, count in tally.most_common():
        print(f"  {kind:<10} {count:>6}")
    if tally.get("unknown"):
        print(f"\n  ! {tally['unknown']} rows could not be classified — check the "
              f"headers against FIELDS in extract.py")

    blueprint = to_blueprint(campaigns, args.trade, args.cities)

    print(f"\nextracted {len(blueprint['campaigns'])} campaigns:")
    for campaign in blueprint["campaigns"]:
        keywords = sum(len(g["keywords"]) for g in campaign["ad_groups"])
        print(f"  {campaign['budget_weight']:>5.1f}%  {campaign['label']:<45} "
              f"{len(campaign['ad_groups']):>3} groups  {keywords:>5} keywords")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(blueprint, handle, sort_keys=False, allow_unicode=True, width=100)

    print(f"\nwrote {args.out}")
    print("Review it before use — the extractor preserves structure, it does not "
          "judge whether the structure is good.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
