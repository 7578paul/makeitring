// Make It Ring — shared behaviour for the site pages
(function () {
  "use strict";

  var FORM_ENDPOINT = "https://formsubmit.co/ajax/we@makeitring.co";

  // Sticky bottom call bar: shows on mobile once the user scrolls past the hero.
  function initCallBar() {
    var bar = document.querySelector("[data-callbar]");
    if (!bar) return;
    function onScroll() {
      var show = window.scrollY > 620 && window.innerWidth < 700;
      bar.classList.toggle("is-visible", show);
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    onScroll();
  }

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

  // Lead forms: submit via FormSubmit, swap to an inline confirmation panel.
  function initLeadForms() {
    var forms = document.querySelectorAll("[data-lead-form]");
    forms.forEach(function (form) {
      var successId = form.getAttribute("data-lead-form");
      var success = successId ? document.getElementById(successId) : null;
      var submitBtn = form.querySelector("button[type=submit]");

      form.addEventListener("submit", function (e) {
        e.preventDefault();
        if (submitBtn) { submitBtn.disabled = true; submitBtn.dataset.label = submitBtn.textContent; submitBtn.textContent = "Sending…"; }

        var data = {};
        new FormData(form).forEach(function (v, k) { data[k] = v; });
        data._subject = "New enquiry — Make It Ring website";
        data._captcha = "false";

        fetch(FORM_ENDPOINT, {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify(data)
        })
          .then(function () {
            form.hidden = true;
            if (success) success.hidden = false;
          })
          .catch(function () {
            if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = submitBtn.dataset.label; }
            alert("That didn't send — please call us instead, the number is in the header.");
          });
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initCallBar();
    initHeroSpend();
    initLeadForms();
  });
})();
