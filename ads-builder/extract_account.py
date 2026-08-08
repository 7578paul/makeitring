#!/usr/bin/env python3
"""Turn a Google Ads Editor account export into a blueprint.

Written against the real Moving Papa export (UTF-16, tab separated, one wide
table where a row's type is implied by which cells are filled).

The account is organised as `Market | Channel | Theme [| GEOs]`. Markets are
client-specific and come from the brief; **themes** are the reusable part, so
this collapses every market's copy of a theme into one template and swaps city
names for {city}.

    python extract_account.py --data data.csv --out blueprints/moving.yaml
"""

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

csv.field_size_limit(10**8)

# Places that appear inside campaign names, ad groups, keywords and ad copy.
# Anything not listed here stays hard-coded into the template, so this list
# matters more than it looks.
PLACES = [
    "Oakville & Surrounding", "Hamilton, Burlington", "Richmond Hill", "North York",
    "Toronto", "Vancouver", "Ottawa", "Barrie", "Oshawa", "Oakville", "London",
    "Hamilton", "Burlington", "Mississauga", "Vaughan", "Etobicoke", "Scarborough",
    "Markham", "Brampton", "Ajax", "Whitby", "Pickering", "Milton", "Guelph",
    "Kitchener", "Waterloo", "Cambridge", "Newmarket", "New Market", "Aurora", "Burnaby",
    "Richmond", "Surrey", "Coquitlam", "Langley", "Delta", "Abbotsford", "York",
    # Other metros and regions the source account blocks so its markets do not
    # overlap. Every one of these must be caught, or it leaks into the list a
    # new client inherits.
    "Calgary", "Edmonton", "Montreal", "Quebec", "Halifax", "Kingston", "Regina",
    "Winnipeg", "Saskatoon", "Victoria", "Windsor", "Belleville", "Brantford",
    "Chatham", "Chilliwack", "Cochrane", "Collingwood", "Comox", "Kelowna",
    "Ladner", "Lindsay", "Maple", "Moncton", "Muskoka", "Niagara", "Niagara Falls",
    "Orillia", "Owen Sound", "Penticton", "Peterborough", "Sarnia", "Sudbury",
    "Caledonia", "Nanaimo", "Kamloops", "Vernon", "Squamish", "Whistler",
    # Provinces, states and catch-all regions
    "Alberta", "BC", "British Columbia", "Ontario", "Manitoba", "Saskatchewan",
    "Nova Scotia", "New Brunswick", "Newfoundland", "Canada", "GTA",
    "Fraser Valley", "Durham", "Peel", "Halton", "Niagara Region",
]

TCPA_NOTE = "taken from the live account, not invented"


