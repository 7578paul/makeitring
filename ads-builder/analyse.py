#!/usr/bin/env python3
"""Read Google Ads performance reports and let the numbers edit the blueprint.

Until now the blueprint said what a good account looks like structurally. It
had no idea which parts of that structure earn anything. These reports do, so
they get to prune it: an ad group that spent money and booked nothing, and a
keyword that has never been served, are both dead weight that every future
client would otherwise inherit.

    python analyse.py --reports ./reports --blueprint blueprints/moving.yaml

Reads the exports from Google Ads (Keywords, Ad groups), which carry two
preamble lines before the header row.
"""

import argparse
import csv
import io
from pathlib import Path

import yaml

# Spend below this is not evidence of anything either way.
MIN_SPEND_TO_JUDGE = 100.0
# An ad group costing more than this multiple of its target is losing money.
CPL_ALARM_MULTIPLE = 2.0


def read_report(path: Path) -> list[dict]:
    """Google's exports carry a title and a date range before the header."""
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines)
                  if line.startswith(("Keyword status", "Ad group status", "Ad status",
                                      "Campaign status", "Negative keyword"))), 0)
    return list(csv.DictReader(io.StringIO("\n".join(lines[start:]))))


def number(value: str) -> float:
    text = (value or "").replace(",", "").replace("$", "").replace("%", "").strip()
    if text in ("", "--", "-"):
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def is_total(row: dict) -> bool:
    return any(str(v).startswith("Total:") for v in row.values() if v)


