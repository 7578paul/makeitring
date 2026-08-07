"""HTML for the local UI.

Rendered from the Plan directly rather than by converting the markdown build
sheet, so the screen can show things the file cannot — character counts as
coloured badges, collapsible ad groups, an errors-block-the-download rule.

No frameworks, no CDN, no build step: one file, plain CSS, a little JS.
"""

from html import escape

from .model import MAX_DESCRIPTION, MAX_HEADLINE, Plan

CSS = """
*{box-sizing:border-box}
:root{
  --bg:#f6f6f4; --card:#fff; --ink:#111; --muted:#666; --line:#e4e4e0;
  --accent:#1a56db; --ok:#0a7c42; --warn:#9a6700; --err:#b42318;
  --okbg:#e7f5ee; --warnbg:#fdf6e3; --errbg:#fdeceb;
}
@media (prefers-color-scheme:dark){
  :root{--bg:#15151a; --card:#1e1e24; --ink:#f2f2f0; --muted:#9a9aa2; --line:#32323a;
        --accent:#7aa2f7; --ok:#4ade80; --warn:#fbbf24; --err:#f87171;
        --okbg:#12281d; --warnbg:#2a2213; --errbg:#2a1614;}
}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:28px 20px 80px}
h1{font-size:26px;letter-spacing:-.02em;margin:0 0 4px}
h2{font-size:19px;letter-spacing:-.015em;margin:32px 0 12px}
h3{font-size:16px;margin:20px 0 8px}
.sub{color:var(--muted);margin:0 0 24px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px;margin:0 0 16px}
fieldset{border:0;padding:0;margin:0 0 26px}
legend{font-weight:700;font-size:13px;letter-spacing:.08em;text-transform:uppercase;
  color:var(--muted);padding:0;margin:0 0 12px}
label{display:block;font-size:13.5px;font-weight:600;margin:0 0 5px}
.hint{font-weight:400;color:var(--muted)}
input[type=text],input[type=number],select,textarea{
  width:100%;padding:9px 11px;border:1px solid var(--line);border-radius:9px;
  background:var(--bg);color:var(--ink);font:inherit;font-size:14.5px}
textarea{min-height:78px;resize:vertical;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px}
input:focus,select:focus,textarea:focus{outline:2px solid var(--accent);outline-offset:-1px}
.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(210px,1fr))}
.row{margin:0 0 14px}
.checks{display:grid;gap:8px;grid-template-columns:repeat(auto-fit,minmax(190px,1fr))}
.check{display:flex;align-items:flex-start;gap:9px;padding:11px 13px;border:1px solid var(--line);
  border-radius:10px;background:var(--bg);cursor:pointer;font-size:14px;font-weight:500}
.check input{margin:2px 0 0}
button{background:var(--accent);color:#fff;border:0;border-radius:999px;padding:13px 26px;
  font:inherit;font-weight:700;cursor:pointer}
button.ghost{background:transparent;color:var(--accent);border:1.5px solid var(--accent)}
a.btn{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;
  border-radius:999px;padding:13px 26px;font-weight:700}
a.btn.off{background:var(--line);color:var(--muted);pointer-events:none}
.tiles{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));margin:0 0 20px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:15px}
.tile b{display:block;font-size:25px;letter-spacing:-.02em}
.tile span{font-size:12.5px;color:var(--muted)}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}
th{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.msg{padding:11px 14px;border-radius:10px;margin:0 0 9px;font-size:14px}
.msg.error{background:var(--errbg);color:var(--err)}
.msg.warning{background:var(--warnbg);color:var(--warn)}
.msg.ok{background:var(--okbg);color:var(--ok)}
details{background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:12px 16px;margin:0 0 9px}
summary{cursor:pointer;font-weight:600;font-size:15px}
summary span{font-weight:400;color:var(--muted);font-size:13.5px}
.kw{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;color:var(--muted);
  columns:2;column-gap:24px;margin:10px 0}
.asset{display:flex;gap:9px;align-items:baseline;padding:3px 0;font-size:14px}
.len{font-family:ui-monospace,monospace;font-size:11px;padding:1px 6px;border-radius:5px;
  background:var(--okbg);color:var(--ok);min-width:30px;text-align:center}
.len.tight{background:var(--warnbg);color:var(--warn)}
.meta{color:var(--muted);font-size:13.5px;margin:4px 0}
code{font-family:ui-monospace,monospace;font-size:12.5px;background:var(--bg);padding:1px 5px;border-radius:5px}
"""


