"""Plan -> files a human posts.

Two outputs, both mandatory:

  * `build-sheet.md`  — what a person reads and approves before anything moves.
  * `*.csv`           — what Google Ads Editor imports.

IMPORTANT — column names are provisional.
Google Ads Editor's import matches on exact header text, and the headers vary by
Editor version and account language. They are all defined in COLUMNS below and
nowhere else, so Phase 0 fixes them in one place: export any existing campaign
from the live account via Editor, diff its headers against COLUMNS, correct.
Until that diff is done, expect the first import to need a mapping pass.
"""

import csv
from pathlib import Path

from .model import RSA_MAX_DESCRIPTIONS, RSA_MAX_HEADLINES, Plan

COLUMNS = {
    "campaign": "Campaign",
    "campaign_type": "Campaign Type",
    "budget": "Budget",
    "bid_strategy": "Bid Strategy Type",
    "max_cpc": "Max CPC",
    "networks": "Networks",
    "language": "Languages",
    "campaign_status": "Campaign Status",
    "ad_group": "Ad Group",
    "ad_group_status": "Ad Group Status",
    "keyword": "Keyword",
    "criterion_type": "Criterion Type",
    "status": "Status",
    "final_url": "Final URL",
    "location": "Location",
    "ad_schedule": "Ad Schedule",
    "ad_type": "Ad type",
    "path1": "Path 1",
    "path2": "Path 2",
}

MATCH_TYPE_LABELS = {"broad": "Broad", "phrase": "Phrase", "exact": "Exact"}
NEGATIVE_LABELS = {
    "broad": "Campaign Negative Broad",
    "phrase": "Campaign Negative Phrase",
    "exact": "Campaign Negative Exact",
}