def analyse_ad_groups(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        if is_total(row) or not (row.get("Ad group") or "").strip():
            continue
        cost, conv = number(row.get("Cost")), number(row.get("Conversions"))
        out.append({
            "ad_group": row["Ad group"].strip(),
            "campaign": (row.get("Campaign") or "").strip(),
            "impressions": number(row.get("Impr.")),
            "cost": cost,
            "conversions": conv,
            "cpl": cost / conv if conv else None,
            "target": number(row.get("Target CPA")) or None,
        })
    return sorted(out, key=lambda r: -r["conversions"])


def analyse_keywords(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        if is_total(row) or not (row.get("Keyword") or "").strip():
            continue
        cost, conv = number(row.get("Cost")), number(row.get("Conversions"))
        out.append({
            "keyword": row["Keyword"].strip().strip('"[]'),
            "ad_group": (row.get("Ad group") or "").strip(),
            "impressions": number(row.get("Impr.")),
            "cost": cost,
            "conversions": conv,
            "cpl": cost / conv if conv else None,
            "reasons": (row.get("Status reasons") or "").strip(),
        })
    return out


def verdicts(groups: list[dict], keywords: list[dict], target_cpl: float) -> dict:
    """Sort everything into keep, watch and cut."""
    never_served = [k for k in keywords if k["impressions"] == 0]
    spent_no_conv = [k for k in keywords
                     if k["conversions"] == 0 and k["cost"] >= MIN_SPEND_TO_JUDGE]

    dead_groups, weak_groups, strong_groups = [], [], []
    for group in groups:
        target = group["target"] or target_cpl
        if group["conversions"] == 0 and group["cost"] >= MIN_SPEND_TO_JUDGE:
            dead_groups.append(group)
        elif group["cpl"] and group["cpl"] > target * CPL_ALARM_MULTIPLE:
            weak_groups.append(group)
        elif group["conversions"] > 0:
            strong_groups.append(group)

    return {
        "never_served": never_served,
        "spent_no_conv": spent_no_conv,
        "dead_groups": dead_groups,
        "weak_groups": sorted(weak_groups, key=lambda g: -(g["cpl"] or 0)),
        "strong_groups": strong_groups,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reports", type=Path, required=True)
    ap.add_argument("--target-cpl", type=float, default=80.0)
    ap.add_argument("--out", type=Path, default=None, help="write findings as YAML")
    ap.add_argument("--apply-to", type=Path, default=None,
                    help="prune a blueprint using these findings")
    args = ap.parse_args()

    files = {p.name.lower(): p for p in args.reports.glob("*.csv")}
    groups_file = next((p for n, p in files.items() if "ad_group" in n), None)
    keywords_file = next((p for n, p in files.items() if "keyword_report" in n
                          and "negative" not in n), None)
    if not groups_file or not keywords_file:
        raise SystemExit("need an ad group report and a search keyword report")

    groups = analyse_ad_groups(read_report(groups_file))
    keywords = analyse_keywords(read_report(keywords_file))
    found = verdicts(groups, keywords, args.target_cpl)

    total_cost = sum(g["cost"] for g in groups)
    total_conv = sum(g["conversions"] for g in groups)
    print(f"\n{len(groups)} ad groups · {len(keywords)} keywords · "
          f"{total_cost:,.0f} spent · {total_conv:,.0f} leads · "
          f"{total_cost / total_conv if total_conv else 0:,.2f} per lead\n")

    print(f"{'AD GROUP':<26}{'CAMPAIGN':<20}{'COST':>10}{'LEADS':>7}{'CPL':>9}   verdict")
    for group in groups:
        target = group["target"] or args.target_cpl
        if group["conversions"] == 0:
            verdict = "no leads" if group["cost"] >= MIN_SPEND_TO_JUDGE else "too early"
        elif group["cpl"] > target * CPL_ALARM_MULTIPLE:
            verdict = f"{group['cpl'] / target:.1f}x target"
        elif group["cpl"] < target:
            verdict = "beating target"
        else:
            verdict = "acceptable"
        theme = group["campaign"].split("|")[-1].strip()[:19]
        print(f"{group['ad_group'][:25]:<26}{theme:<20}{group['cost']:>10,.0f}"
              f"{group['conversions']:>7,.0f}{group['cpl'] or 0:>9,.0f}   {verdict}")

    print(f"\nnever served, no impressions at all: {len(found['never_served'])} keywords")
    for k in found["never_served"][:8]:
        print(f"   {k['keyword']}")
    if len(found["never_served"]) > 8:
        print(f"   … and {len(found['never_served']) - 8} more")

    print(f"\nspent over {MIN_SPEND_TO_JUDGE:.0f} and booked nothing: "
          f"{len(found['spent_no_conv'])} keywords")
    for k in sorted(found["spent_no_conv"], key=lambda x: -x["cost"])[:8]:
        print(f"   {k['cost']:>8,.0f}   {k['keyword']}")

    if args.out:
        args.out.write_text(yaml.safe_dump({
            "target_cpl": args.target_cpl,
            "prune_keywords": sorted({k["keyword"] for k in found["never_served"]}),
            "review_keywords": sorted({k["keyword"] for k in found["spent_no_conv"]}),
            "dead_ad_groups": sorted({g["ad_group"] for g in found["dead_groups"]}),
            "weak_ad_groups": {g["ad_group"]: round(g["cpl"], 2) for g in found["weak_groups"]},
            "ad_group_performance": {
                g["ad_group"]: {"cost": round(g["cost"], 2), "conversions": g["conversions"],
                                "cpl": round(g["cpl"], 2) if g["cpl"] else None}
                for g in groups},
        }, sort_keys=False), encoding="utf-8")
        print(f"\nwrote {args.out}")

    if args.apply_to:
        apply_to_blueprint(args.apply_to, found, args.target_cpl)

    return 0


def apply_to_blueprint(path: Path, found: dict, target_cpl: float) -> None:
    """Delete from the template what the account proved does not work.

    Both accounts were built from the same agency template, so an ad group that
    never served in one is the same ad group in the other. Keeping it means
    every future client inherits the dead weight and pays to rediscover it.
    """
    import re

    blueprint = yaml.safe_load(path.read_text())

    def bare(text: str) -> str:
        """Compare ignoring the city, since the template is parameterised."""
        return re.sub(r"\s+", " ", re.sub(r"\{city\}", "", text or "").lower()).strip()

    never = {bare(k["keyword"]) for k in found["never_served"]}
    dead = {g["ad_group"].lower() for g in found["dead_groups"]}

    pruned_keywords = pruned_groups = 0
    for campaign in blueprint.get("campaigns", []):
        keep_groups = []
        for group in campaign.get("ad_groups", []):
            if bare(group.get("label", "")).lower() in dead:
                pruned_groups += 1
                continue
            before = group.get("keywords")
            if before:
                after = [k for k in before if bare(k) not in never]
                pruned_keywords += len(before) - len(after)
                if not after:
                    pruned_groups += 1
                    continue
                group["keywords"] = after
            keep_groups.append(group)
        campaign["ad_groups"] = keep_groups

    blueprint["pruned_by_performance"] = {
        "keywords_removed": pruned_keywords,
        "ad_groups_removed": pruned_groups,
        "reason": "never served, or spent without booking, in a live account",
    }
    path.write_text(yaml.safe_dump(blueprint, sort_keys=False, allow_unicode=True, width=110),
                    encoding="utf-8")
    print(f"\npruned {pruned_keywords} keyword(s) and {pruned_groups} ad group(s) "
          f"from {path.name} — they never served or never converted")


if __name__ == "__main__":
    raise SystemExit(main())