def norm(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def read(path: Path) -> list[dict]:
    for encoding in ("utf-16", "utf-8-sig", "latin-1"):
        try:
            text = path.read_text(encoding=encoding)
            if text.count("\t") > text.count(","):
                delimiter = "\t"
            else:
                delimiter = ","
            rows = list(csv.DictReader(text.splitlines(), delimiter=delimiter))
            if rows and len(rows[0]) > 5:
                print(f"  {len(rows):,} rows ({encoding}, "
                      f"{'tab' if delimiter == chr(9) else 'comma'} separated)")
                return rows
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise SystemExit(f"could not read {path}")


def split_name(name: str) -> tuple[str, str]:
    """`Toronto | Search | General Moving | GEOs` -> ('Toronto', 'General Moving | GEOs')"""
    parts = [p.strip() for p in name.split("|")]
    if len(parts) >= 3 and parts[1].lower() in ("search", "display", "video"):
        return parts[0], " | ".join(parts[2:])
    return "", name.strip()


class Places:
    def __init__(self, extra: list[str]):
        names = sorted(set(PLACES + extra), key=len, reverse=True)
        self.res = [(re.compile(rf"(?<!\w){re.escape(n)}(?!\w)", re.I), n) for n in names]

    def strip(self, text: str) -> str:
        out = text or ""
        for pattern, _ in self.res:
            out = pattern.sub("{city}", out)
        # "{city} | {city}" and "{city}, {city}" collapse to one token
        out = re.sub(r"\{city\}(\s*[,&|]\s*\{city\})+", "{city}", out)
        return norm(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--negatives-dir", type=Path, default=None)
    ap.add_argument("--business", default="Moving Papa")
    ap.add_argument("--trade", default="moving")
    ap.add_argument("--extra-cities", nargs="*", default=[])
    args = ap.parse_args()

    rows = read(args.data)
    places = Places(args.extra_cities)
    g = lambda r, k: norm(r.get(k))

    campaigns = {}
    themes = defaultdict(lambda: {
        "ad_groups": defaultdict(lambda: {"keywords": [], "matches": set(), "rsa": None}),
        "budgets": [], "tcpa": Counter(), "bid": Counter(), "markets": set(),
    })
    neg_phrase, neg_exact = Counter(), Counter()
    settings = {}

    for row in rows:
        name = g(row, "Campaign")
        if not name or name.startswith("<"):
            if g(row, "Targeting method"):
                settings["targeting_method"] = g(row, "Targeting method")
            continue

        market, theme = split_name(name)
        entry = campaigns.setdefault(name, {"market": market, "theme": theme})
        bucket = themes[theme]
        if market:
            bucket["markets"].add(market)

        # Budget and target CPA exist at both campaign and ad group level, and an
        # ad group override is not the campaign's setting. Only read them off
        # campaign-level rows, or the more numerous overrides win the count.
        is_campaign_row = not g(row, "Ad Group")
        if is_campaign_row:
            if val := g(row, "Budget"):
                try:
                    bucket["budgets"].append(float(val.replace(",", "")))
                except ValueError:
                    pass
            if val := g(row, "Target CPA"):
                bucket["tcpa"][val] += 1
            if val := g(row, "Bid Strategy Type"):
                bucket["bid"][val] += 1
        for col, key in (("Tracking template", "tracking_template"),
                         ("Networks", "networks"),
                         ("Ad rotation", "ad_rotation"),
                         ("Targeting method", "targeting_method"),
                         ("Exclusion method", "exclusion_method")):
            if (val := g(row, col)) and key not in settings:
                settings[key] = val

        keyword, criterion = g(row, "Keyword"), g(row, "Criterion Type").lower()

        if keyword and "negative" in criterion:
            target = neg_exact if "exact" in criterion else neg_phrase
            target[keyword.lower()] += 1
            continue

        group_name = g(row, "Ad Group")
        if not group_name:
            continue
        group = bucket["ad_groups"][places.strip(group_name)]

        if keyword:
            group["keywords"].append(places.strip(keyword).lower())
            group["matches"].add("exact" if "exact" in criterion else "phrase")

        elif g(row, "Ad type") and not group["rsa"]:
            heads, descs = [], []
            for i in range(1, 16):
                if h := g(row, f"Headline {i}"):
                    heads.append(places.strip(h))
            for i in range(1, 5):
                if d := g(row, f"Description {i}"):
                    descs.append(places.strip(d))
            if heads:
                group["rsa"] = {
                    "headlines": list(dict.fromkeys(heads))[:15],
                    "descriptions": list(dict.fromkeys(descs))[:4],
                }

    n_campaigns = len(campaigns)
    print(f"  {n_campaigns} campaigns across {len(themes)} themes")

    # Negatives shared by most campaigns are the reusable wall; the rest are
    # market-specific noise and are left behind.
    cut = max(2, int(n_campaigns * 0.6))
    universal = sorted(t for t, n in neg_phrase.items() if n >= cut)
    competitors = sorted(t for t, n in neg_exact.items() if n >= cut)
    print(f"  {len(universal):,} universal phrase negatives, "
          f"{len(competitors):,} competitor exact negatives")

    # A live account's negatives are not all reusable. Alongside genuine junk it
    # carries two client-specific kinds, and copying either into a new account
    # does real damage:
    #
    #   * place names — each market blocks the OTHER markets' cities so campaigns
    #     do not cannibalise each other. Reused blindly, a Burlington client is
    #     blocked from the word "burlington".
    #   * the client's own brand — blocked in non-brand campaigns so they do not
    #     steal from the Brand campaign. Reused, it blocks the new client's name.
    #
    # Both must be regenerated per client, never inherited.
    place_words = {p.lower() for p in PLACES + args.extra_cities}
    for name in list(place_words):
        place_words.update(part.strip() for part in re.split(r"[,&]", name) if part.strip())
    brand_words = {w.lower() for w in args.business.split()} | {args.business.lower()}
    brand_words -= {"the", "and", "of"}

    def is_place(term):
        return term.lower() in place_words
    def is_brand(term):
        return term.lower() in brand_words

    market_seps = [t for t in universal if is_place(t)]
    brand_negs = [t for t in universal if is_brand(t) and not is_place(t)]
    safe = [t for t in universal if not is_place(t) and not is_brand(t)]

    print(f"    of which {len(market_seps)} are place names and {len(brand_negs)} are own-brand")
    print(f"    -> {len(safe):,} are safely reusable")

    if args.negatives_dir:
        d = args.negatives_dir
        d.mkdir(parents=True, exist_ok=True)
        (d / "negatives-universal.txt").write_text(
            "# Universal phrase negatives, lifted from the live account and safe to\n"
            "# reuse for any client in this trade.\n"
            f"# Present in at least {cut} of its {n_campaigns} campaigns.\n"
            "# Place names and the source client's own brand have been REMOVED —\n"
            "# see the other two files for why.\n"
            + "\n".join(safe) + "\n", encoding="utf-8")
        (d / "negatives-competitors.txt").write_text(
            "# Competitor brand wall — exact match. Lifted from the live account.\n"
            "# Includes other metros on purpose: an irrelevant negative costs nothing.\n"
            + "\n".join(competitors) + "\n", encoding="utf-8")
        (d / "negatives-market-separation.txt").write_text(
            "# DO NOT COPY THIS FILE INTO A NEW ACCOUNT.\n"
            "#\n"
            "# These are place names the source account blocks so its per-market\n"
            "# campaigns do not bid against each other. They are correct for THAT\n"
            "# client and wrong for anyone else: reuse them and you block a new\n"
            "# client from their own city.\n"
            "#\n"
            "# Kept only as evidence of the technique. The builder regenerates the\n"
            "# equivalent per client, from the markets in their brief.\n"
            + "\n".join(market_seps) + "\n", encoding="utf-8")
        (d / "negatives-own-brand.txt").write_text(
            "# DO NOT COPY THIS FILE INTO A NEW ACCOUNT.\n"
            "#\n"
            "# The source client's own brand, blocked in their non-brand campaigns\n"
            "# so those campaigns do not steal traffic the Brand campaign wins more\n"
            "# cheaply. Regenerate per client from their own brand terms.\n"
            + "\n".join(brand_negs) + "\n", encoding="utf-8")

    out_themes = []
    for theme, data in sorted(themes.items(), key=lambda kv: -len(kv[1]["markets"])):
        groups = []
        for label, grp in data["ad_groups"].items():
            keywords = list(dict.fromkeys(k for k in grp["keywords"] if k))
            if not keywords:
                continue
            spec = {
                "key": re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or "group",
                "label": label,
                "per_city": "{city}" in label,
                "match_types": sorted(grp["matches"]) or ["phrase"],
                "keywords": keywords,
            }
            if grp["rsa"]:
                spec["rsa"] = grp["rsa"]
            groups.append(spec)
        if not groups:
            continue

        budgets = data["budgets"]
        out_themes.append({
            "key": re.sub(r"[^a-z0-9]+", "_", theme.lower()).strip("_"),
            "label": theme,
            "markets_seen": sorted(data["markets"]),
            "typical_daily_budget": round(sum(budgets) / len(budgets), 2) if budgets else None,
            "target_cpa": float(data["tcpa"].most_common(1)[0][0]) if data["tcpa"] else None,
            "bid_strategy": data["bid"].most_common(1)[0][0] if data["bid"] else None,
            "ad_groups": groups,
        })

    blueprint = {
        "trade": args.trade,
        "version": "1.0-from-account",
        "source": f"extracted from the live {args.business} Google Ads account",
        "structure": "campaigns are built per market: '{market} | Search | {theme}'",
        "defaults": {
            "campaign_type": "Search",
            "campaign_name_format": "{market} | Search | {label}",
            "networks": settings.get("networks", "Google search"),
            "language": "English",
            "bid_strategy": "Maximize conversions",
            "location_target_type": settings.get("targeting_method", "Location of presence"),
            "location_exclusion_type": settings.get("exclusion_method", "Location of presence"),
            "tracking_template": settings.get("tracking_template", ""),
            "ad_rotation": settings.get("ad_rotation", "Optimize"),
            "status": "Paused",
            "match_types": ["phrase"],
            "target_cpa_note": TCPA_NOTE,
        },
        "budget": {"min_daily": 50.0, "days_per_month": 30.4},
        "negatives": {
            "account_level": {
                "from_file": "_shared/negatives-universal.txt",
                "match_type": "phrase",
                "themes": [],
            },
            "competitor_wall": {
                "from_file": "_shared/negatives-competitors.txt",
                "match_type": "exact",
            },
        },
        "themes": {},
        "campaigns": out_themes,
        "schedules": {"always": {"kind": "all_week"},
                      "business_hours": {"kind": "from_brief"}},
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(blueprint, handle, sort_keys=False, allow_unicode=True, width=110)

    print(f"\n{'THEME':<34}{'MARKETS':>9}{'GROUPS':>8}{'KEYWORDS':>10}{'tCPA':>8}{'BUDGET':>9}")
    for t in out_themes:
        kw = sum(len(g["keywords"]) for g in t["ad_groups"])
        print(f"{t['label'][:33]:<34}{len(t['markets_seen']):>9}{len(t['ad_groups']):>8}"
              f"{kw:>10}{t['target_cpa'] or 0:>8.0f}{t['typical_daily_budget'] or 0:>9.0f}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
