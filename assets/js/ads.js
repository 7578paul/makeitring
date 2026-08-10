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

  // The hero says Paulo is available. That is only worth showing when it is
  // true, so it follows the same window the site already promises everywhere
  // else: a real person within the hour, 7am to 7pm on a working day. Outside
  // it the dot goes grey and the line changes, rather than claiming someone is
  // sitting there at 2am. Hours are Toronto's, not the visitor's, since that is
  // where the phone rings.
  var OPEN_HOUR = 7, CLOSE_HOUR = 19, OFFICE_TZ = "America/Toronto";

  function officeNow() {
    try {
      var parts = new Intl.DateTimeFormat("en-GB", {
        timeZone: OFFICE_TZ, weekday: "short", hour: "numeric", hour12: false
      }).formatToParts(new Date());
      var out = {};
      parts.forEach(function (p) { out[p.type] = p.value; });
      return { day: out.weekday, hour: parseInt(out.hour, 10) };
    } catch (e) {
      return null;  // no Intl or no tz data: leave the markup's default alone
    }
  }

  function initAvailability() {
    var el = document.querySelector("[data-avail]");
    if (!el) return;
    var now = officeNow();
    if (!now || isNaN(now.hour)) return;

    var working = ["Mon", "Tue", "Wed", "Thu", "Fri"].indexOf(now.day) !== -1;
    var open = working && now.hour >= OPEN_HOUR && now.hour < CLOSE_HOUR;
    if (open) return;  // markup already ships in the available state

    el.classList.add("is-away");
    var state = el.querySelector("[data-avail-state]");
    if (state) state.textContent = working && now.hour < OPEN_HOUR
      ? "replies from 7am"
      : "replies first thing";
  }

  document.addEventListener("DOMContentLoaded", function () {
    rememberPlaybook();
    initVideos();
    initSpendPickers();
    initAvailability();
  });
})();