def page(title: str, body: str) -> str:
    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{escape(title)}</title><style>{CSS}</style></head>"
        f"<body><div class=wrap>{body}</div></body></html>"
    )


def _field(label: str, name: str, value: str = "", hint: str = "", kind: str = "text",
           placeholder: str = "") -> str:
    hint_html = f" <span class=hint>{escape(hint)}</span>" if hint else ""
    return (
        f"<div class=row><label for={name}>{escape(label)}{hint_html}</label>"
        f"<input type={kind} id={name} name={name} value='{escape(str(value), quote=True)}' "
        f"placeholder='{escape(placeholder, quote=True)}'></div>"
    )


def _area(label: str, name: str, value: str = "", hint: str = "") -> str:
    hint_html = f" <span class=hint>{escape(hint)}</span>" if hint else ""
    return (
        f"<div class=row><label for={name}>{escape(label)}{hint_html}</label>"
        f"<textarea id={name} name={name}>{escape(value)}</textarea></div>"
    )


def form_html(trades: list[str], trade: str, campaigns: list[dict], values: dict) -> str:
    def v(key: str, default: str = "") -> str:
        return str(values.get(key, default))

    trade_options = "".join(
        f"<option value='{escape(t)}'{' selected' if t == trade else ''}>{escape(t.title())}</option>"
        for t in trades
    )

    selected = set(values.get("services", [c["key"] for c in campaigns]))
    checks = "".join(
        f"<label class=check><input type=checkbox name=services value='{escape(c['key'])}'"
        f"{' checked' if c['key'] in selected else ''}>"
        f"<span>{escape(c['label'])}<br><span class=hint>{c.get('budget_weight', 0)}% of budget</span></span></label>"
        for c in campaigns
    )

    return page(
        "ads-builder",
        f"""
<h1>Build a Google Ads account</h1>
<p class=sub>Fill this in once per client. Everything lands paused — nothing goes live until you post it.</p>
<form method=post action=/build class=card>
  <fieldset><legend>The business</legend>
    <div class=grid>
      {_field("Business name", "business_name", v("business_name"), placeholder="Redline Moving")}
      {_field("Short code", "slug", v("slug"), "used for folder names", placeholder="redline")}
    </div>
    <div class=grid>
      {_field("Phone", "phone", v("phone"), placeholder="+1 416 555 0134")}
      {_field("Website", "website", v("website"), placeholder="https://example.com")}
    </div>
    <div class=grid>
      <div class=row><label for=trade>Trade</label>
        <select id=trade name=trade onchange="this.form.action='/';this.form.method='get';this.form.submit()">
          {trade_options}</select></div>
      {_field("Currency", "currency", v("currency", "CAD"))}
      {_field("Google Ads customer ID", "customer_id", v("customer_id"), placeholder="123-456-7890")}
    </div>
  </fieldset>

  <fieldset><legend>Campaigns to build</legend>
    <div class=checks>{checks}</div>
  </fieldset>

  <fieldset><legend>Service area</legend>
    <div class=grid>
      {_area("Cities", "cities", v("cities"), "one per line — first is the home city")}
      {_field("Region", "region", v("region", "Ontario, Canada"), "appended to each city for geo targeting")}
    </div>
  </fieldset>

  <fieldset><legend>Budget</legend>
    <div class=grid>
      {_field("Monthly total", "monthly_total", v("monthly_total", "6000"), kind="number")}
      {_area("Weight overrides", "weights", v("weights"), "optional, one per line: long_distance = 45")}
    </div>
  </fieldset>

  <fieldset><legend>Positioning</legend>
    <div class=grid>
      {_field("Offer", "offer", v("offer"), placeholder="Free in-home estimate")}
      {_field("Minimum job", "min_job_value", v("min_job_value"), placeholder="$450 minimum")}
    </div>
    {_area("Brand terms", "brand_terms", v("brand_terms"), "one per line — your own name, for the brand campaign")}
  </fieldset>

  <fieldset><legend>Landing pages</legend>
    {_field("Default URL", "default_url", v("default_url"), placeholder="https://example.com/")}
    {_area("Per campaign", "page_map", v("page_map"), "optional, one per line: long_distance = https://…")}
  </fieldset>

  <fieldset><legend>Opening hours</legend>
    <label class=check style=margin-bottom:12px>
      <input type=checkbox name=always {'checked' if values.get('always') else ''}>
      <span>Open 24/7 — run ads around the clock</span></label>
    <div class=grid>
      {_field("Mon–Fri", "mon_fri", v("mon_fri", "07:00-19:00"))}
      {_field("Saturday", "sat", v("sat", "08:00-17:00"))}
      {_field("Sunday", "sun", v("sun"), "blank for closed")}
    </div>
  </fieldset>

  <button type=submit>Build campaigns</button>
</form>""",
    )


