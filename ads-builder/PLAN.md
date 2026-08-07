# Google Ads build automation — plan

**Goal.** From the moment a client hands over access to campaigns live, with the
human time spent on judgement rather than typing. Target: under two hours per
account, most of it review.

**Principle.** Everything a client gives us is a *variable*. Everything we know
about a trade is a *template*. "Different location, different budget, different
campaign count" are not exceptions to the process — they are inputs to it.

---

## Architecture

```
                        the expert's live account
                                  │
                          Editor export (CSV)
                                  │
                            extract.py            ← blueprint is DERIVED, not invented
                                  ▼
web form ─► brief ──┐      blueprint.yaml
                    ├──► compiler ──► Plan (IR) ──┬──► Editor CSV  ──► Editor ──► account
   brief.yaml ──────┘        │                    ├──► build sheet ──► human approval
                        validators                └──► Ads API     ──► account  (phase 3)
```

The loop at the top is the important part. The blueprint is not someone's
opinion about how a moving account should look — it is a proven account, run
through `extract.py`, with the client-specific strings swapped for placeholders.

The **Plan** in the middle is the reason phase 3 is cheap. Exporters read the
Plan and nothing else, so adding the API backend touches no blueprint, no brief
and no compiler logic.

### 1. Intake — `clients/<slug>/brief.yaml`
Every account-specific fact in one file: service area, budget, phone, hours,
positioning, landing pages, which services to advertise. Missing required fields
**fail the build** rather than defaulting — that is what gets briefs answered
properly the first time.

### 2. Blueprint — `blueprints/<trade>.yaml`
The trade template, versioned. Campaign skeleton, keyword vocabularies, keyword
patterns, RSA copy with placeholders, negative themes, budget weights, schedules,
bid strategy defaults. **This is the asset.** Everything else is plumbing.

### 3. Compiler — `src/compiler.py`
Merges the two. Geo expansion into keywords and copy, budget allocation,
per-city ad groups, cross-campaign negatives, dedupe, RSA rendering. No network,
no state — same inputs always produce the same plan, which is what makes
diffing a rebuild against a live account meaningful.

### 4. Validators — `src/validators.py`
`error` blocks export; `warning` needs eyes. Character limits, RSA asset counts,
keyword length/word caps, duplicate keywords across ad groups, missing negatives,
zero budgets, and a hard error if geo targeting is anything other than
**presence**. That last one is the most expensive default in the product and it
should be impossible to ship past by accident.

### 5. Exporters — `src/exporters.py`
- **`build-sheet.md`** — the human-readable review doc. This is what gets
  approved, not the CSV.
- **7 CSVs** — Google Ads Editor bulk import.

Everything imports **paused**. Going live is always a separate human act.

### 6. Measurement — see below.

### 7. Feedback loop
Weekly search-term pull → winners promoted to keywords, losers written back into
the blueprint's negative themes. Client #12 launches better than client #1 did.
Most agencies never build this; it is where the compounding is.

---

## Measurement stack

The previous agency called call tracking "critical". They were right about the
category and it is also where the lock-in lives. What is actually needed:

| Layer | Verdict | Notes |
| --- | --- | --- |
| Call tracking with recording | **Critical** | The whole value story ("6 of 9 calls after 5pm never got a quote") is unprovable without it. |
| `gclid` capture on every form | **Critical** | Without it you can never optimise to booked jobs, only to form fills. |
| Offline conversion import | **Critical** | The actual point. Upload "this lead became a $4,800 move" back to Google. |
| GA4 + key event import | **Needed** | Already specced in the website's `analytics/TAXONOMY.md`. |
| Google forwarding numbers | **Free, use it** | Built into call assets. Covers ad calls only — not organic. |
| GTM container | **Recommended** | Not critical, but makes every other tag swappable without touching the site. |
| Enhanced conversions for leads | **Worth it** | Hashed email/phone match; recovers conversions cookies lose. |
| Session recording (Hotjar/Clarity/Smartlook) | **Optional** | Useful for landing pages. Not part of attribution. |
| Meta pixel | **Optional** | Only if they run Meta. |

### What is actually on movingpapa.com

Confirmed from the page source:

