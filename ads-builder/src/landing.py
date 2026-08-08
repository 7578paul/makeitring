"""Generate a client's landing page, with the tracking already installed.

This is the piece that makes attribution possible. A campaign can be perfect
and still be un-optimisable if the page it lands on cannot say which click
produced which booked job — so the page is generated with the whole chain
wired in rather than added afterwards:

  ad click  ->  gclid + campaign/content/keyword captured from the URL
            ->  stored so they survive the visit
            ->  written into the form as hidden fields
            ->  posted to wherever leads go
            ->  thank-you page fires the conversion Google imports

The URL parameters are the ones the live account's tracking template actually
sends — `campaign`, `content`, `keyword`, not `utm_*`. Reading for the wrong
parameter names is the same as not reading at all.

We generate and deploy this page, which is also why the tracking scripts can
be installed here at all: a client's own website is theirs, but this page is
ours to build.
"""

from html import escape
from pathlib import Path

from .compiler import require

TRUST_DEFAULTS = ["Licensed & insured", "Background-checked crews", "No hidden fees"]


def _tracking_head(cfg: dict) -> str:
    """GTM, GA4 and the Ads tag. Anything missing is simply left out rather than
    emitted with a placeholder id, which would silently collect nothing."""
    out = []

    if gtm := cfg.get("gtm_container"):
        out.append(f"""<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':
new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
}})(window,document,'script','dataLayer','{escape(gtm)}');</script>""")

    tags = [t for t in (cfg.get("ga4_measurement_id"), cfg.get("google_ads_conversion_id")) if t]
    if tags:
        out.append(f"""<script async src="https://www.googletagmanager.com/gtag/js?id={escape(tags[0])}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
{chr(10).join(f"  gtag('config', '{escape(t)}');" for t in tags)}
</script>""")

    if crid := cfg.get("callrail_swap_script"):
        out.append(f'<!-- CallRail dynamic number insertion -->\n'
                   f'<script async src="{escape(crid)}"></script>')

    return "\n".join(out)


ATTRIBUTION_JS = """
/* Capture the click before anything can lose it.
   These parameter names come from the account's real tracking template:
   {lpurl}?campaign={campaignid}&content={creative}&keyword={keyword}
   plus gclid, which Google appends itself. */
(function () {
  var FIELDS = ['gclid', 'gbraid', 'wbraid', 'campaign', 'content', 'keyword',
                'utm_source', 'utm_medium', 'utm_campaign', 'utm_term'];
  var KEY = 'attribution';

  function read() {
    var params = new URLSearchParams(location.search), found = {};
    FIELDS.forEach(function (f) { if (params.get(f)) found[f] = params.get(f); });
    return found;
  }

  /* First touch wins and is kept for 90 days: someone can click the ad today
     and fill the form on Thursday, and it is still the ad's lead. */
  var stored = {};
  try { stored = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) {}
  var fresh = read();

  if (Object.keys(fresh).length) {
    fresh.landed_at = new Date().toISOString();
    fresh.landing_page = location.pathname;
    if (!stored.gclid || fresh.gclid) {
      stored = fresh;
      try { localStorage.setItem(KEY, JSON.stringify(stored)); } catch (e) {}
    }
  }
  window.__attribution = stored;

  /* Write it into every form on the page as hidden fields. */
  function fill() {
    document.querySelectorAll('form[data-lead]').forEach(function (form) {
      Object.keys(stored).forEach(function (k) {
        if (form.querySelector('[name="' + k + '"]')) return;
        var input = document.createElement('input');
        input.type = 'hidden'; input.name = k; input.value = stored[k];
        form.appendChild(input);
      });
    });
  }
  document.addEventListener('DOMContentLoaded', fill);
  fill();
})();
"""

