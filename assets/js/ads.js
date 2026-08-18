// Make It Ring — shared behaviour for the v2 ad landing pages
(function () {
  "use strict";


  // There are two "what are you spending" pickers on these pages (hero + final CTA).
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

  function initSpendPickers() {
    var pairs = document.querySelectorAll("[data-spend-pair]");
    pairs.forEach(function (pair) {
      var select = pair.querySelector("[data-spend-select]");
      var button = pair.querySelector("[data-spend-go]");
      if (!button) return;
    if (!select) { button.addEventListener("click", function () { window.location.href = "book-a-call.html"; }); return; }
      if (!select) { button.addEventListener("click", function () { window.location.href = "book-a-call.html"; }); return; }
      requireSpend(select, button, function () {
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

  // Testimonial videos: HLS from Cloudflare Stream, click to play. Nothing is
  // fetched until the visitor asks for it — preload="none" plus a lazily loaded
  // player library, so the videos cost nothing on page load.
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

  document.addEventListener("DOMContentLoaded", function () {
    rememberPlaybook();
    initVideos();
    initSpendPickers();
  });
})();
