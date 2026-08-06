# Auto-reply with attachment — setup

The website is static (GitHub Pages), so it cannot send email itself. This is a
small Google Apps Script web app that does it: the site posts each lead's name
and email to it, and it replies to them with the attachment.

It sends from whichever Google account owns the script, so sign in as
**we@makeitring.co** before you start. Nothing here costs anything, and there is
no API key or DNS record to set up.

While this is not yet configured the site keeps sending FormSubmit's plain-text
auto-reply instead, so leads always get a reply either way.

## 1. Put the attachment on the site

Add the file to the repo at `downloads/` (e.g. `downloads/make-it-ring.pdf`) so
it is reachable at `https://makeitring.co/downloads/make-it-ring.pdf`. Keeping it
in the repo means it is version-controlled and you can also link to it anywhere.

## 2. Create the script

1. Go to <https://script.google.com>, signed in as **we@makeitring.co**.
2. **New project**, then name it "Make It Ring auto-reply".
3. Delete the sample code and paste in everything from `autoreply/Code.gs`.
4. Edit the settings at the top:
   - `ATTACHMENT_URL` — the file's URL from step 1.
   - `ATTACHMENT_NAME` — the filename the recipient sees.
   - `SUBJECT` — the auto-reply's subject line.
   - `SHARED_SECRET` — any random string, e.g. a password generator's output.
5. Save.

## 3. Deploy it

1. **Deploy → New deployment**, and pick type **Web app**.
2. Set **Execute as** to *Me*, and **Who has access** to *Anyone*.
3. **Deploy**. Google asks you to authorise it — it needs permission to send
   mail as you and to fetch the attachment. Approve.
4. Copy the **Web app URL**. It ends in `/exec`.

## 4. Point the site at it

In `assets/js/site.js`, fill in the two constants near the top:

```js
var AUTOREPLY_ENDPOINT = "https://script.google.com/macros/s/AKfy.../exec";
var AUTOREPLY_SECRET = "the same random string you put in Code.gs";
```

Commit and push. Once `AUTOREPLY_ENDPOINT` is set, the site stops asking
FormSubmit for its plain-text reply and uses this instead.

## 5. Test it

Submit the form on the live site with your own email address. You should get the
reply with the file attached, and the lead notification still lands in
we@makeitring.co as before.

If nothing arrives, open the `/exec` URL in a browser — it should return
`{"ok":true,...}`. Then check **Executions** in the Apps Script editor for the
error.

## Notes

- **Whenever you edit `Code.gs`, deploy again** (*Deploy → Manage deployments →
  edit → Version: New version*). Saving alone does not update the live web app.
- The endpoint is public, so the shared secret sits in the site's source and only
  deters casual abuse. The real guard is in the script: it will send at most one
  auto-reply per email address per hour, so it cannot be used to flood someone.
- Gmail caps sending at roughly 500 messages a day on a personal account and
  1,500 on Workspace — far above normal lead volume, but worth knowing.
- If the attachment cannot be fetched the reply still goes out, just without it.
