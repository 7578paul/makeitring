# Analytics taxonomy

A starting point, grounded in what the site actually has. Change anything —
nothing is wired to events yet, so it is cheap to argue with now and expensive
to argue with later.

## Conventions

- `snake_case`, lowercase, `verb_noun`. GA4 recommended names are used where one
  exists (`generate_lead`, `file_download`) because Google Ads can import those
  as conversions without extra mapping.
- Every event carries `service` and `page_type` so any report can be split by
  trade or by page without a separate breakdown.
- **No personal data, ever.** Name, company, phone and email must never be sent
  to GA. It breaks Google's terms, and the privacy policy on this site says
  those four fields are used to ring people back and nothing else.

## Dimensions on every event

| Param | Values | Where it comes from |
| --- | --- | --- |
| `service` | `local`, `moving`, `cleaning`, `restoration` | the page the visitor came through — the same rule that picks their playbook |
| `page_type` | `home`, `service`, `ads`, `ads_legacy`, `booking`, `thank_you`, `content`, `legal` | the page itself |

`service` follows the visitor: someone landing on `cleaning-ads.html` and
booking on `book-a-call.html` stays `cleaning` for the whole session. That is
what makes cost-per-lead answerable per trade.

## Events

| Event | Fires when | Params |
| --- | --- | --- |
| `page_view` | automatic | `service`, `page_type` |
| `cta_click` | any "Book a call" is clicked | `location`: `nav`, `hero`, `inline`, `footer` |
| `phone_click` | any `tel:` link is clicked | `location` |
| `spend_select` | the monthly-spend dropdown changes | `spend_band` |
| `form_start` | first touch of any form field | `form_id`: `home`, `booking` |
| `form_error` | validation blocks a submit | `form_id`, `error_fields` (e.g. `phone,email`) |
| `generate_lead` | a submit succeeds | `service`, `spend_band`, `form_id`, `playbook` |
| `file_download` | a playbook PDF is opened directly | `file_name` |

`spend_band` is normalised to `0_5k`, `5_10k`, `10k_plus`, `unset` rather than
the display text, so the labels can be reworded without splitting the history.

## What each answers

- **Which trade is worth the spend** — `generate_lead` by `service`, against ad
  spend per campaign.
- **Where people give up** — `form_start` against `generate_lead` is form
  abandonment; `form_error` by `error_fields` says which field is doing it.
- **Whether the ads pages earn their traffic** — `cta_click` by `page_type`,
  since the ads pages have no form and exist only to drive to the booking page.
- **Whether phone beats form** — `phone_click` against `generate_lead`. Worth
  knowing before optimising either.

## Open questions

1. Is `generate_lead` the conversion imported into Google Ads, or is a booked
   call the real conversion? If the latter, that is offline conversion import
   and needs a click ID stored with the lead.
2. Should `thank_you` page views count as the conversion instead of the submit
   event? Cleaner against ad blockers, but loses anyone who bounces before the
   redirect lands.
3. Consent: no banner exists today. Ontario does not require one, but EU
   visitors do. Smartlook is set to `region: 'eu'`, which is worth reconciling.
