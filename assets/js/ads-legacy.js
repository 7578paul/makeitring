// Make It Ring — shared behaviour for the legacy ad landing pages
(function () {
  "use strict";


  function initSpendGo() {
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

  // Cleaning-legacy only: the four problem cards collapse to a fade on mobile.
  function initProblemsToggle() {
    var wrap = document.querySelector("[data-probs-wrap]");
    var toggle = document.querySelector("[data-probs-toggle]");
    if (!wrap || !toggle) return;
    var open = false;
    var mq = window.matchMedia("(max-width: 699px)");

    function render() {
      var collapsed = mq.matches && !open;
      wrap.classList.toggle("is-collapsed", collapsed);
      toggle.textContent = open ? "Show less" : "Read all four";
    }
    toggle.addEventListener("click", function () {
      open = !open;
      render();
    });
    mq.addEventListener("change", render);
    render();
  }

  document.addEventListener("DOMContentLoaded", function () {
    initSpendGo();
    initProblemsToggle();
  });
})();