| Tool | ID | Read |
| --- | --- | --- |
| Google Tag Manager | `GTM-KHD5RLMK` | The container. Almost everything else is inside it. |
| Meta Pixel | `1561438818562563` | Present. Only earns its place if Meta ads are running. |
| ClickCease | — | Click-fraud blocking. See below. |
| Google Maps embed | — | Not tracking. |

Stack is Next.js on Vercel. Every CTA points at **`/finalstep/residential`** — that
is the conversion endpoint, so ads should land in the funnel rather than on the
homepage. Secondary CTA is `tel:8333511791`.

**What is conspicuously absent from the markup:** no GA4 measurement ID, no
Google Ads conversion ID, no call-tracking snippet. Those are either inside the
GTM container or genuinely missing — and which one it is matters enormously.
**Getting into that GTM container is the highest-value next step on tracking.**
Enumerate its tags and you learn in ten minutes whether conversion tracking was
ever set up properly, and whose accounts everything points at.

**On ClickCease specifically:** it is the classic "critical tool" upsell. It is
not worthless — moving is a high-CPC vertical where competitor clicking is real
— but Google already credits invalid clicks automatically, and ClickCease's IP
blocking can and does exclude genuine customers. Ask for the number: how much
spend did it actually block last quarter, and what did it cost? If that question
has no answer, it was a line item, not a tool.

**Two rules, non-negotiable:**

1. **Every account is in the client's name and on the client's card** — including
   the call-tracking account and the tracking numbers. An agency that owns the
   numbers owns the client. Make It Ring already sells on the opposite of that
   ("Your name, your card"), so the tooling has to match the pitch.
2. **Ported numbers, not new ones.** If tracking numbers were issued by the old
   agency and appear on trucks, Google Business Profile or door hangers, they
   must be ported out or the client loses call history at switchover.

3. **Ads land in the funnel.** `/finalstep/residential` converts; the homepage
   asks the visitor to go find it. Campaign final URLs are set per campaign in
   the brief for exactly this reason.

---

## Decisions taken

| Question | Decision |
| --- | --- |
| Delivery | Editor CSV first, Ads API later as a second exporter |
| Home | Standalone repo (scaffolded here under `ads-builder/`, see README) |
| First trade | Moving |

---

## Roadmap

| Phase | Work | Status |
| --- | --- | --- |
| 0 | Brief schema, blueprint format, compiler, validators, CSV + build sheet | **done** |
| 0a | `extract.py` — turn an Editor export into a blueprint automatically | **done** |
| 0b | Local web UI (`app.py`) so a build is a form, not a YAML file | **done** |
| 0c | Run the real account through `extract.py`, replace the straw man | **blocked — needs the Editor export** |
| 0d | Verify Editor CSV column headers against that same export | **blocked — same export** |
| 0e | Enumerate the `GTM-KHD5RLMK` container's tags | **blocked — needs GTM access** |
| 1 | Backtest: rebuild a client we launched by hand, diff against what shipped | next |
| 2 | Pre-launch QA checklist + measurement runbook | after 1 |
| 3 | Ads API exporter, developer token, idempotent upsert | parallel |
| 4 | Search-term mining, negative feedback loop, blueprint versioning | ongoing |

### Phase 1 is the important one

Rebuild an account that was launched manually, then diff the output against what
actually shipped. Every difference is either a gap in the blueprint or something
done by instinct that was never written down. **That diff is the real spec** —
more valuable than any amount of further planning.

---

## What is needed to unblock

1. **Google Ads Editor export** of the best-performing moving account —
   campaigns, ad groups, keywords, ads, negatives. Unblocks 0b and 0c at once.
2. **movingpapa.com page source** — the script tags and `<noscript>` pixels.
3. **A launched client's brief facts** (budget, cities, services) to backtest
   phase 1 against.

## Open questions

1. **Is the conversion a form fill or a booked job?** The two optimise in
   opposite directions. Settle before any campaign has enough data to learn on.
2. **PMax and Demand Gen** — out of scope for v0, which is Search only. Worth
   deciding whether the blueprint should model them at all, since Editor's
   support for asset groups is weaker than for Search.
3. **Conversion actions cannot be created in Editor.** They are UI or API only,
   so account setup stays partly manual until phase 3.
4. **Shared negative lists** — currently negatives are written per campaign,
   which duplicates them. Shared library lists would be cleaner but are awkward
   to bulk-import. Revisit after the Editor export confirms what is possible.
