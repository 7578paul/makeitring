"""The complete client package.

One command, one folder, everything needed to take a client live:

    campaigns_editor_import.csv   the Editor import (UTF-16, tab, 312 columns)
    shared_negative_list.csv      Layers 1 + 2 of the negative wall
    site/                         landing page + thank-you, tracking installed
    launch_checklist.md           the steps no file can do for you
    summary.md                    what was built, to read before importing
    build-sheet.md                every keyword and ad, in full

The checklist is the honest half of this. Conversion actions cannot be created
by an Editor import — they are UI or API only — and neither can turning off
auto-apply recommendations, which the source account did first, before
anything else. Generating campaigns and staying quiet about those would leave
a client optimising toward nothing.
"""

from pathlib import Path

from .model import Plan


def write_summary(plan: Plan, out_dir: Path, *, layer2: dict | None = None,
                  removed_negatives: list[str] | None = None) -> Path:
    groups = sum(len(c.ad_groups) for c in plan.campaigns)
    keywords = sum(c.keyword_count for c in plan.campaigns)
    negatives = len({(n.text, n.match_type) for c in plan.campaigns for n in c.negatives})

    lines = [
        f"# {plan.business_name} — what was built",
        "",
        f"- **{len(plan.campaigns)} campaigns**, {groups} ad groups, {keywords} keywords",
        f"- **{negatives:,} distinct negatives** across the wall",
        f"- **{plan.daily_budget_total:,.2f} {plan.currency}/day** "
        f"({plan.daily_budget_total * 30.4:,.0f}/month)",
        f"- Blueprint `{plan.blueprint_version}` — derived from a live account, not written by hand",
        "",
        "Everything imports **paused**. Nothing spends until a human enables it.",
        "",
        "## Campaigns",
        "",
        "| Campaign | Daily | Target CPA | Ad groups | Keywords |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for c in plan.campaigns:
        lines.append(
            f"| {c.name.replace('|', chr(92) + '|')} | {c.daily_budget:,.2f} "
            f"| {c.target_cpa or '—'} | {len(c.ad_groups)} | {c.keyword_count} |"
        )

    if layer2:
        lines += ["", "## Competitor wall (Layer 2)", "",
                  f"Source: {layer2.get('source', 'none')} · "
                  f"{len(layer2.get('names', []))} businesses found · "
                  f"**{len(layer2.get('negatives', []))} exact negatives**"]
        if layer2.get("rejected"):
            lines += ["", "Rejected, because they would have cost the client traffic:", ""]
            lines += [f"- {r}" for r in layer2["rejected"][:15]]
        if layer2.get("problems"):
            lines += ["", "Problems:", ""] + [f"- {p}" for p in layer2["problems"][:8]]

    if removed_negatives:
        lines += ["", "## Negatives removed for this client", "",
                  "Inherited lists carry the previous client's cities and brand. "
                  "These were dropped because they would have blocked this one:", ""]
        lines += [f"- {r}" for r in removed_negatives[:20]]

    path = out_dir / "summary.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_checklist(plan: Plan, brief: dict, out_dir: Path) -> Path:
    client = brief.get("client", {})
    name = client.get("business_name", "the client")
    website = client.get("website", "their website")
    phone = client.get("phone", "")
    tracking = brief.get("tracking", {})
    subdomain = brief.get("landing", {}).get("subdomain", f"go.{website}")

    def box(done: bool, text: str) -> str:
        return f"- [{'x' if done else ' '}] {text}"

    lines = [
        f"# Launch checklist — {name}",
        "",
        "The campaign files cover what Google Ads Editor can import. These are the",
        "steps it cannot, and skipping them is how an account ends up optimising",
        "toward nothing. Work top to bottom.",
        "",
        "## 1. Before anything goes live",
        "",
        box(bool(tracking.get("gtm_container")),
            f"GTM container installed on {website}"
            + (f" — `{tracking['gtm_container']}`" if tracking.get("gtm_container") else
               " — **container ID still needed**")),
        box(bool(tracking.get("ga4_measurement_id")),
            "GA4 property created and linked to Google Ads"
            + (f" — `{tracking['ga4_measurement_id']}`" if tracking.get("ga4_measurement_id") else
               " — **measurement ID still needed**")),
        box(bool(tracking.get("callrail_swap_script")),
            "Call tracking live, with dynamic number insertion on the site"),
        box(False, f"Tracking number is in **{name}'s** name, not the agency's"),
        box(False, "If their current number is on trucks or the Google Business Profile, "
                   "**port it** — do not replace it, or call history is lost"),
        "",
        "## 2. Conversions — Editor cannot do this part",
        "",
        "Conversion actions are UI or API only. Create them by hand, in Google Ads:",
        "",
        box(False, 'Create the "Leads" conversion — Category **Contact**, Count **Every**, '
                   "click window **60 days**, attribution **Data-driven**, set **Primary**"),
        box(False, "Demote or delete every other conversion, so smart bidding gets one clean signal"),
        box(False, "Import the call-tracking lead definition (calls over 60 seconds) as a conversion"),
        box(False, "Confirm a test lead appears in Google Ads before enabling anything"),
        "",
        "## 3. Turn Google's automation off",
        "",
        "The source account did this **first, before building anything**:",
        "",
        box(False, "Settings → Recommendations → auto-apply: turn **all** of them off"),
        box(False, "Confirm Search Partners and Display are off on every campaign"),
        box(False, "Confirm auto-created assets and Final URL expansion are off"),
        "",
        "## 4. Import",
        "",
        box(False, "Google Ads Editor → Account → Import → From file → "
                   "`campaigns_editor_import.csv`"),
        box(False, "Review every campaign in Editor. **Do not post until it reads correctly**"),
        box(False, "Post. Everything arrives paused"),
        box(False, "Tools → Shared library → Negative keyword lists → import "
                   "`shared_negative_list.csv`, attach to all campaigns"),
        box(False, f"Add the call asset using the **tracking** number, not {phone or 'the public number'}"),
        box(False, "Check the ad schedule matches the hours someone actually answers"),
        "",
        "## 5. Landing page",
        "",
        box(False, f"Deploy `site/` to **{subdomain}**"),
        box(False, f"Ask the client to add one DNS record: `{subdomain}` CNAME → your Pages project"),
        box(False, "Load the page with `?gclid=test123` and confirm the hidden field appears"),
        box(False, "Submit a test lead and confirm it arrives wherever leads go"),
        box(False, "Confirm the thank-you page fires the conversion"),
        "",
        "## 6. Going live, and the first fortnight",
        "",
        box(False, "Enable campaigns one at a time, starting with the core market"),
        box(False, "Read the search terms report **daily** for the first 14 days"),
        box(False, "Add junk patterns as phrase negatives, competitor names as exact"),
        box(False, "Install click-fraud protection, and ask what it actually blocked after a month"),
        box(False, "Scale budget in steps of 20% or less, only once CPA holds"),
        box(False, "Never change target CPA and budget on the same day"),
        "",
        "---",
        "",
        f"Generated for {name}. {len(plan.campaigns)} campaigns, "
        f"{plan.daily_budget_total:,.2f} {plan.currency}/day, all paused.",
    ]

    path = out_dir / "launch_checklist.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
