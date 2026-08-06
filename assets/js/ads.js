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

  document.addEventListener("DOMContentLoaded", function () {
    initSpendPickers();
  });
})();
