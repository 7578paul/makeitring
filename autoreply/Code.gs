/**
 * Make It Ring — auto-reply with the playbook that matches the page the
 * enquiry came from.
 *
 * Deployed as a Google Apps Script web app. The website posts the lead's name,
 * email and playbook here, and this replies from the Google account that owns
 * the script, with the right PDF attached.
 *
 * Setup lives in autoreply/SETUP.md.
 */

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

/**
 * Must match AUTOREPLY_SECRET in assets/js/site.js. This is visible in the
 * site's source, so it only deters casual abuse; the real protection is the
 * per-address rate limit in sendAllowed() below.
 */
var SHARED_SECRET = 'qmWwqpKYKenxJcfNK1p7AVZSIRuY2yIx';

var SITE      = 'https://makeitring.co';
var FROM_NAME = 'Paulo Kihara, Make It Ring';
var REPLY_TO  = 'we@makeitring.co';
var SENDER    = 'Paulo Kihara';
var PHONE     = '(647) 475-2404';
var LOGO_URL  = SITE + '/images/logo-make-it-ring-email.png';

/**
 * Which playbook goes with which key. The website decides the key from the page
 * the visitor came through; anything unrecognised falls back to 'local'.
 */
var PLAYBOOKS = {
  local: {
    url:   SITE + '/downloads/make-it-ring-local-checks.pdf',
    file:  'Make It Ring - Local Services Playbook.pdf',
    label: 'local services playbook'
  },
  moving: {
    url:   SITE + '/downloads/make-it-ring-moving-checks.pdf',
    file:  'Make It Ring - Moving Playbook.pdf',
    label: 'moving playbook'
  },
  cleaning: {
    url:   SITE + '/downloads/make-it-ring-cleaning-checks.pdf',
    file:  'Make It Ring - Cleaning Playbook.pdf',
    label: 'cleaning playbook'
  },
  restoration: {
    url:   SITE + '/downloads/make-it-ring-restoration-checks.pdf',
    file:  'Make It Ring - Restoration Playbook.pdf',
    label: 'restoration playbook'
  }
};

var DEFAULT_PLAYBOOK = 'local';

// ---------------------------------------------------------------------------

// Every enquiry is written here before anything is sent, so there is always one
// record that does not depend on FormSubmit, on Gmail, or on this script
// getting as far as an email. The sheet is created on first use; its id is kept
// in script properties so it is found again next time.
function logLead(data) {
  try {
    var props = PropertiesService.getScriptProperties();
    var id = props.getProperty('LEAD_SHEET_ID');
    var ss = null;
    if (id) {
      try { ss = SpreadsheetApp.openById(id); } catch (e) { ss = null; }
    }
    if (!ss) {
      ss = SpreadsheetApp.create('Make It Ring leads');
      props.setProperty('LEAD_SHEET_ID', ss.getId());
      ss.getSheets()[0].appendRow(
        ['When', 'Name', 'Company', 'Phone', 'Email', 'Spend', 'Page', 'What happened']);
    }
    ss.getSheets()[0].appendRow([
      new Date(),
      String(data.name || ''),
      String(data.company || ''),
      String(data.phone || ''),
      String(data.email || ''),
      String(data.spend || ''),
      String(data.playbook || ''),
      data.kind === 'lead_backup' ? 'FormSubmit refused it, backup emailed' : 'enquiry submitted'
    ]);
  } catch (err) {
    // Never let bookkeeping stop the email going out.
    console.error('logLead failed: ' + err);
  }
}

