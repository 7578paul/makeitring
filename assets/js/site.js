// Make It Ring — shared behaviour for the site pages
(function () {
  "use strict";

  var FORM_ENDPOINT = "https://formsubmit.co/ajax/we@makeitring.co";

  // Google Apps Script web app that sends the auto-reply with the attachment.
  // Paste the /exec URL here after deploying autoreply/Code.gs — see
  // autoreply/SETUP.md. While this is blank the site falls back to FormSubmit's
  // own plain-text auto-reply below, so a reply always goes out.
  var AUTOREPLY_ENDPOINT = "https://script.google.com/macros/s/AKfycbzx2BWIkOHAE-wKcXcQP8ipnqHgB6H4RQoq_X_k4_0SfWHdyaqgQTejCN34qanrcFA3/exec";
  var AUTOREPLY_SECRET = "qmWwqpKYKenxJcfNK1p7AVZSIRuY2yIx";

  // Which playbook a visitor gets is decided by the page they came through.
  // The ads and service pages have no form of their own — they all send people
  // to book-a-call.html — so each page records itself on load and the form
  // reads it back. Keys must match PLAYBOOKS in autoreply/Code.gs.
  var PLAYBOOK_KEY = "mir_playbook";

  function playbookForPath(path) {
    var file = String(path || "").split("/").pop().toLowerCase();
    if (file.indexOf("cleaning") === 0) return "cleaning";
    if (file.indexOf("moving") === 0) return "moving";
    if (file.indexOf("restoration") === 0) return "restoration";
    return "local";
  }

  function isFormPage(file) {
    return file.indexOf("book-a-call") === 0 || file.indexOf("thank-you") === 0;
  }

  // Record this page, unless it is the form itself — that must not overwrite
  // wherever the visitor came from.
  function rememberPlaybook() {
    var file = String(location.pathname).split("/").pop().toLowerCase();
    if (isFormPage(file)) return;
    try { sessionStorage.setItem(PLAYBOOK_KEY, playbookForPath(location.pathname)); } catch (e) {}
  }

  function currentPlaybook() {
    var file = String(location.pathname).split("/").pop().toLowerCase();
    if (!isFormPage(file)) return playbookForPath(location.pathname);
    try {
      var stored = sessionStorage.getItem(PLAYBOOK_KEY);
      if (stored) return stored;
    } catch (e) {}
    // Session storage blocked or the visitor arrived straight at the form:
    // fall back to whichever page linked here.
    if (document.referrer) {
      try {
        var ref = new URL(document.referrer);
        if (ref.host === location.host) return playbookForPath(ref.pathname);
      } catch (e) {}
    }
    return "local";
  }

  // Fallback auto-reply, used only while AUTOREPLY_ENDPOINT is unset. FormSubmit
  // delivers this to the address in the form's `email` field. Plain text, and it
  // cannot carry an attachment — that is what the Apps Script relay is for.
  var AUTO_REPLY = [
    "Thanks, we have your details.",
    "",
    "A real person rings you back within the hour between 7am and 7pm. Outside those hours you are the first call of the next working day. Calls come from (647) 475-2404, worth saving it.",
    "",
    "Worth having handy for the call: roughly what you spend a month on ads, and who runs them now: you, an agency, or nobody.",
    "",
    "Nothing is invoiced until after that call.",
    "",
    "Make It Ring",
    "(647) 475-2404 | we@makeitring.co | makeitring.co"
  ].join("\n");

  // Carry the landing page's spend answer onto the booking form. Without this
  // the visitor is asked the same question twice, or — as was the case — the
  // answer is stored and then silently dropped, since the booking form had no
  // spend field at all.
  function initSpendFill() {
    var fields = document.querySelectorAll("[data-spend-fill]");
    if (!fields.length) return;
    var stored = "";
    try { stored = sessionStorage.getItem("mir_spend") || ""; } catch (e) {}
    if (!stored) return;
    fields.forEach(function (field) {
      // A dropdown only takes a value it actually offers; a hidden field just
      // carries whatever the landing page recorded.
      if (field.tagName === "SELECT") {
        var match = field.querySelector('option[value="' + stored.replace(/"/g, '\\"') + '"]');
        if (match) field.value = stored;
      } else {
        field.value = stored;
      }
    });
  }

  // Hero "what are you spending" selector: remembers the choice and sends the visitor to Book a call.
  // The picker only carries the answer forward; it is the whole reason the
  // booking form no longer asks. Leaving it unset used to send people on with
  // an empty spend, so it now has to be chosen first.
  function requireSpend(select, button, onOk) {
    // Work out where the message lives once. Looking it up again on the way
    // out searched a different node, so the error never cleared.
    var row = select.closest("[data-spend-pair]") || select.closest(".inputrow");
    var host = (row && row.parentNode) || select.parentNode;
    var msg = null;

    function clear() {
      select.classList.remove("is-invalid");
      select.removeAttribute("aria-invalid");
      if (msg && msg.parentNode) msg.parentNode.removeChild(msg);
      msg = null;
    }

    select.addEventListener("change", function () { if (select.value) clear(); });

    button.addEventListener("click", function () {
      if (!select.value) {
        select.classList.add("is-invalid");
        select.setAttribute("aria-invalid", "true");
        if (!msg) {
          msg = document.createElement("p");
          msg.className = "spend-error";
          msg.setAttribute("role", "alert");
          msg.textContent = "Choose your monthly spend first.";
          host.insertBefore(msg, row ? row.nextSibling : null);
        }
        if (select.focus) select.focus();
        return;
      }
      clear();
      onOk();
    });
  }

  function initHeroSpend() {
    var select = document.querySelector("[data-spend-select]");
    var button = document.querySelector("[data-spend-go]");
    if (!button) return;
    if (!select) { button.addEventListener("click", function () { window.location.href = "book-a-call.html"; }); return; }
    requireSpend(select, button, function () {
      try {
        sessionStorage.setItem("mir_spend", select ? select.value : "");
      } catch (e) {}
      window.location.href = "book-a-call.html";
    });
  }

  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[a-z]{2,}$/i;

  // Field-level rules. Anything else that is `required` just has to be non-empty.
  function fieldProblem(input) {
    var value = (input.value || "").trim();
    var label = (input.getAttribute("data-label") || input.name || "This field");

    if (!value) return "Enter your " + label + ".";

    if (input.name === "email" || input.type === "email") {
      if (!EMAIL_RE.test(value)) return "That email doesn't look right. Check for a typo.";
    }
    if (input.name === "phone" || input.type === "tel") {
      var digits = value.replace(/\D/g, "");
      if (digits.length < 10) return "Enter a full phone number, including the area code.";
      if (digits.length > 15) return "That phone number has too many digits.";
    }
    if (input.name === "name" && value.length < 2) {
      return "Enter your full name.";
    }
    return null;
  }

  function clearError(input) {
    input.classList.remove("is-invalid");
    input.removeAttribute("aria-invalid");
    var msg = input.parentNode.querySelector(".field-error");
    if (msg) msg.parentNode.removeChild(msg);
  }

  function showError(input, message) {
    input.classList.add("is-invalid");
    input.setAttribute("aria-invalid", "true");
    var msg = input.parentNode.querySelector(".field-error");
    if (!msg) {
      msg = document.createElement("p");
      msg.className = "field-error";
      input.parentNode.appendChild(msg);
    }
    msg.textContent = message;
  }

  function setFormAlert(form, message) {
    var alert = form.querySelector(".form-alert");
    if (!message) {
      if (alert) alert.parentNode.removeChild(alert);
      return;
    }
    if (!alert) {
      alert = document.createElement("p");
      alert.className = "form-alert";
      alert.setAttribute("role", "alert");
      form.insertBefore(alert, form.firstChild);
    }
    alert.textContent = message;
  }

  function validate(form) {
    var inputs = form.querySelectorAll("input[required], select[required]");
    var firstBad = null;
    inputs.forEach(function (input) {
      var problem = fieldProblem(input);
      if (problem) {
        showError(input, problem);
        if (!firstBad) firstBad = input;
      } else {
        clearError(input);
      }
    });
    return firstBad;
  }

  // Ask the Apps Script relay to send the auto-reply with its attachment, and
  // to write the enquiry into the ledger. It carries the whole lead rather than
  // just the name and address, so there is always one record of an enquiry that
  // does not depend on FormSubmit having accepted it.
  // Deliberately fire-and-forget: the lead notification goes through FormSubmit
  // regardless, so a problem here must never cost us the enquiry. text/plain
  // keeps it a simple request, so the browser skips the CORS preflight that
  // Apps Script does not answer; keepalive lets it finish after we navigate.
  function sendAutoReply(data) {
    if (!AUTOREPLY_ENDPOINT) return;
    try {
      fetch(AUTOREPLY_ENDPOINT, {
        method: "POST",
        mode: "no-cors",
        keepalive: true,
        headers: { "Content-Type": "text/plain;charset=utf-8" },
        body: JSON.stringify({
          secret: AUTOREPLY_SECRET,
          name: data.name || "",
          company: data.company || "",
          phone: data.phone || "",
          email: data.email || "",
          spend: data.spend || "",
          playbook: currentPlaybook()
        })
      }).catch(function () {});
    } catch (e) {}
  }

  // If FormSubmit will not take the lead, hand the whole thing to the Apps
  // Script relay instead, flagged so it emails us rather than the visitor.
  // Fire and forget for the same reason as the auto-reply: no-cors means we
  // cannot read the result, but a second blind channel beats one.
  function sendLeadBackup(data, reason) {
    if (!AUTOREPLY_ENDPOINT) return;
    try {
      fetch(AUTOREPLY_ENDPOINT, {
        method: "POST",
        mode: "no-cors",
        keepalive: true,
        headers: { "Content-Type": "text/plain;charset=utf-8" },
        body: JSON.stringify({
          secret: AUTOREPLY_SECRET,
          kind: "lead_backup",
          reason: String(reason || "").slice(0, 200),
          name: data.name || "",
          company: data.company || "",
          phone: data.phone || "",
          email: data.email || "",
          spend: data.spend || "",
          playbook: currentPlaybook()
        })
      }).catch(function () {});
    } catch (e) {}
  }

  // Lead forms: validate, submit via FormSubmit, then send the visitor to the thank-you page.
  function initLeadForms() {
    var forms = document.querySelectorAll("[data-lead-form]");
    forms.forEach(function (form) {
      var submitBtn = form.querySelector("button[type=submit]");

      // Use our own messages rather than the browser's bubbles.
      form.setAttribute("novalidate", "novalidate");

      // Clear a field's error as soon as it becomes valid again.
      form.addEventListener("input", function (e) {
        var input = e.target;
        if (input.classList && input.classList.contains("is-invalid") && !fieldProblem(input)) {
          clearError(input);
          if (!form.querySelector(".is-invalid")) setFormAlert(form, null);
        }
      });

      form.addEventListener("submit", function (e) {
        e.preventDefault();

        var firstBad = validate(form);
        if (firstBad) {
          setFormAlert(form, "Please check the fields marked below.");
          firstBad.focus();
          if (firstBad.scrollIntoView) firstBad.scrollIntoView({ block: "center", behavior: "smooth" });
          return;
        }
        setFormAlert(form, null);

        if (submitBtn) { submitBtn.disabled = true; submitBtn.dataset.label = submitBtn.textContent; submitBtn.textContent = "Sending…"; }

        var data = {};
        new FormData(form).forEach(function (v, k) { data[k] = v; });
        data._subject = "New enquiry from the Make It Ring website";
        data._captcha = "false";
        if (!AUTOREPLY_ENDPOINT) data._autoresponse = AUTO_REPLY;

        sendAutoReply(data);

        fetch(FORM_ENDPOINT, {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify(data)
        })
          // fetch only rejects when the browser cannot reach the host at all.
          // A 403 for an unactivated address, a 422 for rate limiting, a 500:
          // all of those resolve, and treating them as success sent people to
          // the thank-you page, counted a conversion and delivered no email.
          // The status and FormSubmit's own success flag both have to say yes.
          .then(function (res) {
            return res.text().then(function (body) {
              var ok = res.ok;
              if (ok) {
                try {
                  var parsed = JSON.parse(body);
                  if (parsed && "success" in parsed) ok = String(parsed.success) === "true";
                } catch (e) {}
              }
              if (!ok) throw new Error("formsubmit " + res.status + " " + body.slice(0, 140));
              return true;
            });
          })
          .then(function () {
            try {
              sessionStorage.setItem("mir_pending_lead", JSON.stringify({
                service: currentPlaybook(),
                spend_band: spendBand(data.spend || ""),
                form_id: form.id === "lead-form" ? "booking" : "home"
              }));
            } catch (e) {}
            window.location.href = "thank-you.html";
          })
          .catch(function (err) {
            // Second channel, so a FormSubmit outage does not lose the enquiry.
            sendLeadBackup(data, err && err.message);
            if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = submitBtn.dataset.label; }
            setFormAlert(form, "That didn't send. Please call (647) 475-2404 so we don't miss you.");
          });
      });
    });
  }

  // The conversion is the visitor landing on the thank-you page, not the submit
  // itself — it survives ad blockers better and is what Google Ads imports.
  // Fires once per submission: the flag is cleared as soon as it is read, so a
  // refresh or a back-button return does not double-count.
  function initConversion() {
    var file = String(location.pathname).split("/").pop().toLowerCase();
    if (file.indexOf("thank-you") !== 0) return;

    var pending = "";
    try { pending = sessionStorage.getItem("mir_pending_lead") || ""; } catch (e) {}
    if (!pending) return;
    try { sessionStorage.removeItem("mir_pending_lead"); } catch (e) {}

    var data = {};
    try { data = JSON.parse(pending); } catch (e) { data = {}; }

    // No personal data here — see analytics/TAXONOMY.md.
    gtag("event", "generate_lead", {
      service: data.service || "local",
      spend_band: data.spend_band || "unset",
      form_id: data.form_id || "booking",
      page_type: "thank_you"
    });

    // Meta's equivalent, fired from here rather than its own handler because
    // the flag above is cleared on read: a second reader would find nothing.
    // Same one-shot guard, so a refresh does not count twice. No personal data.
    if (typeof fbq === "function") {
      fbq("track", "Lead", {
        content_category: data.service || "local",
        content_name: data.form_id || "booking"
      });
    }
  }

  // Spend values are normalised so the display wording can change without
  // splitting the reporting history.
  function spendBand(value) {
    if (value === "3-5k") return "3_5k";
    if (value === "5-10k") return "5_10k";
    if (value === "10k+") return "10k_plus";
    return "unset";
  }

  // Testimonial videos: HLS from Cloudflare Stream, click to play. Nothing is
  // fetched until the visitor asks for it — preload="none" plus a lazily loaded
  // player library, so the videos cost nothing on page load. This mirrors the
  // same block in ads.js; the two bundles are deliberately independent.
  var HLS_LIB = "assets/js/vendor/hls.light.min.js";
  var hlsLoading = null;

  function loadHls() {
    if (window.Hls) return Promise.resolve(window.Hls);
    if (hlsLoading) return hlsLoading;
    hlsLoading = new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = HLS_LIB;
      s.onload = function () { resolve(window.Hls); };
      s.onerror = reject;
      document.head.appendChild(s);
    });
    return hlsLoading;
  }

  function initVideos() {
    var wraps = document.querySelectorAll("[data-vid]");
    wraps.forEach(function (wrap) {
      var video = wrap.querySelector("[data-vid-el]");
      var button = wrap.querySelector("[data-vid-play]");
      var source = wrap.querySelector("[data-vid-src]");
      if (!video || !button || !source) return;
      var url = source.getAttribute("data-vid-src");
      var started = false;

      function start() {
        if (started) return;
        started = true;
        wrap.classList.add("is-playing");
        video.controls = true;

        // Safari and iOS play HLS natively; everyone else needs the library.
        if (video.canPlayType("application/vnd.apple.mpegurl")) {
          video.src = url;
          video.play();
          return;
        }
        loadHls().then(function (Hls) {
          if (Hls && Hls.isSupported()) {
            var hls = new Hls();
            hls.loadSource(url);
            hls.attachMedia(video);
            hls.on(Hls.Events.MANIFEST_PARSED, function () { video.play(); });
          } else {
            video.src = url;
            video.play();
          }
        }).catch(function () {
          wrap.classList.remove("is-playing");
          started = false;
        });
      }

      button.addEventListener("click", start);
    });
  }

  // The thank-you page hands over the playbook straight away rather than making
  // people wait for the email. Which one they get is decided the same way the
  // email decides it, so the two always agree. Keys match PLAYBOOKS in
  // autoreply/Code.gs; the markup ships with the general one, so a visitor with
  // no session still gets a working download.
  var PLAYBOOK_FILES = {
    local:       { slug: "local",       file: "Make It Ring - Local Services Playbook.pdf", title: "your local services playbook" },
    moving:      { slug: "moving",      file: "Make It Ring - Moving Playbook.pdf",         title: "your moving playbook" },
    cleaning:    { slug: "cleaning",    file: "Make It Ring - Cleaning Playbook.pdf",       title: "your cleaning playbook" },
    restoration: { slug: "restoration", file: "Make It Ring - Restoration Playbook.pdf",    title: "your restoration playbook" }
  };

  function initPlaybookOffer() {
    var link = document.querySelector("[data-playbook-link]");
    if (!link) return;

    var key = currentPlaybook();
    var book = PLAYBOOK_FILES[key] || PLAYBOOK_FILES.local;

    link.setAttribute("href", "downloads/make-it-ring-" + book.slug + "-checks.pdf");
    link.setAttribute("download", book.file);

    var title = document.querySelector("[data-playbook-title]");
    if (title) title.textContent = book.title;

    // No personal data — see analytics/TAXONOMY.md.
    link.addEventListener("click", function () {
      if (typeof gtag !== "function") return;
      gtag("event", "file_download", {
        file_name: book.file,
        service: key,
        page_type: "thank_you"
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initConversion();
    rememberPlaybook();
    initSpendFill();
    initHeroSpend();
    initLeadForms();
    initVideos();
    initPlaybookOffer();
  });
})();
