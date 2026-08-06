# Analytics taxonomy — Make It Ring

GA4 property `G-7NRTMS7Y1R`. Site deploys from Cloudflare Workers.

**Status:** `page_view` and `generate_lead` are live. Everything under
"Not yet wired" is agreed but not built.

## Conventions

- `snake_case`, lowercase, `verb_noun`. GA4 recommended names are used where one
  exists (`generate_lead`, `file_download`) so Google Ads can import them as
  conversions without extra mapping.
- Every event carries `service` and `page_type`, so any report splits by trade or
  by page without a separate breakdown.
- **No personal data, ever.** Name, company, phone and email must never reach GA.
  It breaks Google's terms, and the site's privacy policy says those four fields
  are used to ring people back and nothing else.

## Dimensions

| Param | Values | Source |
| --- | --- | --- |
| `service` | `local`, `moving`, `cleaning`, `restoration` | the page the visitor came through |
| `page_type` | `home`, `service`, `ads`, `ads_legacy`, `booking`, `thank_you`, `content`, `legal` | the page itself |
| `spend_band` | `0_5k`, `5_10k`, `10k_plus`, `unset` | the monthly-spend dropdown |
| `form_id` | `home`, `booking` | which of the two forms was used |

`service` follows the visitor. Someone landing on `cleaning-ads.html` and booking
on `book-a-call.html` stays `cleaning` for the whole session, which is what makes
cost-per-lead answerable per trade. It is stored in session storage on each page
and read back at submit, falling back to the referrer and then to `local`.

`spend_band` is normalised rather than stored as display text, so the wording can
change without splitting the reporting history.

## Live

| Event | Fires when | Params |
| --- | --- | --- |
| `page_view` | automatic, every page | `service`, `page_type` |
| `generate_lead` | the visitor lands on `thank-you.html` after a successful submit | `service`, `spend_band`, `form_id`, `page_type` |

**`generate_lead` is the conversion.** It counts the thank-you landing rather
than the submit click: it survives ad blockers better and is what Google Ads
imports. It fires once per submission — the flag is cleared as it is read, so a
refresh or a back-button return cannot double-count.

## Not yet wired

Agreed, not built. Names are fixed; wiring is mechanical.

| Event | Fires when | Params |
| --- | --- | --- |
| `cta_click` | a "Book a call" is clicked | `location`: `nav`, `hero`, `inline`, `footer` |
| `phone_click` | a `tel:` link is clicked | `location` |
| `spend_select` | the spend dropdown changes | `spend_band` |
| `form_start` | first touch of any form field | `form_id` |
| `form_error` | validation blocks a submit | `form_id`, `error_fields` |
| `file_download` | a playbook PDF is opened directly | `file_name` |

## What each answers

- **Which trade earns the spend** — `generate_lead` by `service`, against ad spend
  per campaign.
- **Where people give up** — `form_start` against `generate_lead` is abandonment;
  `form_error` by `error_fields` says which field causes it.
- **Whether the ads pages earn their traffic** — `cta_click` by `page_type`. Those
  pages have no form; they exist only to drive to the booking page.
- **Whether phone beats form** — `phone_click` against `generate_lead`. Worth
  knowing before optimising either.

## Setup still to do in GA4

1. **Admin → Events**, mark `generate_lead` as a **key event**. Only appears once
   data has flowed.
2. **Admin → Product links → Google Ads**, link the account, import the key event
   as a conversion.
3. Register `service`, `spend_band` and `form_id` as **custom dimensions** under
   **Admin → Custom definitions**, or they will not be reportable.

## Open questions

1. **Is a form fill the real conversion, or a booked call?** If the latter, that is
   offline conversion import: the form must capture Google's click id (`gclid`)
   and store it with the lead so the outcome can be uploaded later. Worth settling
   before campaigns are optimised on form fills, since the two pull differently.
2. **Consent.** No banner today. Ontario does not require one, EU visitors do, and
   Smartlook is configured `region: 'eu'` — worth reconciling.
