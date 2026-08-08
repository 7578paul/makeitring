/* ============================================================
   Everything beyond the campaigns themselves. Ported from the
   Python engine so the browser produces the same package.
   ============================================================ */

/* ---------- match semantics: would this negative block this query? ---------- */
function normQ(t){ return String(t||'').toLowerCase().replace(/[^\w\s]/g,' ').split(/\s+/).filter(Boolean).join(' '); }

function blocksQuery(negative, match, query){
  const n = normQ(negative), q = normQ(query);
  if (!n || !q) return false;
  if (match === 'exact') return n === q;
  if (match === 'phrase') return (' ' + q + ' ').indexOf(' ' + n + ' ') !== -1;
  const words = new Set(q.split(' '));
  return n.split(' ').every(w => words.has(w));
}

/* An inherited list always carries terms wrong for a new client — that is
   routine, not exceptional. Drop exactly the offenders and say which. */
function resolveNegatives(negatives, targets){
  const kept = [], removed = [];
  negatives.forEach(([text, match]) => {
    const hit = targets.find(t => blocksQuery(text, match, t));
    if (hit) removed.push('"' + text + '" [' + match + '] would have blocked "' + hit + '"');
    else kept.push([text, match]);
  });
  return {kept, removed};
}

/* ---------- competitor wall (Layer 2) ---------- */
const GENERIC_WORDS = new Set(['moving','movers','mover','move','moves','company','companies',
  'co','services','service','inc','llc','ltd','corp','group','and','the','of','a','storage',
  'transport','logistics','van','lines','removals','relocation','relocations','packing',
  'delivery','solutions']);

function nameVariants(name){
  const base = normQ(name), out = new Set([base]);
  [[/\btwo\b/g,'2'],[/\bthree\b/g,'3'],[/\bone\b/g,'1'],[/\band\b/g,'&'],[/&/g,'and']]
    .forEach(([re, to]) => { const v = normQ(base.replace(re, to)); if (v !== base) out.add(v); });
  out.add(base.replace(/ /g,''));
  return [...out].filter(v => v && v.length > 3);
}

function competitorNegatives(names, ownKeywords, brandTerms, cities){
  const placeWords = new Set();
  cities.forEach(c => normQ(c).split(' ').forEach(w => placeWords.add(w)));
  const own = ownKeywords.concat(brandTerms, cities).map(normQ);
  const negatives = [], rejected = [], seen = new Set();

  names.forEach(name => {
    const words = normQ(name).split(' ');
    const distinctive = words.filter(w => !GENERIC_WORDS.has(w) && !placeWords.has(w));
    if (!distinctive.length || words.length < 2){
      rejected.push('"' + name + '" — a place plus trade words, not a brand: the client wants this search');
      return;
    }
    nameVariants(name).forEach(v => {
      if (seen.has(v)) return;
      seen.add(v);
      const hit = own.find(t => blocksQuery(v, 'exact', t));
      if (hit) rejected.push('"' + v + '" — would block the client\'s own "' + hit + '"');
      else negatives.push(v);
    });
  });
  return {negatives, rejected};
}

/* ---------- landing page ---------- */
const ATTRIBUTION = `
(function () {
  var FIELDS = ['gclid','gbraid','wbraid','campaign','content','keyword',
                'utm_source','utm_medium','utm_campaign','utm_term'];
  var KEY = 'attribution';
  function read(){
    var p = new URLSearchParams(location.search), f = {};
    FIELDS.forEach(function(k){ if (p.get(k)) f[k] = p.get(k); });
    return f;
  }
  var stored = {};
  try { stored = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch(e){}
  var fresh = read();
  if (Object.keys(fresh).length){
    fresh.landed_at = new Date().toISOString();
    if (!stored.gclid || fresh.gclid){
      stored = fresh;
      try { localStorage.setItem(KEY, JSON.stringify(stored)); } catch(e){}
    }
  }
  function fill(){
    document.querySelectorAll('form[data-lead]').forEach(function(form){
      Object.keys(stored).forEach(function(k){
        if (form.querySelector('[name="' + k + '"]')) return;
        var i = document.createElement('input');
        i.type = 'hidden'; i.name = k; i.value = stored[k];
        form.appendChild(i);
      });
    });
  }
  document.addEventListener('DOMContentLoaded', fill); fill();
})();`;

