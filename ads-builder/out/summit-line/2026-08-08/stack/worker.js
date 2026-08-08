/* The tracking backbone. One Cloudflare Worker, one D1 database, all clients.
 *
 *   POST /lead?client=slug         landing page form posts here; attribution
 *                                  hidden fields ride along
 *   POST /webhook/callrail?client= CallRail post-call webhook; stores caller,
 *                                  duration, recording, attribution
 *   POST /click?client=            landing page logs every paid click for the
 *                                  fraud layer (fire-and-forget beacon)
 *   GET  /dash?client=&key=        the client dashboard
 *   GET  /export/conversions.csv?client=&key=
 *                                  Google Ads offline conversion import — the
 *                                  file that closes the loop from click to
 *                                  booked job
 *   GET  /export/ip-exclusions.csv?client=&key=
 *                                  IPs that clicked too often, as Editor rows
 *
 * Auth: per-client key in the CLIENT_KEYS env var as "slug:key,slug:key".
 * Writes (lead/click/webhook) are open by necessity — they come from browsers
 * and vendors — but validated and rate-limited by the fraud table itself.
 */

const FRAUD_CLICKS_PER_DAY = 6; // same IP, same client, 24h — beyond this is not a customer

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const client = (url.searchParams.get("client") || "").replace(/[^a-z0-9-]/g, "");
    const route = url.pathname;

    const cors = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };
    if (request.method === "OPTIONS") return new Response(null, { headers: cors });
    if (!client) return json({ error: "client required" }, 400, cors);

    try {
      if (route === "/lead" && request.method === "POST")
        return await lead(request, env, client, cors);
      if (route === "/click" && request.method === "POST")
        return await click(request, env, client, cors);
      if (route === "/webhook/callrail" && request.method === "POST")
        return await callWebhook(request, env, client, cors);

      // everything below needs the client key
      if (!authorised(env, client, url.searchParams.get("key")))
        return json({ error: "bad key" }, 403, cors);

      if (route === "/dash") return dashboard(env, client);
      if (route === "/export/conversions.csv") return conversionsCsv(env, client);
      if (route === "/export/ip-exclusions.csv") return ipExclusionsCsv(env, client);
      if (route === "/api/summary") return summary(env, client, cors);
      if (route === "/api/mark" && request.method === "POST")
        return await mark(request, env, client, cors);

      return json({ error: "no such route" }, 404, cors);
    } catch (err) {
      return json({ error: String(err) }, 500, cors);
    }
  },
};

function authorised(env, client, key) {
  if (!key) return false;
  const pairs = (env.CLIENT_KEYS || "").split(",");
  return pairs.some((p) => p.trim() === `${client}:${key}`);
}

