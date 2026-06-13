/* =========================================================================
   M16 mockup script — chest activation + reveal orchestration + cookie write.
   Look/feel artifact for sign-off. In the REAL build this lives in
   static/gateway.js (D20), depends on theme.js, and calls
   Archive19Theme.choose(theme) instead of writing the cookie inline, then
   navigates to the real /map/horror | /map/sea subpages.
   (REQUIREMENTS §17 / ARCHITECTURE §17, D19-D24.)
   ========================================================================= */
(function () {
  "use strict";

  // Mockup stand-ins for the real /map/{theme} subpages (no backend here).
  var DEST = { horror: "level-horror.html", sea: "level-sea.html" };

  var reveal      = document.getElementById("gw-reveal");
  var revealGhost = document.getElementById("gw-reveal-ghost");
  var revealCake  = document.getElementById("gw-reveal-cake");

  var prefersReduced = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* --- D19/M16R9 contract (mockup inlines what theme.js does for real) ---- */
  function chooseTheme(theme) {
    var oneYear = 60 * 60 * 24 * 365;
    document.cookie = "theme=" + theme + "; path=/; max-age=" + oneYear + "; SameSite=Lax";
    try { window.sessionStorage.setItem("theme", theme); } catch (e) {}
  }

  /* --- resolve which theme a chest leads to (chest2 = random 50/50, D21) -- */
  function resolveTheme(chest) {
    var fixed = chest.getAttribute("data-theme");      // "horror" | "sea" | "random"
    if (fixed === "random") return Math.random() < 0.5 ? "horror" : "sea";
    return fixed;
  }

  function navigateOnce(state) {
    if (state.navigated) return;
    state.navigated = true;
    window.location.assign(DEST[state.theme]);
  }

  function activate(chest) {
    var theme = resolveTheme(chest);   // ONE coin per click drives art AND dest
    chooseTheme(theme);                // cookie + session set BEFORE navigation

    // Reduced motion: skip the reveal entirely, go straight there (D22).
    if (prefersReduced) {
      window.location.assign(DEST[theme]);
      return;
    }

    var state = { theme: theme, navigated: false };

    // open the chest lid
    chest.classList.add("is-opening");

    // arm the reveal overlay with the matching art + veil tint
    reveal.classList.remove("to-horror", "to-sea");
    reveal.classList.add("is-active", theme === "horror" ? "to-horror" : "to-sea");

    var obj = theme === "horror" ? revealGhost : revealCake;
    // restart the animation cleanly
    obj.classList.remove("is-playing");
    void obj.offsetWidth;            // reflow to reset
    obj.classList.add("is-playing");

    // primary handoff: when the zoom animation ends
    obj.addEventListener("animationend", function onEnd(ev) {
      if (ev.animationName === "gw-zoom") {
        obj.removeEventListener("animationend", onEnd);
        navigateOnce(state);
      }
    });

    // guarded fallback timer (R-M16-9 / D24): fires the SAME guarded navigate
    // if animationend never arrives.
    var ms = 1100 + 250;             // --gw-reveal + slack
    window.setTimeout(function () { navigateOnce(state); }, ms);
  }

  // wire all chests: mouse/touch + keyboard (buttons already handle Enter/Space)
  var chests = document.querySelectorAll(".gw-chest");
  chests.forEach(function (chest) {
    chest.addEventListener("click", function () { activate(chest); });
  });
})();
