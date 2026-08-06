// Make It Ring — shared behaviour for the v2 ad landing pages
(function () {
  "use strict";


  // There are two "what are you spending" pickers on these pages (hero + final CTA).
  function initSpendPickers() {
    var pairs = document.querySelectorAll("[data-spend-pair]");
    pairs.forEach(function (pair) {
      var select = pair.querySelector("[data-spend-select]");
      var button = pair.querySelector("[data-spend-go]");
      if (!button) return;
      button.addEventListener("click", function () {
        try {
          sessionStorage.setItem("mir_spend", select ? select.value : "");
        } catch (e) {}
        window.location.href = "book-a-call.html";
      });
    });
  }

  // Record which playbook this page maps to, so book-a-call.html can attach the
  // right one to the auto-reply. These pages have no form of their own. Keys
  // must match PLAYBOOKS in autoreply/Code.gs.
  function rememberPlaybook() {
    var file = String(location.pathname).split("/").pop().toLowerCase();
    if (file.indexOf("book-a-call") === 0 || file.indexOf("thank-you") === 0) return;
    var key = "local";
    if (file.indexOf("cleaning") === 0) key = "cleaning";
    else if (file.indexOf("moving") === 0) key = "moving";
    else if (file.indexOf("restoration") === 0) key = "restoration";
    try { sessionStorage.setItem("mir_playbook", key); } catch (e) {}
  }

  document.addEventListener("DOMContentLoaded", function () {
    rememberPlaybook();
    initSpendPickers();
  });
})();