function pageCSS(accent){
  return `*{box-sizing:border-box}
:root{--accent:${accent};--ink:#141210;--muted:#5f584f;--line:#e5e0d8;--bg:#faf8f5;--card:#fff}
body{margin:0;font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg)}
.wrap{max-width:1120px;margin:0 auto;padding:0 20px}
header{background:var(--card);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:20}
.bar{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:12px 0}
.brand{font-weight:800;font-size:19px;letter-spacing:-.02em}
.tel{display:inline-flex;align-items:center;gap:8px;background:var(--accent);color:#fff;text-decoration:none;font-weight:800;padding:11px 18px;border-radius:999px;white-space:nowrap}
.hero{display:grid;gap:34px;grid-template-columns:1.15fr .85fr;padding:44px 0 40px;align-items:start}
@media(max-width:860px){.hero{grid-template-columns:1fr;padding:26px 0}}
h1{font-size:clamp(30px,4.6vw,46px);line-height:1.06;letter-spacing:-.035em;margin:0 0 14px;text-wrap:balance}
.lede{font-size:18.5px;color:var(--muted);margin:0 0 20px;max-width:44ch}
.stars{color:#f5a623;letter-spacing:2px;font-size:17px}
.rating{display:flex;align-items:center;gap:10px;margin:0 0 18px;font-size:14.5px;color:var(--muted)}
.badges{display:flex;flex-wrap:wrap;gap:8px;margin:22px 0 0;padding:0;list-style:none}
.badges li{background:var(--card);border:1px solid var(--line);border-radius:999px;padding:7px 14px;font-size:13.5px;font-weight:600}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:26px;box-shadow:0 1px 2px rgba(20,18,16,.04),0 12px 32px rgba(20,18,16,.07)}
.card h2{margin:0 0 4px;font-size:22px;letter-spacing:-.02em}
.card p.sub{margin:0 0 18px;color:var(--muted);font-size:14.5px}
label{display:block;font-size:13px;font-weight:700;margin:0 0 5px}
input,select{width:100%;padding:12px 13px;font:inherit;font-size:15.5px;border:1px solid var(--line);border-radius:9px;background:#fff;color:var(--ink)}
input:focus,select:focus{outline:2.5px solid var(--accent);outline-offset:-1px}
.row{margin:0 0 13px}.two{display:grid;gap:13px;grid-template-columns:1fr 1fr}
button{width:100%;background:var(--accent);color:#fff;border:0;border-radius:999px;padding:15px;font:inherit;font-weight:800;font-size:17px;cursor:pointer;margin-top:6px}
.callback{text-align:center;margin:13px 0 0;font-size:14px;color:var(--muted)}
.callback a{color:var(--accent);font-weight:700}
section.band{background:var(--card);border-top:1px solid var(--line);padding:44px 0}
h2.sec{font-size:clamp(23px,3vw,31px);letter-spacing:-.025em;margin:0 0 22px}
.g3{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}
.rev{background:var(--bg);border:1px solid var(--line);border-radius:13px;padding:20px}
.rev p{margin:9px 0 12px;font-size:15.5px}
.svc{display:flex;flex-wrap:wrap;gap:9px;list-style:none;padding:0;margin:0}
.svc li{background:var(--bg);border:1px solid var(--line);border-radius:9px;padding:11px 16px;font-weight:600;font-size:15px}
footer{padding:30px 0;color:var(--muted);font-size:13.5px;text-align:center}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}`;
}

