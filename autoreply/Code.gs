/**
 * Make It Ring — auto-reply with attachment.
 *
 * Deployed as a Google Apps Script web app. The website posts the lead's
 * details here, and this sends them a reply from the Google account that owns
 * the script, with the attachment included.
 *
 * Setup lives in autoreply/SETUP.md.
 */

// ---------------------------------------------------------------------------
// Settings — edit these four, then redeploy.
// ---------------------------------------------------------------------------

/** Public URL of the file to attach. Leave blank to send with no attachment. */
var ATTACHMENT_URL = 'https://makeitring.co/downloads/make-it-ring.pdf';

/** Filename the recipient sees. */
var ATTACHMENT_NAME = 'Make It Ring.pdf';

/** Subject line of the auto-reply. */
var SUBJECT = 'Thanks — we have your details';

/**
 * Must match AUTOREPLY_SECRET in assets/js/site.js. This is visible in the
 * site's source, so it only deters casual abuse; the real protection is the
 * per-address rate limit in sendAllowed() below.
 */
var SHARED_SECRET = 'CHANGE_ME';

var FROM_NAME = 'Make It Ring';
var REPLY_TO  = 'we@makeitring.co';
var PHONE     = '(647) 475-2404';

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

    var first = String(data.name || '').trim().split(/\s+/)[0] || 'there';

    var options = {
      name: FROM_NAME,
      replyTo: REPLY_TO,
      htmlBody: htmlBody(first)
    };

    var file = attachment();
    if (file) options.attachments = [file];

    GmailApp.sendEmail(to, SUBJECT, textBody(first), options);
    return reply({ ok: true });

  } catch (err) {
    console.error(err);
    return reply({ ok: false, error: String(err) });
  }
}

/** Lets you confirm the deployment is live by opening the URL in a browser. */
function doGet() {
  return reply({ ok: true, service: 'Make It Ring auto-reply' });
}

function attachment() {
  if (!ATTACHMENT_URL) return null;
  try {
    var blob = UrlFetchApp.fetch(ATTACHMENT_URL, { muteHttpExceptions: true }).getBlob();
    return blob.setName(ATTACHMENT_NAME);
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

function textBody(first) {
  return [
    'Hi ' + first + ',',
    '',
    'Thanks — we have your details.',
    '',
    'A real person rings you back within the hour between 7am and 7pm. Outside those hours you are the first call of the next working day. Calls come from ' + PHONE + ', worth saving it.',
    '',
    'Attached is something to read in the meantime.',
    '',
    'Worth having handy for the call: roughly what you spend a month on ads, and who runs them now — you, an agency, or nobody.',
    '',
    'Nothing is invoiced until after that call.',
    '',
    '— Make It Ring',
    PHONE + ' | ' + REPLY_TO + ' | makeitring.co'
  ].join('\n');
}

function htmlBody(first) {
  var accent = '#FF3D00';
  var p = 'margin:0 0 16px;font-size:16px;line-height:1.55;color:#333;';
  return '' +
    '<div style="margin:0;padding:24px;background:#e9e9e7;font-family:Helvetica,Arial,sans-serif;">' +
      '<div style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:20px;padding:32px 28px;">' +
        '<p style="margin:0 0 22px;font-size:22px;font-weight:800;letter-spacing:-0.02em;color:#111;">' +
          'make it <span style="color:' + accent + ';">ring</span>' +
        '</p>' +
        '<p style="' + p + '">Hi ' + escapeHtml(first) + ',</p>' +
        '<p style="' + p + '">Thanks — we have your details.</p>' +
        '<p style="' + p + '">A real person rings you back <strong>within the hour between 7am and 7pm</strong>. ' +
          'Outside those hours you are the first call of the next working day. Calls come from ' +
          '<a href="tel:+16474752404" style="color:#111;font-weight:600;">' + PHONE + '</a>, worth saving it.</p>' +
        '<p style="' + p + '">Attached is something to read in the meantime.</p>' +
        '<p style="' + p + '">Worth having handy for the call: roughly what you spend a month on ads, ' +
          'and who runs them now — you, an agency, or nobody.</p>' +
        '<p style="' + p + 'color:#777;">Nothing is invoiced until after that call.</p>' +
        '<p style="margin:26px 0 0;padding-top:18px;border-top:1px solid #ececeb;font-size:14px;line-height:1.6;color:#999;">' +
          'Make It Ring<br>' +
          '<a href="tel:+16474752404" style="color:#777;">' + PHONE + '</a> &middot; ' +
          '<a href="mailto:' + REPLY_TO + '" style="color:#777;">' + REPLY_TO + '</a> &middot; ' +
          '<a href="https://makeitring.co" style="color:#777;">makeitring.co</a>' +
        '</p>' +
      '</div>' +
    '</div>';
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
}
