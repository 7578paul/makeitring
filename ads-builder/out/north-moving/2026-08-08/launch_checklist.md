# Launch checklist — North Moving

The campaign files cover what Google Ads Editor can import. These are the
steps it cannot, and skipping them is how an account ends up optimising
toward nothing. Work top to bottom.

## 1. Before anything goes live

- [ ] GTM container installed on https://northmoving.ca — **container ID still needed**
- [ ] GA4 property created and linked to Google Ads — **measurement ID still needed**
- [ ] Call tracking live, with dynamic number insertion on the site
- [ ] Tracking number is in **North Moving's** name, not the agency's
- [ ] If their current number is on trucks or the Google Business Profile, **port it** — do not replace it, or call history is lost

## 2. Conversions — Editor cannot do this part

Conversion actions are UI or API only. Create them by hand, in Google Ads:

- [ ] Create the "Leads" conversion — Category **Contact**, Count **Every**, click window **60 days**, attribution **Data-driven**, set **Primary**
- [ ] Demote or delete every other conversion, so smart bidding gets one clean signal
- [ ] Import the call-tracking lead definition (calls over 60 seconds) as a conversion
- [ ] Confirm a test lead appears in Google Ads before enabling anything

## 3. If the account already has campaigns

Skip this if the account is empty. Otherwise the old campaigns will bid
against the new ones for the same searches, and whichever wins, the client
pays twice to find out. Do not simply pause everything on day one — a hard
stop kills the lead flow while the new campaigns are still learning.

- [ ] Export the existing account from Editor first, and keep the file. It is the only record of what was there
- [ ] List the existing campaigns and what each one targets. Anything overlapping the new structure is the problem
- [ ] **Drop legacy budgets to a token amount** rather than pausing — traffic winds down instead of stopping dead
- [ ] Launch the new campaigns alongside them and let them gather data
- [ ] Once the new campaigns hold target CPA for a few days, **pause the legacy ones fully**
- [ ] Watch for name collisions: Editor **skips** a campaign whose name already exists rather than updating it. Rename the old one, or delete it, before importing
- [ ] Check the old campaigns' negative lists before deleting them — mined negatives are worth keeping

## 4. Turn Google's automation off

The source account did this **first, before building anything**:

- [ ] Settings → Recommendations → auto-apply: turn **all** of them off
- [ ] Confirm Search Partners and Display are off on every campaign
- [ ] Confirm auto-created assets and Final URL expansion are off

## 5. Import

- [ ] Google Ads Editor → Account → Import → From file → `campaigns_editor_import.csv`
- [ ] **Confirm the EU political ads declaration** — Google blocks posting until this is answered once per account. Settings → account-level policy, or the prompt Editor shows
- [ ] Review every campaign in Editor. **Do not post until it reads correctly**
- [ ] Post. Everything arrives paused
- [ ] Tools → Shared library → Negative keyword lists → import `shared_negative_list.csv`, attach to all campaigns
- [ ] Add the call asset using the **tracking** number, not 416-555-0188
- [ ] Add at least 3 image assets — Google marks a Search campaign down without them. Photos of real crews and trucks beat stock. Put their paths in the brief under `assets.images`, or add them in the Google Ads UI
- [ ] Check the ad schedule matches the hours someone actually answers

## 6. Landing page

- [ ] Deploy `site/` to **go.northmoving.ca**
- [ ] Ask the client to add one DNS record: `go.northmoving.ca` CNAME → your Pages project
- [ ] Load the page with `?gclid=test123` and confirm the hidden field appears
- [ ] Submit a test lead and confirm it arrives wherever leads go
- [ ] Confirm the thank-you page fires the conversion

## 7. Going live, and the first fortnight

- [ ] Enable campaigns one at a time, starting with the core market
- [ ] Read the search terms report **daily** for the first 14 days
- [ ] Add junk patterns as phrase negatives, competitor names as exact
- [ ] Install click-fraud protection, and ask what it actually blocked after a month
- [ ] Scale budget in steps of 20% or less, only once CPA holds
- [ ] Never change target CPA and budget on the same day

## What the first three months actually look like

From a live account's own conversion history, so nobody panics in week two:

- **Weeks 1-2: zero.** Not a problem. Smart bidding is still learning and there is not enough conversion data to bid on.
- **Weeks 3-6:** first leads, 1-5 a day, erratic. Do not touch the budget yet.
- **Weeks 7-10:** 3-9 a day and steadier. This is where target CPA starts holding.
- **Weeks 11+:** 12-20 a day on a mature account.

The account this is modelled on reached roughly $94 per lead on Search. Its
Performance Max campaign reached $39 for the same period — worth knowing
before judging Search on its own.

## Warnings you should ignore

Google will show these after import. They are it selling against the
strategy, not faults in the build — every one is a deliberate choice:

- **"Search Partners disabled. Enable it to reach more customers."** Off on purpose. Search Partners is a different, worse audience.
- **"Display Network expansion disabled."** Off on purpose. It spends search budget on display placements that do not book jobs.
- **"You don't have conversion tracking enabled."** Correct for now — section 2 above is how it gets fixed. Do not enable campaigns until it is.

The one real blocker is the EU political ads declaration, which Google
requires once per account before anything can be posted.

---

Generated for North Moving. 5 campaigns, 340.63 CAD/day. Campaigns paused, ad groups enabled — so going live is one switch per campaign.