function trackingHead(t){
  const out = [];
  if (t.gtm) out.push(`<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
})(window,document,'script','dataLayer','${t.gtm}');<\/script>`);
  const tags = [t.ga4, t.awid].filter(Boolean);
  if (tags.length) out.push(`<script async src="https://www.googletagmanager.com/gtag/js?id=${tags[0]}"><\/script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}
gtag('js',new Date());
${tags.map(x => "gtag('config','" + x + "');").join('\n')}<\/script>`);
  if (t.callrail) out.push(`<script async src="${t.callrail}"><\/script>`);
  return out.join('\n');
}

function landingPage(b, page){
  const tel = (b.phone||'').replace(/[^\d+]/g,'');
  const city = b.cities[0] || 'your area';
  const head = trackingHead(b.tracking);
  const noscript = b.tracking.gtm
    ? `<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=${b.tracking.gtm}" height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>` : '';

  if (page === 'thank-you'){
    const conv = (b.tracking.awid && b.tracking.awlabel)
      ? `gtag('event','conversion',{'send_to':'${b.tracking.awid}/${b.tracking.awlabel}'});`
      : '/* Ads conversion label not set yet */';
    return `<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Thank you — ${esc(b.business)}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
${head}<style>${pageCSS(b.accent)}</style></head><body>${noscript}
<header><div class="wrap bar"><span class="brand">${esc(b.business)}</span>
<a class="tel" href="tel:${tel}">${esc(b.phone)}</a></div></header>
<div class="wrap" style="padding:70px 20px;text-align:center;max-width:640px">
<h1>Thanks — we've got it.</h1>
<p class="lede" style="margin:0 auto 22px">One of our team will call you shortly.
If it's urgent, ring us now and we'll pick up.</p>
<a class="tel" href="tel:${tel}" style="font-size:18px;padding:15px 26px">${esc(b.phone)}</a></div>
<footer><div class="wrap">© ${esc(b.business)}</div></footer>
<script>
(function(){
  if (!sessionStorage.getItem('lead_submitted')) return;
  sessionStorage.removeItem('lead_submitted');
  if (window.gtag){ gtag('event','generate_lead',{currency:'${b.currency}',value:1}); ${conv} }
  window.dataLayer = window.dataLayer || []; window.dataLayer.push({event:'generate_lead'});
})();
<\/script></body></html>`;
  }

  const services = (b.services_list||[]);
  const opts = services.length ? services.map(s => `<option>${esc(s)}</option>`).join('')
                               : '<option>Local move</option><option>Long distance</option>';
  const badges = (b.badges||[]).map(x => `<li>${esc(x)}</li>`).join('');
  const revs = (b.quotes||[]).map(q =>
    `<div class="rev"><div class="stars" aria-hidden="true">★★★★★</div>
     <p>“${esc(q.quote)}”</p><b>${esc(q.name)}</b></div>`).join('');

  return `<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>${esc(b.business)} — ${esc(city)} Movers | ${esc(b.offer||'Free quote')}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="${esc(b.business)}. ${esc(b.offer||'Free quote')}. Call ${esc(b.phone)}.">
${head}<style>${pageCSS(b.accent)}</style>
<script>${ATTRIBUTION}<\/script></head><body>${noscript}
<header><div class="wrap bar"><span class="brand">${esc(b.business)}</span>
<a class="tel" href="tel:${tel}"><span aria-hidden="true">📞</span><span>${esc(b.phone)}</span></a></div></header>
<div class="wrap"><div class="hero"><div>
<h1>${esc(b.lpHeadline || (city + ' movers who quote it straight'))}</h1>
<div class="rating"><span class="stars" aria-hidden="true">★★★★★</span>
<span><b>${esc(b.rating)}</b>${b.reviewCount ? ' from ' + esc(b.reviewCount) + ' reviews' : ''}</span></div>
<p class="lede">Upfront pricing, no surprises on moving day. Tell us about your move and
we'll come back with a written quote.</p>
<ul class="badges">${badges}</ul></div>
<div class="card"><h2>${esc(b.offer || 'Free quote')}</h2>
<p class="sub">Takes about a minute. No obligation.</p>
<form data-lead method="post" action="${esc(b.leadEndpoint || '#')}">
<div class="row"><label for="nm">Your name</label><input id="nm" name="name" required autocomplete="name"></div>
<div class="two"><div class="row"><label for="ph">Phone</label><input id="ph" name="phone" type="tel" required autocomplete="tel"></div>
<div class="row"><label for="em">Email</label><input id="em" name="email" type="email" autocomplete="email"></div></div>
<div class="two"><div class="row"><label for="fr">Moving from</label><input id="fr" name="moving_from" placeholder="${esc(city)}"></div>
<div class="row"><label for="to">Moving to</label><input id="to" name="moving_to"></div></div>
<div class="row"><label for="sv">What do you need?</label><select id="sv" name="service">${opts}</select></div>
<div class="row"><label for="dt">Move date</label><input id="dt" name="move_date" type="date"></div>
<label class="sr" for="hp">Leave blank</label><input class="sr" id="hp" name="company_website" tabindex="-1" autocomplete="off">
<button type="submit">Get my quote</button>
<p class="callback">Rather talk? <a href="tel:${tel}">Call ${esc(b.phone)}</a></p>
</form></div></div></div>
${services.length ? `<section class="band"><div class="wrap"><h2 class="sec">What we move</h2>
<ul class="svc">${services.map(s => '<li>' + esc(s) + '</li>').join('')}</ul></div></section>` : ''}
${revs ? `<section class="band"><div class="wrap"><h2 class="sec">What customers say</h2>
<div class="g3">${revs}</div></div></section>` : ''}
<footer><div class="wrap">© ${esc(b.business)} · ${esc(b.phone)}</div></footer>
<script>
document.querySelector('form[data-lead]').addEventListener('submit', function(e){
  if (this.company_website.value){ e.preventDefault(); return; }
  sessionStorage.setItem('lead_submitted','1');
});
<\/script></body></html>`;
}

