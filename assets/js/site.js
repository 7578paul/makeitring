// Make It Ring — shared behaviour for the site pages
(function () {
  "use strict";

  var FORM_ENDPOINT = "https://formsubmit.co/ajax/we@makeitring.co";

  // Google Apps Script web app that sends the auto-reply with the attachment.
  // Paste the /exec URL here after deploying autoreply/Code.gs — see
  // autoreply/SETUP.md. While this is blank the site falls back to FormSubmit's
  // own plain-text auto-reply below, so a reply always goes out.
  var AUTOREPLY_ENDPOINT = "";
  var AUTOREPLY_SECRET = "CHANGE_ME";

  // Fallback auto-reply, used only while AUTOREPLY_ENDPOINT is unset. FormSubmit
  // delivers this to the address in the form's `email` field. Plain text, and it
  // cannot carry an attachment — that is what the Apps Script relay is for.
  var AUTO_REPLY = [
    "Thanks — we have your details.",
    "",
    "A real person rings you back within the hour between 7am and 7pm. Outside those hours you are the first call of the next working day. Calls come from (647) 475-2404, worth saving it.",
    "",
    "Worth having handy for the call: roughly what you spend a month on ads, and who runs them now — you, an agency, or nobody.",
    "",
    "Nothing is invoiced until after that call.",
    "",
    "— Make It Ring",
    "(647) 475-2404 | we@makeitring.co | makeitring.co"
  ].join("\n");

  // Hero "what are you spending" selector: remembers the choice and sends the visitor to Book a call.
  function initHeroSpend() {
    var select = document.querySelector("[data-spend-select]");
    var button = document.querySelector("[data-spend-go]");
    if (!button) return;
    button.addEventListener("click", function () {
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
      if (!EMAIL_RE.test(value)) return "That email doesn't look right — check for a typo.";
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

  // Ask the Apps Script relay to send the auto-reply with its attachment.
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
          email: data.email || ""
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
        data._subject = "New enquiry — Make It Ring website";
        data._captcha = "false";
        if (!AUTOREPLY_ENDPOINT) data._autoresponse = AUTO_REPLY;

        sendAutoReply(data);

        fetch(FORM_ENDPOINT, {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify(data)
        })
          .then(function () {
            window.location.href = "thank-you.html";
          })
          .catch(function () {
            if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = submitBtn.dataset.label; }
            setFormAlert(form, "That didn't send. Please call (647) 475-2404 instead.");
          });
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initHeroSpend();
    initLeadForms();
  });
})();
