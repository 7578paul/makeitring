# Corrected spec — from the playbook, then from the account

> **Update — the real account has now been read** (Editor export, 65,075 rows,
> 31 campaigns). Most of the playbook held up. Four things below are wrong and
> are corrected here rather than silently edited, because the difference between
> a document about an account and the account itself is the whole point.
>
> | Playbook said | The account actually does |
> | --- | --- |
> | Negatives live in a shared library list | They are **pasted per campaign** — 28,962 phrase negative rows for 947 distinct terms across 31 campaigns. The shared set exists but holds almost nothing. |
> | `utm_medium=paid&utm_keyword=...` | `{lpurl}?campaign={campaignid}&content={creative}&keyword={keyword}` — no `utm_` prefixes at all |
> | 5–15 keywords per ad group | Median **7**, so the rule holds for most — but the flagship *Local Moving* group carries **194**. The discipline is real; the hard cap is not. |
> | 600–700 universal negatives | **947** distinct, of which 895 are safely reusable |
>
> **And one thing the playbook never mentions, which matters more than any of
> the above:** the account's negative list contains **51 place names and its own
> brand**. Each market blocks the other markets' cities so campaigns do not
> cannibalise each other, and blocks "papa" so General Moving does not steal from
> Brand. Both are correct for *that* client and destructive for anyone else —
> copy the list to a Burlington client and you block them from the word
> "burlington". `extract_account.py` now quarantines these into
> `negatives-market-separation.txt` and `negatives-own-brand.txt`, which carry a
> do-not-copy header, and the builder regenerates the equivalents per client.
>
> Confirmed exactly as described: `Market | Search | Theme` naming, tCPA per
> theme (General Moving 75, Commercial & Office 85, Last-mile 85, Brand 30,
> PMax 31.25), Search-only networks, **Location of presence** targeting,
> postal-code geo (10,367 negative locations), DKI `{KeyWord:Moving Papa}` and
> `{LOCATION(City):Your Area}`, one RSA per ad group at Excellent strength, and
> a call asset on a tracking number distinct from the site's public one.



The v0 builder was written before the playbook existed. It guessed at structure
and guessed wrong in ways that would have cost money. This is the corrected
specification, and the v0 blueprint is now considered invalid rather than
provisional.

Source: *The Local Service Google Ads Playbook*, reverse-engineered from two
live accounts (moving: $1.34M spend, 19,403 leads @ $69 CPA; cleaning: launched
June 2026).

---

## What v0 got wrong

| # | v0 built | The account actually does | Cost of the mistake |
| --- | --- | --- | --- |
| 1 | 360–440 keywords, every term × pattern × city × match type | **5–15 phrase keywords per ad group**, one theme per ad group | The whole premise was wrong. Phrase match plus smart bidding finds the long tail; the negative wall filters it. A cartesian product splits data across hundreds of near-duplicates and starves every one of them. |
| 2 | Phrase **and** exact for every keyword | Phrase throughout, with **one** exact ad group per campaign for head terms | Doubles the keyword count for nothing and fragments the same query across two criteria. |
| 3 | ~45 universal negatives, written per campaign | **600–700** universal phrase negatives + **300–600** exact competitor negatives, in a **shared library list** | This is the moat and v0 barely has one. Writing them per campaign also means every new campaign starts naked instead of inheriting. |
| 4 | `Maximize conversions`, no target | **Maximize Conversions with tCPA set immediately**, ~10–15% of job value | Smart bidding with no target spends to the budget instead of to the number. |
| 5 | `MOV \| Search \| Local Moving \| EN` | `Market \| Channel \| Theme` — e.g. `Toronto \| Search \| Local Moving \| Core` | Market is the top-level axis, not trade. Trade is implied by the account. |
| 6 | One campaign, an ad group per city | **A campaign set per market**; GEO campaigns with one ad group per suburb come later, once core proves out | Wrong shape entirely. GEO campaigns were their **highest converting type at 31–33%** and v0 cannot express them. |
| 7 | No tracking template | `{lpurl}?utm_medium=paid&utm_keyword={keyword}&utm_campaign=[slug]` on every campaign | No attribution past the click. |
| 8 | Plain-text headlines | **DKI** `{KeyWord:Fallback}` and **location insertion** `{LOCATION(City)}` | Loses the relevance lift these give, and the pinned price anchor. |
| 9 | Nothing | Search Partners **off**, Display **off**, auto-created assets **off**, AI Max **off**, ad rotation **optimize**, all auto-apply recommendations **off** | Google's defaults are all on. Leaving them on is how budget leaks. |
| 10 | Nothing | Negative geo: every province/state not served | Pays for clicks from places they cannot serve. |

Two more the playbook settles that v0 never asked:

- **Conversion actions cannot be created in Editor.** They are UI or API only.
  The tool must emit a checklist for these, not pretend to build them.
- **Ad groups mirror the website's service nav.** One service page = one ad
  group. That is where the structure comes from — not from keyword research.

---

## The corrected structure

### Campaign set, per market, in build order

1. `{Market} | Search | {Core Service} | Core` — the revenue engine
2. `All Markets | Search | Brand` — one campaign across every market, low tCPA
3. Volume layer, once core is stable — PMax with city radius, or Demand Gen
   with channel control set to Maps only
4. `{Market} | Search | {Premium/B2B}` — higher tCPA, its own landing page
5. `{Market} | Search | {Core} | GEOs` — one ad group per suburb, added once
   core holds target

