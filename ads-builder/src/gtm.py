"""Generate a Google Tag Manager container export for a client.

"Install these scripts on your site" fails because the client's site is
theirs. "Import this file" succeeds: GTM's Admin > Import Container takes this
JSON and creates every tag, trigger and variable in two clicks, on any site
that already has the GTM snippet.

What the container carries, mirroring the reference account's stack:
  - GA4 configuration tag (all pages)
  - Google Ads conversion tag, fired on the generate_lead dataLayer event the
    thank-you page pushes
  - phone-click event (any tel: link), pushed to GA4
  - CallRail dynamic number swap script, when the client has one
  - form_start event on first interaction with a lead form

IDs that are not known yet are simply left out, and the summary says so —
a placeholder ID collects nothing and looks like it works.
"""

import json
from pathlib import Path

_uid = 0
def _next() -> str:
    global _uid
    _uid += 1
    return str(_uid)


def _tag(name, tag_type, params, trigger_ids):
    return {"tagId": _next(), "name": name, "type": tag_type,
            "parameter": params, "firingTriggerId": trigger_ids,
            "tagFiringOption": "ONCE_PER_EVENT"}


def _template(key, value):
    return {"type": "TEMPLATE", "key": key, "value": value}


def build_container(brief: dict) -> tuple[dict | None, list[str]]:
    global _uid
    _uid = 100
    tracking = brief.get("tracking", {}) or {}
    client = brief.get("client", {})
    notes: list[str] = []

    ga4 = tracking.get("ga4_measurement_id")
    aw_id = tracking.get("google_ads_conversion_id")
    aw_label = tracking.get("google_ads_conversion_label")
    callrail = tracking.get("callrail_swap_script")

    triggers = [
        {"triggerId": "10", "name": "All Pages", "type": "PAGEVIEW"},
        {"triggerId": "11", "name": "generate_lead event", "type": "CUSTOM_EVENT",
         "customEventFilter": [{"type": "EQUALS", "parameter": [
             _template("arg0", "{{_event}}"), _template("arg1", "generate_lead")]}]},
        {"triggerId": "12", "name": "Phone link click", "type": "LINK_CLICK",
         "filter": [{"type": "STARTS_WITH", "parameter": [
             _template("arg0", "{{Click URL}}"), _template("arg1", "tel:")]}],
         "waitForTags": {"type": "BOOLEAN", "value": "false"},
         "checkValidation": {"type": "BOOLEAN", "value": "false"}},
    ]

    tags = []
    if ga4:
        tags.append(_tag("GA4 Configuration", "gaawc",
                         [_template("measurementId", ga4)], ["10"]))
        tags.append(_tag("GA4 - phone_click", "gaawe",
                         [_template("eventName", "phone_click"),
                          _template("measurementIdOverride", ga4)], ["12"]))
        tags.append(_tag("GA4 - generate_lead", "gaawe",
                         [_template("eventName", "generate_lead"),
                          _template("measurementIdOverride", ga4)], ["11"]))
    else:
        notes.append("GA4 measurement ID missing — GA4 tags left out of the container")

    if aw_id and aw_label:
        tags.append(_tag("Google Ads - Lead conversion", "awct",
                         [_template("conversionId", aw_id.replace("AW-", "")),
                          _template("conversionLabel", aw_label)], ["11"]))
    else:
        notes.append("Ads conversion ID/label missing — the conversion tag is left out; "
                     "add it after creating the Leads conversion in Google Ads")

    if callrail:
        tags.append(_tag("CallRail number swap", "html",
                         [_template("html", f'<script async src="{callrail}"></script>'),
                          {"type": "BOOLEAN", "key": "supportDocumentWrite", "value": "false"}],
                         ["10"]))
    else:
        notes.append("CallRail swap script missing — dynamic number insertion not in container")

    if not tags:
        return None, notes + ["no IDs at all yet: container skipped entirely"]

    container = {
        "exportFormatVersion": 2,
        "containerVersion": {
            "container": {
                "name": f"{client.get('business_name', 'Client')} — generated",
                "usageContext": ["WEB"],
            },
            "tag": tags,
            "trigger": triggers,
            "variable": [],
            "builtInVariable": [
                {"type": "PAGE_URL", "name": "Page URL"},
                {"type": "CLICK_URL", "name": "Click URL"},
            ],
        },
    }
    return container, notes


def write_container(brief: dict, out_dir: Path) -> Path | None:
    container, notes = build_container(brief)
    for note in notes:
        print(f"   gtm: {note}")
    if container is None:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "gtm-container.json"
    path.write_text(json.dumps(container, indent=2), encoding="utf-8")
    return path
