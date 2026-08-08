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

    by_layer = {}
    for c in plan.campaigns:
        for n in c.negatives:
            key = (n.text.lower(), n.match_type)
            by_layer.setdefault(n.source or "other", set()).add(key)
    if by_layer:
        lines += ["", "## Negative wall by layer", "",
                  "| Layer | Match | Distinct terms |", "| --- | --- | ---: |"]
        label = {"universal": "1 — junk / DIY / informational", 
                 "competitor-wall": "2 — competitor brands (mined from real spend)",
                 "excluded-service": "3 — services the client refuses",
                 "extracted": "campaign routing (from the source account)"}
        for src, terms in sorted(by_layer.items()):
            match = "/".join(sorted({m for _, m in terms}))
            lines.append(f"| {label.get(src, src)} | {match} | {len(terms)} |")

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
        "## 3. If the account already has campaigns",
        "",
        "Skip this if the account is empty. Otherwise the old campaigns will bid",
        "against the new ones for the same searches, and whichever wins, the client",
        "pays twice to find out. Do not simply pause everything on day one — a hard",
        "stop kills the lead flow while the new campaigns are still learning.",
        "",
        box(False, "Export the existing account from Editor first, and keep the file. "
                   "It is the only record of what was there"),
        box(False, "List the existing campaigns and what each one targets. Anything "
                   "overlapping the new structure is the problem"),
        box(False, "**Drop legacy budgets to a token amount** rather than pausing — "
                   "traffic winds down instead of stopping dead"),
        box(False, "Launch the new campaigns alongside them and let them gather data"),
        box(False, "Once the new campaigns hold target CPA for a few days, **pause the "
                   "legacy ones fully**"),
        box(False, "Watch for name collisions: Editor **skips** a campaign whose name "
                   "already exists rather than updating it. Rename the old one, or "
                   "delete it, before importing"),
        box(False, "Check the old campaigns' negative lists before deleting them — "
                   "mined negatives are worth keeping"),
        "",
        "## 4. Turn Google's automation off",
        "",
        "The source account did this **first, before building anything**:",
        "",
        box(False, "Settings → Recommendations → auto-apply: turn **all** of them off"),
        box(False, "Confirm Search Partners and Display are off on every campaign"),
        box(False, "Confirm auto-created assets and Final URL expansion are off"),
        "",
        "## 5. Import",
        "",
        box(False, "Google Ads Editor → Account → Import → From file → "
                   "`campaigns_editor_import.csv`"),
        box(False, "**Confirm the EU political ads declaration** — Google blocks posting "
                   "until this is answered once per account. Settings → account-level "
                   "policy, or the prompt Editor shows"),
        box(False, "Review every campaign in Editor. **Do not post until it reads correctly**"),
        box(False, "Post. Everything arrives paused"),
        box(False, "Optional: the negative wall is already in the import, applied per "
                   "campaign. `shared_negative_list.csv` is the same wall as one file if "
                   "you later prefer to manage it as a shared library list"),
        box(False, "Add the call asset once the **tracking** number exists — the import "
                   "ships without one on purpose, so the public number never ends up "
                   "in ads unattributable"),
        box(False, "Performance Max: add marketing images (landscape, square, portrait) "
                   "and a logo to each asset group — images cannot ship in a CSV, and "
                   "the asset group will not serve without them"),
        box(bool((brief.get("assets", {}) or {}).get("images")),
            "Add at least 3 image assets — Google marks a Search campaign down without them. "
            "Photos of real crews and trucks beat stock. Put their paths in the brief under "
            "`assets.images`, or add them in the Google Ads UI"),
        box(False, "Check the ad schedule matches the hours someone actually answers"),
        "",
        "## 6. Landing page",
        "",
        box(False, f"Ad URLs currently point at the client's own site. If you deploy "
                   f"`site/` to **{subdomain}**, update the campaigns' Final URLs to "
                   f"match — one destination, everywhere"),
        box(False, f"Deploy `site/` to **{subdomain}**"),
        box(False, f"Ask the client to add one DNS record: `{subdomain}` CNAME → your Pages project"),
        box(False, "Load the page with `?gclid=test123` and confirm the hidden field appears"),
        box(False, "Submit a test lead and confirm it arrives wherever leads go"),
        box(False, "Confirm the thank-you page fires the conversion"),
        "",
        "## 7. Going live, and the first fortnight",
        "",
        box(False, "Enable campaigns one at a time, starting with the core market"),
        box(False, "Read the search terms report **daily** for the first 14 days"),
        box(False, "Add junk patterns as phrase negatives, competitor names as exact"),
        box(False, "Install click-fraud protection, and ask what it actually blocked after a month"),
        box(False, "Scale budget in steps of 20% or less, only once CPA holds"),
        box(False, "Never change target CPA and budget on the same day"),
        "",
        "## What the first three months actually look like",
        "",
        "From a live account's own conversion history, so nobody panics in week two:",
        "",
        "- **Weeks 1-2: zero.** Not a problem. Smart bidding is still learning and "
        "there is not enough conversion data to bid on.",
        "- **Weeks 3-6:** first leads, 1-5 a day, erratic. Do not touch the budget yet.",
        "- **Weeks 7-10:** 3-9 a day and steadier. This is where target CPA starts "
        "holding.",
        "- **Weeks 11+:** 12-20 a day on a mature account.",
        "",
        "The account this is modelled on reached roughly $94 per lead on Search. Its",
        "Performance Max campaign reached $39 for the same period — worth knowing",
        "before judging Search on its own.",
        "",
        "## Warnings you should ignore",
        "",
        "Google will show these after import. They are it selling against the",
        "strategy, not faults in the build — every one is a deliberate choice:",
        "",
        "- **\"Search Partners disabled. Enable it to reach more customers.\"** "
        "Off on purpose. Search Partners is a different, worse audience.",
        "- **\"Display Network expansion disabled.\"** Off on purpose. It spends "
        "search budget on display placements that do not book jobs.",
        "- **\"You don't have conversion tracking enabled.\"** Correct for now — "
        "section 2 above is how it gets fixed. Do not enable campaigns until it is.",
        "",
        "The one real blocker is the EU political ads declaration, which Google",
        "requires once per account before anything can be posted.",
        "",
        "---",
        "",
        f"Generated for {name}. {len(plan.campaigns)} campaigns, "
        f"{plan.daily_budget_total:,.2f} {plan.currency}/day. Campaigns paused, "
        f"ad groups enabled — so going live is one switch per campaign.",
    ]

    path = out_dir / "launch_checklist.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