### Ad groups

- One per service, named for the service, mirroring the site nav
- 5–15 phrase-match keywords, formula: `[service term] × [modifier]` where
  modifier ∈ {near me, [city], companies, services, cost, quote, best}
- One exact-match ad group per campaign for head terms
- One RSA each

### The settings block, every campaign

| Setting | Value |
| --- | --- |
| Type | Search |
| Bidding | Maximize Conversions **with tCPA from day one** |
| tCPA | ~10–15% of average job value — cleaning $35, moving $75, commercial $85, brand $30 |
| Search Partners | Off |
| Display Network | Off |
| Automatically created assets | Off |
| AI Max | Off |
| Ad rotation | Optimize |
| Locations | City + named suburbs, postal-code level where it matters |
| Location option | **Presence only** |
| Negative locations | Every province/state not served, plus the bot-traffic exclusion template |
| Ad schedule | Answering hours only |
| Tracking template | `{lpurl}?utm_medium=paid&utm_keyword={keyword}&utm_campaign=[slug]` |
| Audiences | Observation mode only |
| Budget | Modest to start — $65/day cleaning, $120/day moving. Standard delivery. |
| Status | Paused until the whole set is built |

### Negatives — three layers, shared library

- **Layer 1** — universal junk, 600–700 phrase negatives. Built once, reused
  forever, pasted whole into every account.
- **Layer 2** — competitor brand wall, 300–600 exact negatives per market.
  Harvested by scraping Google Maps for every business in the category, plus
  national franchises, plus misspellings.
- **Layer 3** — mined weekly from the search terms report. Starts empty.

Layers 1 and 2 live in a **shared negative keyword list** applied to all
campaigns, so every future campaign inherits them instantly. Irrelevant
negatives from other markets cost nothing — do not prune them.

---

## Measurement — answering the questions raised

### Call tracking (CallRail / WhatConverts class)

Confirmed in the account: conversion source is `Import click`, category
`Contact`, with transaction-specific values, and the call asset uses a
**dedicated tracking number different from the site's public number**.

What it does that nothing else does:
- **Dynamic number insertion** on the site, so an organic visitor and a paid
  visitor see different numbers and the call is attributed correctly
- **A separate tracking number in the Google Ads call asset**
- **Defines what a lead is** — calls over 30–60 seconds, form fills, quote
  requests — and imports that back into Google Ads as the conversion

To find the exact vendor in the account: **Tools → Conversions → the "Leads"
conversion → Source**.

**The tracking numbers must be in the client's name.** Numbers on trucks, door
hangers or the Google Business Profile need porting, or call history is lost at
switchover.

### Conversion action settings, observed

Category `Contact` · Count `Every` · Click window `60 days` ·
Attribution `Data-driven` · **Primary**. Everything else demoted to secondary
or deleted, so smart bidding gets one clean signal.

### UTM / attribution

The tracking template goes on every campaign. `{keyword}` and the campaign slug
mean the CRM can answer which keyword produced which booked job — which is what
makes offline conversion import possible later.

### Lead delivery

Not covered by the playbook, but it belongs in onboarding and the brief must
capture it: where does a lead actually land? Options are the call-tracking
tool's own routing, a CRM webhook, or plain email. Whichever it is, it has to
carry the `gclid` and the UTM values through, or the loop from spend to booked
job stays broken.

### Landing pages

Purpose-built, not a WordPress theme. The formula observed:

- Quote form above the fold, plus a "Get a Call from Us" callback option
- Click-to-call in the header, number swapped by the call-tracking script
- Star rating and review count near the form
- Trust badges — licensed, insured, background checked
- "No surprises / upfront pricing" copy that **matches the ad copy**
- Named-crew reviews for social proof density
- **A separate page or subdomain for commercial**, so B2B ads land on B2B
  content (`commercial.movingpapa.com`)

### Click fraud

ClickCease, running from week 1–2 — 544,709 automated IP-block changes in the
moving account. In competitive local verticals the playbook puts the saving at
5–15% of budget. Worth keeping, but ask for the number it actually blocked.

---

## What the tool has to become

The v0 pipeline shape — brief + blueprint → plan → files — survives. What
changes is everything the blueprint can express:

1. **Market as the top-level axis**, with a campaign set per market
2. **Shared negative lists** as real objects, not per-campaign duplication
3. **The full settings block**, including tCPA, network toggles, tracking
   template and negative geo
4. **DKI and location insertion** in RSA templates
5. **Keyword discipline** — 5–15 per ad group, phrase, one exact ad group per
   campaign. A build producing 400 keywords should fail its own checks.
6. **A manual checklist** for what Editor cannot do: conversion actions, call
   assets with tracking numbers, auto-apply recommendations off
7. **Job values in the brief**, so tCPA is derived rather than typed

---

## What is needed to finish this properly

1. **The Google Ads Editor export of the live account.** Everything above is
   read from a document about the account; the export is the account. It
   settles the real campaign names, the real keyword counts per ad group, the
   real RSA copy, and the exact negative lists.
2. **The shared negative lists themselves** — `General Negatives - ALL
   CAMPAIGNS` and the competitor wall. These are the moat and cannot be
   reconstructed.
3. **Read access to the GTM container** `GTM-KHD5RLMK`, to enumerate what is
   actually firing.
4. **Average job value per service**, to derive tCPA rather than copy the
   playbook's numbers.
5. **Where leads should land** — CRM, webhook or email.