/* ---------- the documents ---------- */
function summaryMd(plan, b, layer2, removed){
  const groups = plan.campaigns.reduce((n,c) => n + c.groups.length, 0);
  const kws = plan.campaigns.reduce((n,c) => n + c.groups.reduce((m,g) => m + g.keywords.length, 0), 0);
  const negs = new Set();
  plan.campaigns.forEach(c => c.negatives.forEach(n => negs.add(n.text + '|' + n.match)));
  const daily = plan.campaigns.reduce((n,c) => n + c.budget, 0);

  let out = `# ${plan.business} — what was built\n\n`;
  out += `- **${plan.campaigns.length} campaigns**, ${groups} ad groups, ${kws} keywords\n`;
  out += `- **${negs.size.toLocaleString()} distinct negatives**\n`;
  out += `- **${daily.toFixed(2)} ${plan.currency}/day** (${Math.round(daily*30.4).toLocaleString()}/month)\n\n`;
  out += `Everything imports **paused**. Nothing spends until a human enables it.\n\n`;
  out += `## Campaigns\n\n| Campaign | Daily | Target CPA | Ad groups | Keywords |\n| --- | ---: | ---: | ---: | ---: |\n`;
  plan.campaigns.forEach(c => {
    out += `| ${c.name.replace(/\|/g,'\\|')} | ${c.budget.toFixed(2)} | ${c.targetCpa || '—'} | ${c.groups.length} | ${c.groups.reduce((m,g)=>m+g.keywords.length,0)} |\n`;
  });
  if (layer2 && layer2.negatives.length){
    out += `\n## Competitor wall\n\n${layer2.negatives.length} exact negatives from ${layer2.count} businesses.\n`;
    if (layer2.rejected.length){
      out += `\nRejected, because they would have cost the client traffic:\n\n`;
      layer2.rejected.slice(0,15).forEach(r => out += `- ${r}\n`);
    }
  }
  if (removed && removed.length){
    out += `\n## Negatives removed for this client\n\n`;
    removed.slice(0,20).forEach(r => out += `- ${r}\n`);
  }
  return out;
}

