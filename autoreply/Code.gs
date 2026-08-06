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

    GmailApp.sendEmail(to, 'Thanks ' + first + ', got your details', textBody(first, book), options);
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
