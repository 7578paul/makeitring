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

from src.compiler import BriefError, compile_plan, load_yaml
from src.editor_export import write_editor_file, write_shared_negatives
from src.exporters import export_build_sheet, export_editor_csv
from src.preflight import check as preflight_check, errors as preflight_errors, load_negatives
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
    # build is actually about to create, before a single file is written.
    brief = load_yaml(args.brief)
    conflicts = preflight_check(
        keywords=[(c.name, g.name, k.text)
                  for c in plan.campaigns for g in c.ad_groups for k in g.keywords],
        # Only the lists actually destined for the account. The quarantined
        # files (market-separation, own-brand, campaign-routing) are evidence of
        # the source account's technique, not negatives to apply — globbing them
        # in would report conflicts against terms we were never going to use.
        negatives=load_negatives(
            *(ROOT / "blueprints" / "_shared" / name for name in (
                "negatives-universal.txt", "negatives-competitors.txt"))),
        brand_terms=brief.get("positioning", {}).get("brand_terms") or [],
        cities=brief.get("service_area", {}).get("cities") or [],
    )
    for conflict in conflicts:
        print(conflict, file=sys.stderr)
    if preflight_errors(conflicts) and not args.force:
        print(f"\n{len(preflight_errors(conflicts))} negative-list conflict(s) — "
              f"nothing written. These block the client's own traffic.", file=sys.stderr)
        return 3

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

    for path in export_editor_csv(plan, out_dir):
        print(f"  {path}")
    print(f"  {write_editor_file(plan, out_dir, ROOT / 'data')}   <- import this one")
    print(f"  {write_shared_negatives(plan, out_dir)}")

    print("\nNext: import into Google Ads Editor, review, post. Everything lands paused.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
