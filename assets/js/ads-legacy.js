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
    initSpendGo();
    initProblemsToggle();
  });
})();