CONVERSION_JS = """
/* Fires once, on the thank-you page, not on the submit click — it survives ad
   blockers better and it is what Google Ads imports. The flag is cleared as it
   is read, so a refresh or a back-button return cannot double-count. */
(function () {
  if (!sessionStorage.getItem('lead_submitted')) return;
  sessionStorage.removeItem('lead_submitted');

  if (window.gtag) {
    gtag('event', 'generate_lead', {
      currency: '__CURRENCY__',
      value: __LEAD_VALUE__
    });
    __ADS_CONVERSION__
  }
  window.dataLayer = window.dataLayer || [];
  window.dataLayer.push({ event: 'generate_lead' });
})();
"""


def _css(accent: str) -> str:
    return f"""
*{{box-sizing:border-box}}
:root{{--accent:{accent};--ink:#141210;--muted:#5f584f;--line:#e5e0d8;--bg:#faf8f5;--card:#fff}}
body{{margin:0;font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  color:var(--ink);background:var(--bg);-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1120px;margin:0 auto;padding:0 20px}}
header{{background:var(--card);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:20}}
.bar{{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:12px 0}}
.brand{{font-weight:800;font-size:19px;letter-spacing:-.02em}}
.tel{{display:inline-flex;align-items:center;gap:8px;background:var(--accent);color:#fff;
  text-decoration:none;font-weight:800;padding:11px 18px;border-radius:999px;white-space:nowrap}}
.hero{{display:grid;gap:34px;grid-template-columns:1.15fr .85fr;padding:44px 0 40px;align-items:start}}
@media(max-width:860px){{.hero{{grid-template-columns:1fr;padding:26px 0}}}}
h1{{font-size:clamp(30px,4.6vw,46px);line-height:1.06;letter-spacing:-.035em;margin:0 0 14px;text-wrap:balance}}
.lede{{font-size:18.5px;color:var(--muted);margin:0 0 20px;max-width:44ch}}
.stars{{color:#f5a623;letter-spacing:2px;font-size:17px}}
.rating{{display:flex;align-items:center;gap:10px;margin:0 0 18px;font-size:14.5px;color:var(--muted)}}
.badges{{display:flex;flex-wrap:wrap;gap:8px;margin:22px 0 0;padding:0;list-style:none}}
.badges li{{background:var(--card);border:1px solid var(--line);border-radius:999px;
  padding:7px 14px;font-size:13.5px;font-weight:600}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:26px;
  box-shadow:0 1px 2px rgba(20,18,16,.04),0 12px 32px rgba(20,18,16,.07)}}
.card h2{{margin:0 0 4px;font-size:22px;letter-spacing:-.02em}}
.card p.sub{{margin:0 0 18px;color:var(--muted);font-size:14.5px}}
label{{display:block;font-size:13px;font-weight:700;margin:0 0 5px}}
input,select,textarea{{width:100%;padding:12px 13px;font:inherit;font-size:15.5px;
  border:1px solid var(--line);border-radius:9px;background:#fff;color:var(--ink)}}
input:focus,select:focus,textarea:focus{{outline:2.5px solid var(--accent);outline-offset:-1px}}
.row{{margin:0 0 13px}}
.two{{display:grid;gap:13px;grid-template-columns:1fr 1fr}}
button{{width:100%;background:var(--accent);color:#fff;border:0;border-radius:999px;
  padding:15px;font:inherit;font-weight:800;font-size:17px;cursor:pointer;margin-top:6px}}
button:hover{{opacity:.92}}
.callback{{text-align:center;margin:13px 0 0;font-size:14px;color:var(--muted)}}
.callback a{{color:var(--accent);font-weight:700}}
section.band{{background:var(--card);border-top:1px solid var(--line);padding:44px 0}}
h2.sec{{font-size:clamp(23px,3vw,31px);letter-spacing:-.025em;margin:0 0 22px;text-wrap:balance}}
.g3{{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}}
.rev{{background:var(--bg);border:1px solid var(--line);border-radius:13px;padding:20px}}
.rev p{{margin:9px 0 12px;font-size:15.5px}}
.rev b{{font-size:14px}}
.svc{{display:flex;flex-wrap:wrap;gap:9px;list-style:none;padding:0;margin:0}}
.svc li{{background:var(--bg);border:1px solid var(--line);border-radius:9px;padding:11px 16px;font-weight:600;font-size:15px}}
footer{{padding:30px 0;color:var(--muted);font-size:13.5px;text-align:center}}
.sr{{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}}
"""


