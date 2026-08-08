# Deterministic generation rules

## Target CPA
OBSERVED (not a stated rule — inferred from real accounts; treat as default, user-overridable):
- Moving, general consumer service: tCPA $75 (blended actual CPA achieved: $69)
- Commercial / B2B variant: tCPA $85
- Brand campaign: tCPA $30 (~40-45% of core)
- Carpet cleaning (lower job value): tCPA $35
Derived default rule: `tCPA = round(avg_job_value * 0.12)`, floor $15, ceiling $150.
Brand tCPA = round(core_tCPA * 0.45).
ALWAYS display computed value in UI and allow override.

## Starting daily budget (observed)
- Toronto moving core campaign launched at CA$120/day, scaled to $2,200/day over ~18 months
- Cleaning core campaign launched at $65/day; secondary (Demand Gen/Maps) $35/day
Default rule: starting_daily_budget = max(3 * tCPA, 50). User-overridable. Scale in <=20% steps.

## Keyword formula
For each ad group: [service term] x {near me, <city>, companies, services, cost, quote, best}
- Match type: Phrase for all
- One "<Service> - EXACT" ad group per core campaign with head terms in Exact
- GEO ad groups: "<service> <suburb>", "<service> company <suburb>", "<suburb> <service>"
- 5-15 keywords per ad group. Do NOT build long-tail lists — phrase match + negatives handle it.

## Campaign naming
`<City> | Search | <Theme>`; GEO variant: `<City> | Search | <Theme> | GEOs`; brand: `All Markets | Search | Brand`
Ad group naming: service name; GEO ad groups: `<Service> - <Suburb>`

## Match type rules for negatives
- Competitor brand names -> Exact
- Intent patterns (how to, jobs, rental) -> Phrase
- Single unambiguous words (job, rental) -> Broad, sparingly