// The lead notification we actually rely on. Sent from our own account, so it
// is not a third party mailing us about ourselves and does not get filtered
// like one. Reply-to is the enquirer, so hitting reply writes to them.
function notifyCompany(data, book, to) {
  var lines = [
    'Name:    ' + (data.name || ''),
    'Company: ' + (data.company || ''),
    'Phone:   ' + (data.phone || ''),
    'Email:   ' + to,
    'Spend:   ' + (data.spend || 'not given'),
    'Page:    ' + (book.label || data.playbook || ''),
    '',
    'They have been sent the ' + book.label + ' and told you will ring today.',
    '',
    'Reply to this email to write straight back to them.'
  ].join('\n');

  GmailApp.sendEmail(
    REPLY_TO,
    'New lead: ' + (data.name || 'unknown') + (data.company ? ' at ' + data.company : ''),
    lines,
    { name: FROM_NAME, replyTo: to }
  );
}

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);

    if (SHARED_SECRET && data.secret !== SHARED_SECRET) {
      return reply({ ok: false, error: 'unauthorised' });
    }

    var to = String(data.email || '').trim();
    if (!/^[^\s@]+@[^\s@]+\.[a-z]{2,}$/i.test(to)) {
      return reply({ ok: false, error: 'invalid address' });
    }

    // Record it first. Everything after this point can fail without losing the
    // enquiry, which is the whole reason the ledger exists.
    logLead(data);

    // Backup channel. The site calls this when FormSubmit refuses the lead, so
    // an outage there does not lose the enquiry. It emails us, not the visitor,
    // and skips the per-address limit below because that guards the visitor's
    // inbox and this never reaches it.
    if (data.kind === 'lead_backup') {
      var lines = [
        'FormSubmit did not accept this enquiry, so the site sent it here instead.',
        '',
        'Name:    ' + (data.name || ''),
        'Company: ' + (data.company || ''),
        'Phone:   ' + (data.phone || ''),
        'Email:   ' + to,
        'Spend:   ' + (data.spend || 'not given'),
        'Page:    ' + (data.playbook || ''),
        '',
        'Why FormSubmit refused it: ' + (data.reason || 'not reported'),
        '',
        'The visitor was told to ring instead, so they may call before you reach them.'
      ].join('\n');
      GmailApp.sendEmail(REPLY_TO, 'LEAD (backup): ' + (data.name || 'unknown') + ' — FormSubmit failed', lines, {
        name: FROM_NAME,
        replyTo: to
      });
      return reply({ ok: true, kind: 'lead_backup' });
    }

    // One auto-reply per address per hour, so the open endpoint cannot be used
    // to mailbomb someone.
    if (!sendAllowed(to)) {
      return reply({ ok: false, error: 'already sent recently' });
    }

    var book  = PLAYBOOKS[String(data.playbook || '')] || PLAYBOOKS[DEFAULT_PLAYBOOK];
    var first = String(data.name || '').trim().split(/\s+/)[0] || 'there';

    var options = {
      name: FROM_NAME,
      replyTo: REPLY_TO,
      htmlBody: htmlBody(first, book)
    };

    var pdf = attachment(book);
    if (pdf) options.attachments = [pdf];

    // Tell us first. FormSubmit's notifications come from their servers rather
    // than our domain, which is why they land in spam; this one is sent by our
    // own account, so it arrives in the inbox. Wrapped separately so neither
    // email can stop the other going out.
    try {
      notifyCompany(data, book, to);
    } catch (err) {
      console.error('company notification failed: ' + err);
    }

    try {
      GmailApp.sendEmail(to, 'Thanks ' + first + ', got your details', textBody(first, book), options);
    } catch (err) {
      console.error('auto-reply failed: ' + err);
      return reply({ ok: false, error: 'notified, auto-reply failed' });
    }
    return reply({ ok: true, playbook: book.label });

  } catch (err) {
    console.error(err);
    return reply({ ok: false, error: String(err) });
  }
}

/** Lets you confirm the deployment is live by opening the URL in a browser. */
function doGet() {
  return reply({ ok: true, service: 'Make It Ring auto-reply' });
}

function attachment(book) {
  try {
    var res = UrlFetchApp.fetch(book.url, { muteHttpExceptions: true });
    if (res.getResponseCode() !== 200) {
      console.error('attachment ' + book.url + ' returned ' + res.getResponseCode());
      return null;
    }
    return res.getBlob().setName(book.file);
  } catch (err) {
    // Never lose the reply just because the file could not be fetched.
    console.error('attachment fetch failed: ' + err);
    return null;
  }
}

function sendAllowed(email) {
  var cache = CacheService.getScriptCache();
  var key = 'sent_' + Utilities.base64EncodeWebSafe(email.toLowerCase());
  if (cache.get(key)) return false;
  cache.put(key, '1', 3600); // seconds
  return true;
}

function reply(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function textBody(first, book) {
  return [
    'Thanks ' + first + ', got your details.',
    '',
    "I'll call you today. If I miss you, I'll text so you know who it was.",
    '',
    "In the meantime I've attached the " + book.label + '. Seven things worth checking in your account whether or not we end up working together.',
    '',
    SENDER,
    PHONE
  ].join('\n');
}

function htmlBody(first, book) {
  var p = 'margin:0 0 16px;font-size:16px;line-height:1.55;color:#333;';
  return '' +
    '<div style="margin:0;padding:24px;background:#e9e9e7;font-family:Helvetica,Arial,sans-serif;">' +
      '<div style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:20px;padding:32px 28px;">' +
        '<img src="' + LOGO_URL + '" alt="Make It Ring" width="150" ' +
             'style="width:150px;max-width:150px;height:auto;display:block;border:0;margin:0 0 26px;">' +
        '<p style="' + p + '">Thanks ' + escapeHtml(first) + ', got your details.</p>' +
        '<p style="' + p + '">I&rsquo;ll call you today. If I miss you, I&rsquo;ll text so you know who it was.</p>' +
        '<p style="' + p + '">In the meantime I&rsquo;ve attached the <strong>' + escapeHtml(book.label) + '</strong>. ' +
          'Seven things worth checking in your account whether or not we end up working together.</p>' +
        '<p style="margin:26px 0 0;padding-top:18px;border-top:1px solid #ececeb;font-size:16px;line-height:1.6;color:#333;">' +
          '<strong>' + SENDER + '</strong><br>' +
          '<a href="tel:+16474752404" style="color:#111;text-decoration:none;">' + PHONE + '</a>' +
        '</p>' +
      '</div>' +
    '</div>';
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
}