def results_html(plan: Plan, findings, out_dir: str, blocked: bool) -> str:
    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]

    messages = "".join(
        f"<div class='msg {f.severity}'><b>{escape(f.where)}</b> — {escape(f.message)}</div>"
        for f in errors + warnings
    ) or "<div class='msg ok'>All checks passed.</div>"

    total = plan.daily_budget_total or 1
    rows = "".join(
        f"<tr><td>{escape(c.name)}</td><td class=n>{c.daily_budget:,.2f}</td>"
        f"<td class=n>{c.daily_budget * 30.4:,.0f}</td>"
        f"<td class=n>{c.daily_budget / total * 100:.0f}%</td></tr>"
        for c in plan.campaigns
    )

    blocks = []
    for campaign in plan.campaigns:
        groups = []
        for group in campaign.ad_groups:
            keywords = "".join(
                f"<div>{escape(_kw(k))}</div>" for k in group.keywords[:40]
            )
            if len(group.keywords) > 40:
                keywords += f"<div>… {len(group.keywords) - 40} more</div>"

            ads = ""
            for ad in group.ads:
                ads += f"<p class=meta>{escape(ad.final_url)}</p>"
                ads += "".join(_asset(h, MAX_HEADLINE) for h in ad.headlines)
                ads += "<div style=height:8px></div>"
                ads += "".join(_asset(d, MAX_DESCRIPTION) for d in ad.descriptions)

            groups.append(
                f"<details><summary>{escape(group.name)} "
                f"<span>· {len(group.keywords)} keywords</span></summary>"
                f"<div class=kw>{keywords}</div>{ads}</details>"
            )

        blocks.append(
            f"<h3>{escape(campaign.name)}</h3>"
            f"<p class=meta>{escape(campaign.bid_strategy)} · "
            f"{campaign.daily_budget:,.2f}/day · {len(campaign.negatives)} negatives · "
            f"geo <b>{escape(campaign.location_target_type)}</b></p>"
            + "".join(groups)
        )

    download = (
        "<a class='btn off'>Fix errors to download</a>"
        if blocked
        else f"<a class=btn href='/download?dir={escape(out_dir, quote=True)}'>Download CSVs</a>"
    )

    return page(
        f"{plan.business_name} — build",
        f"""
<h1>{escape(plan.business_name)}</h1>
<p class=sub>{escape(plan.trade)} · blueprint v{escape(plan.blueprint_version)} ·
everything below imports <b>paused</b></p>

<div class=tiles>
  <div class=tile><b>{len(plan.campaigns)}</b><span>campaigns</span></div>
  <div class=tile><b>{sum(len(c.ad_groups) for c in plan.campaigns)}</b><span>ad groups</span></div>
  <div class=tile><b>{sum(c.keyword_count for c in plan.campaigns)}</b><span>keywords</span></div>
  <div class=tile><b>{plan.daily_budget_total:,.0f}</b><span>{escape(plan.currency)}/day</span></div>
  <div class=tile><b>{len(errors)}</b><span>errors</span></div>
</div>

<h2>Checks</h2>{messages}

<h2>Budget</h2>
<div class=card><table><tr><th>Campaign</th><th class=n>Daily</th><th class=n>Monthly</th>
<th class=n>Share</th></tr>{rows}</table></div>

<h2>Structure</h2>{"".join(blocks)}

<p style=margin-top:28px>{download}
&nbsp;<a class='btn ghost' href='/' style='background:transparent;border:1.5px solid var(--accent);color:var(--accent)'>Start over</a></p>
<p class=meta>Written to <code>{escape(out_dir)}</code></p>""",
    )


def _kw(keyword) -> str:
    if keyword.match_type == "exact":
        return f"[{keyword.text}]"
    if keyword.match_type == "phrase":
        return f'"{keyword.text}"'
    return keyword.text


def _asset(text: str, limit: int) -> str:
    tight = " tight" if len(text) > limit - 3 else ""
    return (
        f"<div class=asset><span class='len{tight}'>{len(text)}</span>"
        f"<span>{escape(text)}</span></div>"
    )


def error_html(message: str) -> str:
    return page(
        "ads-builder — problem",
        f"<h1>That didn't build</h1><div class='msg error'>{escape(message)}</div>"
        "<p><a class=btn href='/'>Back</a></p>",
    )