function checklistMd(plan, b){
  const box = (done, t) => `- [${done ? 'x' : ' '}] ${t}\n`;
  const t = b.tracking;
  let out = `# Launch checklist — ${b.business}\n\n`;
  out += `The campaign file covers what Google Ads Editor can import. These are the steps\n`;
  out += `it cannot, and skipping them is how an account ends up optimising toward nothing.\n\n`;
  out += `## 1. Before anything goes live\n\n`;
  out += box(!!t.gtm, 'GTM container installed on the site' + (t.gtm ? ' — `' + t.gtm + '`' : ' — **container ID still needed**'));
  out += box(!!t.ga4, 'GA4 property created and linked to Google Ads' + (t.ga4 ? ' — `' + t.ga4 + '`' : ' — **measurement ID still needed**'));
  out += box(!!t.callrail, 'Call tracking live, with dynamic number insertion on the site');
  out += box(!!b.callTrackingNumber, 'Call asset uses a **tracking** number, not the public one');
  out += box(false, `Tracking number is in **${b.business}'s** name, not the agency's`);
  out += box(false, 'If their current number is on trucks or the Google Business Profile, **port it**');
  out += `\n## 2. Conversions — Editor cannot do this part\n\n`;
  out += box(false, 'Create the "Leads" conversion — Category **Contact**, Count **Every**, click window **60 days**, attribution **Data-driven**, set **Primary**');
  out += box(false, 'Demote or delete every other conversion, so smart bidding gets one clean signal');
  out += box(false, 'Import the call-tracking lead definition (calls over 60 seconds) as a conversion');
  out += box(false, 'Confirm a test lead appears in Google Ads before enabling anything');
  out += `\n## 3. Turn Google's automation off\n\n`;
  out += box(false, 'Settings → Recommendations → auto-apply: turn **all** of them off');
  out += box(false, 'Confirm Search Partners and Display are off on every campaign');
  out += `\n## 4. Import\n\n`;
  out += box(false, 'Google Ads Editor → Account → Import → From file → `campaigns_editor_import.csv`');
  out += box(false, '**Confirm the EU political ads declaration** — Google blocks posting until this is answered once per account');
  out += box(false, 'Review every campaign in Editor. **Do not post until it reads correctly**');
  out += box(false, 'Post. Everything arrives paused');
  out += box(false, 'Tools → Shared library → Negative keyword lists → import `shared_negative_list.csv`, attach to all campaigns');
  out += box(false, 'Add at least 3 image assets — photos of real crews and trucks beat stock');
  out += `\n## 5. Landing page\n\n`;
  out += box(false, `Deploy \`index.html\` and \`thank-you.html\` to **${b.subdomain || 'go.theirdomain.com'}**`);
  out += box(false, `Ask the client to add one DNS record: CNAME → your hosting`);
  out += box(false, 'Load it with `?gclid=test123` and confirm the hidden field appears');
  out += box(!!b.leadEndpoint, 'Submit a test lead and confirm it arrives' + (b.leadEndpoint ? '' : ' — **no lead destination set**'));
  out += `\n## 6. Going live\n\n`;
  out += box(false, 'Enable campaigns one at a time, starting with the core market');
  out += box(false, 'Read the search terms report **daily** for the first 14 days');
  out += box(false, 'Scale budget in steps of 20% or less, only once CPA holds');
  out += box(false, 'Never change target CPA and budget on the same day');
  out += `\n## Warnings to ignore\n\n`;
  out += `Google reports these as faults. Every one is a deliberate choice:\n\n`;
  out += `- **"Search Partners disabled"** — off on purpose, a different and worse audience\n`;
  out += `- **"Display Network expansion disabled"** — off on purpose\n`;
  out += `- **"Upgrade your keywords to broad match"** — the negative wall does the filtering\n`;
  return out;
}