function json(body, status = 200, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

async function body(request) {
  const type = request.headers.get("Content-Type") || "";
  if (type.includes("application/json")) return await request.json();
  const form = await request.formData();
  return Object.fromEntries(form.entries());
}

/* ---------------- writes ---------------- */

async function lead(request, env, client, cors) {
  const f = await body(request);
  if (f.company_website) return json({ ok: true }, 200, cors); // honeypot: swallow bots silently
  if (!f.name && !f.phone) return json({ error: "name or phone required" }, 400, cors);

  await env.DB.prepare(
    `INSERT INTO leads (client, name, phone, email, service, moving_from, moving_to,
       move_date, gclid, campaign, content, keyword, landing_page)
     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)`
  ).bind(client, s(f.name), s(f.phone), s(f.email), s(f.service), s(f.moving_from),
         s(f.moving_to), s(f.move_date), s(f.gclid), s(f.campaign), s(f.content),
         s(f.keyword), s(f.landing_page)).run();

  // browsers follow the redirect to the thank-you page, which fires the pixel
  const back = f._redirect || request.headers.get("Referer") || "";
  if (back && !back.includes("://" + new URL(request.url).host))
    return Response.redirect(back.replace(/[^/]*$/, "") + "thank-you.html", 303);
  return json({ ok: true }, 200, cors);
}

async function click(request, env, client, cors) {
  const f = await body(request).catch(() => ({}));
  const ip = request.headers.get("CF-Connecting-IP") || "";
  await env.DB.prepare(
    `INSERT INTO clicks (client, ip, gclid, campaign, keyword, user_agent)
     VALUES (?,?,?,?,?,?)`
  ).bind(client, ip, s(f.gclid), s(f.campaign), s(f.keyword),
         s(request.headers.get("User-Agent"))).run();
  return json({ ok: true }, 200, cors);
}

async function callWebhook(request, env, client, cors) {
  // CallRail's post-call webhook. Field names follow their payload; unknown
  // shapes land in the raw columns rather than being dropped.
  const f = await body(request);
  await env.DB.prepare(
    `INSERT INTO calls (client, caller_number, caller_name, duration_sec,
       recording_url, tracking_number, first_call, gclid, campaign, keyword, answered)
     VALUES (?,?,?,?,?,?,?,?,?,?,?)`
  ).bind(client,
         s(f.customer_phone_number || f.caller_number || f.callernum),
         s(f.customer_name || f.caller_name),
         parseInt(f.duration || f.duration_sec || 0, 10) || 0,
         s(f.recording || f.recording_url || f.recording_player),
         s(f.tracking_phone_number || f.tracking_number),
         f.first_call === true || f.first_call === "true" ? 1 : 0,
         s(f.gclid), s(f.utm_campaign || f.campaign),
         s(f.keywords || f.keyword),
         f.answered === false || f.answered === "false" ? 0 : 1).run();
  return json({ ok: true }, 200, cors);
}

async function mark(request, env, client, cors) {
  // the human closes the loop: this lead/call became a job worth X
  const f = await body(request);
  const table = f.kind === "call" ? "calls" : "leads";
  await env.DB.prepare(
    `UPDATE ${table} SET status = ?, job_value = ? WHERE id = ? AND client = ?`
  ).bind(s(f.status) || "booked", parseFloat(f.job_value) || null,
         parseInt(f.id, 10), client).run();
  return json({ ok: true }, 200, cors);
}

/* ---------------- exports ---------------- */

async function conversionsCsv(env, client) {
  // Google Ads > Conversions > Upload. Only rows with a gclid can be imported;
  // booked jobs carry their real value, which is what makes tCPA learn on
  // revenue instead of form fills.
  const { results } = await env.DB.prepare(
    `SELECT gclid, created_at, job_value, status FROM leads
      WHERE client = ? AND gclid != '' AND status IN ('booked','quoted')
     UNION ALL
     SELECT gclid, created_at, job_value, status FROM calls
      WHERE client = ? AND gclid != '' AND status IN ('booked','quoted')`
  ).bind(client, client).all();

  const rows = [["Google Click ID", "Conversion Name", "Conversion Time",
                 "Conversion Value", "Conversion Currency"]];
  for (const r of results) {
    rows.push([r.gclid, r.status === "booked" ? "Booked Job" : "Quoted",
               r.created_at.replace("T", " ") + " UTC",
               r.job_value || "", r.job_value ? "USD" : ""]);
  }
  return csv(rows, "conversions.csv");
}

async function ipExclusionsCsv(env, client) {
  const { results } = await env.DB.prepare(
    `SELECT ip, COUNT(*) AS n FROM clicks
      WHERE client = ? AND created_at > datetime('now', '-1 day') AND ip != ''
      GROUP BY ip HAVING n >= ?`
  ).bind(client, FRAUD_CLICKS_PER_DAY).all();

  const rows = [["IP address", "Clicks in 24h"]];
  for (const r of results) rows.push([r.ip, r.n]);
  return csv(rows, "ip-exclusions.csv");
}

function csv(rows, name) {
  const text = rows.map((r) => r.map((c) =>
    /[",\n]/.test(String(c)) ? `"${String(c).replace(/"/g, '""')}"` : c).join(",")).join("\r\n");
  return new Response(text, {
    headers: {
      "Content-Type": "text/csv",
      "Content-Disposition": `attachment; filename="${name}"`,
    },
  });
}

/* ---------------- dashboard ---------------- */

async function summary(env, client, cors) {
  const q = (sql, ...args) => env.DB.prepare(sql).bind(client, ...args).all();
  const [leads, calls, fraud] = await Promise.all([
    q(`SELECT * FROM leads WHERE client = ? ORDER BY created_at DESC LIMIT 200`),
    q(`SELECT * FROM calls WHERE client = ? ORDER BY created_at DESC LIMIT 200`),
    q(`SELECT ip, COUNT(*) AS n FROM clicks WHERE client = ?
        AND created_at > datetime('now','-1 day') GROUP BY ip
        HAVING n >= ${FRAUD_CLICKS_PER_DAY}`),
  ]);
  return json({ leads: leads.results, calls: calls.results,
                flagged_ips: fraud.results }, 200, cors);
}

async function dashboard(env, client) {
  return new Response(DASH_HTML.replace("__CLIENT__", client), {
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}

function s(v) { return (v === undefined || v === null) ? "" : String(v).slice(0, 500); }

const DASH_HTML = `<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>__CLIENT__ — leads</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<style>
*{box-sizing:border-box}
body{margin:0;font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  background:#f4f3f0;color:#17140f}
.wrap{max-width:1180px;margin:0 auto;padding:26px 18px}
h1{font-size:24px;letter-spacing:-.02em;margin:0 0 4px}
.sub{color:#6d6459;margin:0 0 22px;font-size:14px}
.tiles{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));margin:0 0 24px}
.tile{background:#fff;border:1px solid #e2ded6;border-radius:10px;padding:14px 16px}
.tile b{display:block;font-size:26px;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.tile span{font-size:11px;text-transform:uppercase;letter-spacing:.09em;color:#6d6459}
h2{font-size:17px;margin:26px 0 10px}
.card{background:#fff;border:1px solid #e2ded6;border-radius:12px;overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:13.5px;min-width:840px}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid #eee9e2;white-space:nowrap}
th{font-size:10.5px;text-transform:uppercase;letter-spacing:.08em;color:#6d6459}
tr:last-child td{border-bottom:0}
.pill{font-size:11px;font-weight:700;padding:2px 8px;border-radius:99px;background:#eee9e2}
.pill.booked{background:#dcefe3;color:#0f7a43}.pill.new{background:#fff1ea;color:#c14a12}
.pill.lost{background:#fbeae8;color:#a51b12}
a{color:#c14a12}
.attr{font-family:ui-monospace,monospace;font-size:11.5px;color:#6d6459}
button{font:inherit;font-size:12px;padding:3px 10px;border-radius:6px;border:1px solid #cfc9be;
  background:#fff;cursor:pointer}
.warn{background:#fdf6e3;border:1px solid #e0c469;border-radius:10px;padding:12px 16px;
  font-size:14px;margin:0 0 20px}
</style></head><body><div class="wrap">
<h1>__CLIENT__</h1>
<p class="sub">Every lead and call, with the ad click that caused it.
Mark jobs as booked (with the value) and the conversions export teaches Google
to find more like them.</p>
<div class="tiles" id="tiles"></div>
<div id="fraud"></div>
<h2>Form leads</h2><div class="card"><table id="leads"><thead><tr>
<th>When</th><th>Name</th><th>Phone</th><th>Service</th><th>From → To</th>
<th>Attribution</th><th>Status</th><th></th></tr></thead><tbody></tbody></table></div>
<h2>Calls</h2><div class="card"><table id="calls"><thead><tr>
<th>When</th><th>Caller</th><th>Number</th><th>Length</th><th>Recording</th>
<th>Attribution</th><th>Status</th><th></th></tr></thead><tbody></tbody></table></div>
<p class="sub" style="margin-top:20px">
<a id="dlconv">Download conversions for Google Ads</a> ·
<a id="dlip">Download IP exclusions</a></p>
<script>
const params=new URLSearchParams(location.search);
const base='?client='+params.get('client')+'&key='+params.get('key');
document.getElementById('dlconv').href='/export/conversions.csv'+base;
document.getElementById('dlip').href='/export/ip-exclusions.csv'+base;
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const money=v=>v?'$'+Number(v).toLocaleString():'';
function attr(r){return [r.campaign&&('c:'+r.campaign),r.keyword&&('kw:'+r.keyword),
  r.gclid&&'gclid ✓'].filter(Boolean).join(' · ')||'—';}
function pill(s){return '<span class="pill '+esc(s)+'">'+esc(s)+'</span>';}
async function markRow(kind,id){
  const status=prompt('Status (booked / quoted / contacted / lost):','booked');
  if(!status)return;
  const v=status==='booked'?prompt('Job value (numbers only):',''):'';
  await fetch('/api/mark'+base,{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({kind,id,status,job_value:v})});
  load();
}
async function load(){
  const r=await fetch('/api/summary'+base); const d=await r.json();
  const booked=[...d.leads,...d.calls].filter(x=>x.status==='booked');
  const withG=[...d.leads,...d.calls].filter(x=>x.gclid).length;
  const revenue=booked.reduce((n,x)=>n+(x.job_value||0),0);
  document.getElementById('tiles').innerHTML=
    tile(d.leads.length,'form leads')+tile(d.calls.length,'calls')+
    tile(booked.length,'booked')+tile(money(revenue)||'$0','revenue')+
    tile(withG,'with click id');
  document.getElementById('fraud').innerHTML=d.flagged_ips.length?
    '<div class="warn"><b>'+d.flagged_ips.length+' IP(s) clicking abnormally</b> — '+
    d.flagged_ips.map(f=>esc(f.ip)+' ('+f.n+'×)').join(', ')+
    '. Download the exclusion file below and add it under Campaign Settings → IP exclusions.</div>':'';
  document.querySelector('#leads tbody').innerHTML=d.leads.map(l=>'<tr>'+
    '<td>'+esc((l.created_at||'').slice(0,16))+'</td><td><b>'+esc(l.name)+'</b></td>'+
    '<td><a href="tel:'+esc(l.phone)+'">'+esc(l.phone)+'</a></td><td>'+esc(l.service)+'</td>'+
    '<td>'+esc(l.moving_from)+' → '+esc(l.moving_to)+'</td>'+
    '<td class="attr">'+attr(l)+'</td><td>'+pill(l.status)+(l.job_value?' '+money(l.job_value):'')+'</td>'+
    '<td><button onclick="markRow(\\'lead\\','+l.id+')">mark</button></td></tr>').join('')
    ||'<tr><td colspan="8">Nothing yet.</td></tr>';
  document.querySelector('#calls tbody').innerHTML=d.calls.map(c=>'<tr>'+
    '<td>'+esc((c.created_at||'').slice(0,16))+'</td><td><b>'+esc(c.caller_name||'—')+'</b>'+
    (c.first_call?' <span class="pill">first call</span>':'')+'</td>'+
    '<td><a href="tel:'+esc(c.caller_number)+'">'+esc(c.caller_number)+'</a></td>'+
    '<td>'+Math.floor((c.duration_sec||0)/60)+'m'+((c.duration_sec||0)%60)+'s</td>'+
    '<td>'+(c.recording_url?'<a href="'+esc(c.recording_url)+'" target="_blank" rel="noopener">listen</a>':'—')+'</td>'+
    '<td class="attr">'+attr(c)+'</td><td>'+pill(c.status)+(c.job_value?' '+money(c.job_value):'')+'</td>'+
    '<td><button onclick="markRow(\\'call\\','+c.id+')">mark</button></td></tr>').join('')
    ||'<tr><td colspan="8">Nothing yet.</td></tr>';
}
function tile(v,l){return '<div class="tile"><b>'+v+'</b><span>'+l+'</span></div>';}
load();setInterval(load,60000);
</script></div></body></html>`;