def _write(path: Path, headers: list[str], rows: list[dict]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def export_editor_csv(plan: Plan, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    c = COLUMNS
    written: list[Path] = []

    written.append(
        _write(
            out_dir / "01-campaigns.csv",
            [c["campaign"], c["campaign_type"], c["budget"], c["bid_strategy"],
             c["networks"], c["language"], c["campaign_status"]],
            [
                {
                    c["campaign"]: camp.name,
                    c["campaign_type"]: camp.campaign_type,
                    c["budget"]: f"{camp.daily_budget:.2f}",
                    c["bid_strategy"]: camp.bid_strategy,
                    c["networks"]: camp.networks,
                    c["language"]: camp.language,
                    c["campaign_status"]: camp.status,
                }
                for camp in plan.campaigns
            ],
        )
    )

    written.append(
        _write(
            out_dir / "02-locations.csv",
            [c["campaign"], c["location"], c["criterion_type"]],
            [
                {c["campaign"]: camp.name, c["location"]: loc, c["criterion_type"]: kind}
                for camp in plan.campaigns
                for kind, locations in (
                    ("Location", camp.locations),
                    ("Excluded Location", camp.excluded_locations),
                )
                for loc in locations
            ],
        )
    )

    written.append(
        _write(
            out_dir / "03-schedules.csv",
            [c["campaign"], c["ad_schedule"]],
            [
                {c["campaign"]: camp.name, c["ad_schedule"]: f"{s.day}, {s.start}, {s.end}"}
                for camp in plan.campaigns
                for s in camp.schedule
            ],
        )
    )

    written.append(
        _write(
            out_dir / "04-campaign-negatives.csv",
            [c["campaign"], c["keyword"], c["criterion_type"]],
            [
                {
                    c["campaign"]: camp.name,
                    c["keyword"]: neg.text,
                    c["criterion_type"]: NEGATIVE_LABELS.get(neg.match_type, "Campaign Negative Phrase"),
                }
                for camp in plan.campaigns
                for neg in camp.negatives
            ],
        )
    )

    written.append(
        _write(
            out_dir / "05-ad-groups.csv",
            [c["campaign"], c["ad_group"], c["max_cpc"], c["ad_group_status"]],
            [
                {
                    c["campaign"]: camp.name,
                    c["ad_group"]: group.name,
                    c["max_cpc"]: f"{group.max_cpc:.2f}" if group.max_cpc else "",
                    c["ad_group_status"]: group.status,
                }
                for camp in plan.campaigns
                for group in camp.ad_groups
            ],
        )
    )

    written.append(
        _write(
            out_dir / "06-keywords.csv",
            [c["campaign"], c["ad_group"], c["keyword"], c["criterion_type"],
             c["status"], c["final_url"]],
            [
                {
                    c["campaign"]: camp.name,
                    c["ad_group"]: group.name,
                    c["keyword"]: kw.text,
                    c["criterion_type"]: MATCH_TYPE_LABELS.get(kw.match_type, "Phrase"),
                    c["status"]: group.status,
                    c["final_url"]: kw.final_url or "",
                }
                for camp in plan.campaigns
                for group in camp.ad_groups
                for kw in group.keywords
            ],
        )
    )

    headline_cols = [f"Headline {i}" for i in range(1, RSA_MAX_HEADLINES + 1)]
    description_cols = [f"Description {i}" for i in range(1, RSA_MAX_DESCRIPTIONS + 1)]
    ad_rows = []
    for camp in plan.campaigns:
        for group in camp.ad_groups:
            for ad in group.ads:
                row = {
                    c["campaign"]: camp.name,
                    c["ad_group"]: group.name,
                    c["ad_type"]: "Responsive search ad",
                    c["final_url"]: ad.final_url,
                    c["path1"]: ad.path1,
                    c["path2"]: ad.path2,
                    c["status"]: group.status,
                }
                row.update(dict(zip(headline_cols, ad.headlines)))
                row.update(dict(zip(description_cols, ad.descriptions)))
                ad_rows.append(row)

    written.append(
        _write(
            out_dir / "07-ads-rsa.csv",
            [c["campaign"], c["ad_group"], c["ad_type"], *headline_cols, *description_cols,
             c["path1"], c["path2"], c["final_url"], c["status"]],
            ad_rows,
        )
    )

    return written


def export_build_sheet(plan: Plan, findings, out_dir: Path) -> Path:
    """The human-readable review document. This is what gets approved, not the CSV."""
    out_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []

    lines.append(f"# Build sheet — {plan.business_name}")
    lines.append("")
    lines.append(f"- **Trade** {plan.trade} (blueprint v{plan.blueprint_version})")
    lines.append(f"- **Budget** {plan.monthly_budget:,.0f} {plan.currency}/month "
                 f"({plan.daily_budget_total:,.2f}/day across {len(plan.campaigns)} campaigns)")
    lines.append(f"- **Campaigns** {len(plan.campaigns)} · "
                 f"**Ad groups** {sum(len(c.ad_groups) for c in plan.campaigns)} · "
                 f"**Keywords** {sum(c.keyword_count for c in plan.campaigns)}")
    lines.append("- **Status** everything imports paused. Going live is a separate, human step.")
    lines.append("")

    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]

    lines.append(f"## Checks — {len(errors)} error(s), {len(warnings)} warning(s)")
    lines.append("")
    if not findings:
        lines.append("Clean.")
    for finding in errors + warnings:
        lines.append(f"- `{finding.severity}` **{finding.where}** — {finding.message}")
    lines.append("")

    lines.append("## Budget split")
    lines.append("")
    lines.append("| Campaign | Daily | Monthly | Share |")
    lines.append("| --- | ---: | ---: | ---: |")
    total = plan.daily_budget_total or 1
    for camp in plan.campaigns:
        # Campaign names contain `|` by convention, which is also the table
        # delimiter. Escape it or the whole row collapses.
        lines.append(
            f"| {camp.name.replace('|', chr(92) + '|')} | {camp.daily_budget:,.2f} "
            f"| {camp.daily_budget * 30.4:,.0f} | {camp.daily_budget / total * 100:.0f}% |"
        )
    lines.append("")

    for camp in plan.campaigns:
        lines.append(f"## {camp.name}")
        lines.append("")
        lines.append(f"- Bid strategy: {camp.bid_strategy}"
                     + (f" (max CPC {camp.max_cpc:.2f})" if camp.max_cpc else ""))
        lines.append(f"- Geo: {', '.join(camp.locations)} — **{camp.location_target_type}**")
        if camp.excluded_locations:
            lines.append(f"- Excluded: {', '.join(camp.excluded_locations)}")
        lines.append(f"- Schedule: {_schedule_summary(camp.schedule)}")
        lines.append(f"- Campaign negatives: {len(camp.negatives)}")
        lines.append("")

        for group in camp.ad_groups:
            lines.append(f"### {group.name}")
            lines.append("")
            lines.append(f"{len(group.keywords)} keywords")
            lines.append("")
            lines.append("```")
            for kw in group.keywords[:20]:
                lines.append(f"  {_display_keyword(kw)}")
            if len(group.keywords) > 20:
                lines.append(f"  … {len(group.keywords) - 20} more")
            lines.append("```")
            lines.append("")
            for ad in group.ads:
                lines.append(f"**Ad** → {ad.final_url}"
                             + (f" /{ad.path1}" if ad.path1 else "")
                             + (f"/{ad.path2}" if ad.path2 else ""))
                lines.append("")
                for headline in ad.headlines:
                    lines.append(f"- `{len(headline):2}` {headline}")
                lines.append("")
                for description in ad.descriptions:
                    lines.append(f"- `{len(description):2}` {description}")
                lines.append("")

    path = out_dir / "build-sheet.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _display_keyword(keyword) -> str:
    if keyword.match_type == "exact":
        return f"[{keyword.text}]"
    if keyword.match_type == "phrase":
        return f'"{keyword.text}"'
    return keyword.text


def _schedule_summary(slots) -> str:
    if not slots:
        return "all hours"
    grouped: dict[tuple[str, str], list[str]] = {}
    for slot in slots:
        grouped.setdefault((slot.start, slot.end), []).append(slot.day[:3])
    return "; ".join(f"{'/'.join(days)} {start}-{end}" for (start, end), days in grouped.items())