def _reviews(items: list[dict]) -> str:
    if not items:
        return ""
    cards = "".join(
        f'<div class="rev"><div class="stars" aria-hidden="true">★★★★★</div>'
        f'<p>“{escape(r.get("quote", ""))}”</p>'
        f'<b>{escape(r.get("name", "Verified customer"))}</b></div>'
        for r in items
    )
    return (f'<section class="band"><div class="wrap"><h2 class="sec">What customers say</h2>'
            f'<div class="g3">{cards}</div></div></section>')


def build_page(brief: dict, *, page: str = "index") -> str:
    client = brief["client"]
    name = client["business_name"]
    phone = client["phone"]
    tel = "".join(ch for ch in phone if ch.isdigit() or ch == "+")
    lp = brief.get("landing", {})
    tracking = brief.get("tracking", {})
    accent = lp.get("accent", "#ff5a1f")
    city = (brief.get("service_area", {}).get("cities") or ["your area"])[0]
    offer = brief.get("positioning", {}).get("offer", "Free quote")
    services = brief.get("landing", {}).get("services") or []
    trust = lp.get("trust_badges") or TRUST_DEFAULTS

    head = _tracking_head(tracking)
    gtm_noscript = ""
    if gtm := tracking.get("gtm_container"):
        gtm_noscript = (f'<noscript><iframe src="https://www.googletagmanager.com/ns.html?id={escape(gtm)}"'
                        f' height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>')

    if page == "thank-you":
        ads_id = tracking.get("google_ads_conversion_id")
        label = tracking.get("google_ads_conversion_label")
        conversion = (f"gtag('event', 'conversion', {{'send_to': '{escape(ads_id)}/{escape(label)}'}});"
                      if ads_id and label else "/* Ads conversion label not set yet */")
        script = (CONVERSION_JS
                  .replace("__CURRENCY__", escape(client.get("currency", "CAD")))
                  .replace("__LEAD_VALUE__", str(lp.get("lead_value", 1)))
                  .replace("__ADS_CONVERSION__", conversion))
        body = f"""
<header><div class="wrap bar"><span class="brand">{escape(name)}</span>
<a class="tel" href="tel:{escape(tel)}">{escape(phone)}</a></div></header>
<div class="wrap" style="padding:70px 20px;text-align:center;max-width:640px">
  <h1>Thanks — we've got it.</h1>
  <p class="lede" style="margin:0 auto 22px">One of our team will call you shortly.
     If it's urgent, ring us now and we'll pick up.</p>
  <a class="tel" href="tel:{escape(tel)}" style="font-size:18px;padding:15px 26px">{escape(phone)}</a>
</div>
<footer><div class="wrap">© {escape(name)}</div></footer>
<script>{script}</script>"""
        title = f"Thank you — {name}"
    else:
        service_options = "".join(f'<option>{escape(s)}</option>' for s in services) or \
                          '<option>Local move</option><option>Long distance</option><option>Commercial</option>'
        badges = "".join(f"<li>{escape(b)}</li>" for b in trust)
        rating = lp.get("rating", "4.9")
        review_count = lp.get("review_count", "")
        rating_line = (f'<div class="rating"><span class="stars" aria-hidden="true">★★★★★</span>'
                       f'<span><b>{escape(str(rating))}</b>'
                       f'{f" from {escape(str(review_count))} reviews" if review_count else ""}</span></div>')
        services_band = ""
        if services:
            services_band = (f'<section class="band"><div class="wrap"><h2 class="sec">What we move</h2>'
                             f'<ul class="svc">{"".join(f"<li>{escape(s)}</li>" for s in services)}'
                             f'</ul></div></section>')

        body = f"""
<header><div class="wrap bar">
  <span class="brand">{escape(name)}</span>
  <a class="tel" href="tel:{escape(tel)}" data-call>
    <span aria-hidden="true">📞</span><span class="tel-number">{escape(phone)}</span></a>
</div></header>

<div class="wrap"><div class="hero">
  <div>
    <h1>{escape(lp.get("headline") or f"{city} movers who quote it straight")}</h1>
    {rating_line}
    <p class="lede">{escape(lp.get("subhead") or
      "Upfront pricing, no surprises on moving day. Tell us about your move and we'll come back with a written quote.")}</p>
    <ul class="badges">{badges}</ul>
  </div>

  <div class="card">
    <h2>{escape(offer)}</h2>
    <p class="sub">Takes about a minute. No obligation.</p>
    <form data-lead method="post" action="{escape(brief.get("lead_delivery", {}).get("endpoint", "#"))}">
      <div class="row"><label for="nm">Your name</label>
        <input id="nm" name="name" required autocomplete="name"></div>
      <div class="two">
        <div class="row"><label for="ph">Phone</label>
          <input id="ph" name="phone" type="tel" required autocomplete="tel"></div>
        <div class="row"><label for="em">Email</label>
          <input id="em" name="email" type="email" autocomplete="email"></div>
      </div>
      <div class="two">
        <div class="row"><label for="fr">Moving from</label>
          <input id="fr" name="moving_from" placeholder="{escape(city)}"></div>
        <div class="row"><label for="to">Moving to</label>
          <input id="to" name="moving_to"></div>
      </div>
      <div class="row"><label for="sv">What do you need?</label>
        <select id="sv" name="service">{service_options}</select></div>
      <div class="row"><label for="dt">Move date</label>
        <input id="dt" name="move_date" type="date"></div>
      <label class="sr" for="hp">Leave blank</label>
      <input class="sr" id="hp" name="company_website" tabindex="-1" autocomplete="off">
      <button type="submit">Get my quote</button>
      <p class="callback">Rather talk? <a href="tel:{escape(tel)}">Call {escape(phone)}</a></p>
    </form>
  </div>
</div></div>

{services_band}
{_reviews(lp.get("reviews") or [])}
<footer><div class="wrap">© {escape(name)} · {escape(phone)}</div></footer>

<script>
document.querySelector('form[data-lead]').addEventListener('submit', function (e) {{
  /* a bot filling the hidden field is the only thing this blocks */
  if (this.company_website.value) {{ e.preventDefault(); return; }}
  sessionStorage.setItem('lead_submitted', '1');
}});
</script>"""
        title = lp.get("title") or f"{name} — {city} Movers | {offer}"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{escape(title)}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{escape(lp.get('meta_description') or f'{name}. {offer}. Call {phone}.')}">
<meta name="robots" content="{'noindex' if page == 'thank-you' else 'index,follow'}">
{head}
<style>{_css(accent)}</style>
<script>{ATTRIBUTION_JS}</script>
</head>
<body>
{gtm_noscript}
{body}
</body>
</html>"""


def write_site(brief: dict, out_dir: Path) -> list[Path]:
    require(brief, "client.business_name")
    require(brief, "client.phone")
    out_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for page, filename in (("index", "index.html"), ("thank-you", "thank-you.html")):
        path = out_dir / filename
        path.write_text(build_page(brief, page=page), encoding="utf-8")
        written.append(path)

    # Cloudflare Pages serves a directory as-is; no build step, same as the
    # main site. The client adds one CNAME and nothing else.
    (out_dir / "_headers").write_text(
        "/*\n"
        "  X-Frame-Options: SAMEORIGIN\n"
        "  X-Content-Type-Options: nosniff\n"
        "  Referrer-Policy: strict-origin-when-cross-origin\n",
        encoding="utf-8")
    written.append(out_dir / "_headers")
    return written
