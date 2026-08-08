#!/usr/bin/env python3
"""Compile a client brief into an importable Google Ads build.

    python build.py clients/example-mover/brief.yaml

Writes to out/<slug>/<date>/. Exits non-zero on validation errors and writes no
CSV, so a broken build cannot be posted by accident. `--force` overrides that
for inspection; it does not make the build safe to import.
"""

import argparse
import sys
from datetime import date
from pathlib import Path

from src.competitors import api_key_from_env, build_layer2
from src.compiler import BriefError, compile_plan, load_yaml
from src.landing import write_site
from src.model import NegativeKeyword
from src.package import write_checklist, write_summary
from src.editor_export import write_editor_file, write_shared_negatives
from src.exporters import export_build_sheet, export_editor_csv
from src.preflight import check as preflight_check, load_negatives, resolve as preflight_resolve
from src.validators import has_errors, validate

ROOT = Path(__file__).parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief", type=Path, help="path to a client brief.yaml")
    parser.add_argument("--out", type=Path, default=None, help="output directory")
    parser.add_argument("--force", action="store_true", help="export despite errors")
    args = parser.parse_args()

    try:
        plan = compile_plan(args.brief, ROOT / "blueprints")
    except BriefError as exc:
        print(f"brief error: {exc}", file=sys.stderr)
        return 2

    findings = validate(plan)

    # Never trust an inherited negative list. Test it against the keywords this
    # build is actually about to create, drop whatever would block the client,
    # and say so — an inherited list always carries some terms that are wrong
    # for a new client, so this is routine rather than exceptional.
    brief = load_yaml(args.brief)
    brand_terms = brief.get("positioning", {}).get("brand_terms") or []
    cities = brief.get("service_area", {}).get("cities") or []
    keywords = [(c.name, g.name, k.text)
                for c in plan.campaigns for g in c.ad_groups for k in g.keywords]

    negatives = load_negatives(*(ROOT / "blueprints" / "_shared" / name for name in (
        "negatives-universal.txt", "negatives-competitors.txt")))
    kept, removed = preflight_resolve(negatives, keywords=keywords,
                                      brand_terms=brand_terms, cities=cities)
    if removed:
        print(f"\nremoved {len(removed)} negative(s) that would have blocked this client:",
              file=sys.stderr)
        for line in removed[:12]:
            print(f"   {line}", file=sys.stderr)
        if len(removed) > 12:
            print(f"   ... and {len(removed) - 12} more", file=sys.stderr)

    for conflict in preflight_check(keywords=keywords, negatives=kept,
                                    brand_terms=brand_terms, cities=cities):
        print(conflict, file=sys.stderr)

    out_dir = args.out or ROOT / "out" / plan.client_slug / date.today().isoformat()

    sheet = export_build_sheet(plan, findings, out_dir)

    for finding in findings:
        print(finding, file=sys.stderr)

    print(
        f"\n{plan.business_name}: {len(plan.campaigns)} campaigns, "
        f"{sum(len(c.ad_groups) for c in plan.campaigns)} ad groups, "
        f"{sum(c.keyword_count for c in plan.campaigns)} keywords, "
        f"{plan.daily_budget_total:,.2f} {plan.currency}/day"
    )
    print(f"build sheet: {sheet}")

    if has_errors(findings) and not args.force:
        print("\nerrors present — no CSV written. Fix, or re-run with --force.", file=sys.stderr)
        return 1

    # The competitor wall has to be built BEFORE the files are written,
    # or it is added to a plan that has already been exported.
    # Layer 2: the competitor wall for THIS market. An inherited one is worth
    # nothing here — a Toronto list contains no Miami movers.
    names_file = args.brief.parent / "competitor-names.txt"
    layer2 = build_layer2(
        cities=cities,
        service_terms=brief.get("landing", {}).get("services") or ["movers"],
        client_keywords=[k for _c, _g, k in keywords],
        brand_terms=brand_terms,
        api_key=api_key_from_env(),
        names_file=names_file,
    )
    if layer2["negatives"]:
        for campaign in plan.campaigns:
            campaign.negatives.extend(
                NegativeKeyword(t, "exact", source="competitor") for t in layer2["negatives"])
        print(f"\ncompetitor wall: {len(layer2['negatives'])} exact negatives "
              f"from {layer2['source']}", file=sys.stderr)
    for problem in layer2["problems"]:
        print(f"   competitor source: {problem}", file=sys.stderr)
    for line in layer2["rejected"][:6]:
        print(f"   rejected {line}", file=sys.stderr)

    for path in export_editor_csv(plan, out_dir):
        print(f"  {path}")
    print(f"  {write_editor_file(plan, out_dir, ROOT / 'data')}   <- import this one")

    print(f"  {write_shared_negatives(plan, out_dir)}")

    for path in write_site(brief, out_dir / "site"):
        print(f"  {path}")
    print(f"  {write_summary(plan, out_dir, layer2=layer2, removed_negatives=removed)}")
    print(f"  {write_checklist(plan, brief, out_dir)}")

    print("\nNext: import into Google Ads Editor, review, post. Everything lands paused.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
