/* =========================================================================
   Archive 19 — M16 chest-chooser GATEWAY orchestrator (D19-D24)

   Lives on the neutral gateway (`/`, templates/gateway.html). Depends on
   static/theme.js (Archive19Theme.choose — cookie+session, NO reload) and,
   optionally, static/audio-engine.js for the gateway ambient bed.

   Flow per chest activation:
     1. resolve the theme (chest 2 = ONE Math.random()<0.5 coin → art AND dest)
     2. Archive19Theme.choose(theme)   — write cookie+session BEFORE navigating
     3. reduced-motion → location.assign(dest) immediately
     4. else → play the open→emerge→zoom reveal; on the zoom's animationend
        (with a guarded fallback timer) → location.assign(dest)

   Defensive throughout: a missing audio file, a missing Archive19Theme, or a
   reveal that never fires animationend must all degrade silently without
   breaking the navigation.
   ========================================================================= */
(function () {
  "use strict";

  // Real map subpages (D14/D15) — replace the mockup's level-*.html stand-ins.
  var DEST = { horror: "/map/horror", sea: "/map/sea" };

  var reveal = document.getElementById("gw-reveal");
  var revealGhost = document.getElementById("gw-reveal-ghost");
  var revealCake = document.getElementById("gw-reveal-cake");

  var prefersReduced =
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* --- cookie + session, reusing the shared theme.js contract (D19) ------- */
  function chooseTheme(theme) {
    try {
      if (window.Archive19Theme && typeof window.Archive19Theme.choose === "function") {
        window.Archive19Theme.choose(theme);
      }
    } catch (e) {
      /* never block navigation on a persistence hiccup */
    }
  }

  /* --- resolve which theme a chest leads to (chest2 = random 50/50, D21) -- */
  function resolveTheme(chest) {
    var fixed = chest.getAttribute("data-theme"); // "horror" | "sea" | "random"
    if (fixed === "random") return Math.random() < 0.5 ? "horror" : "sea";
    return fixed === "sea" ? "sea" : "horror";
  }

  function destFor(theme) {
    return DEST[theme] || DEST.horror;
  }

  function navigateOnce(state) {
    if (state.navigated) return;
    state.navigated = true;
    window.location.assign(destFor(state.theme));
  }

  /* --- optional gateway ambient: gesture-gated + fail-silent (Q-M16-6) ----
     The chest tap IS a user gesture, so playback is autoplay-legal. We reuse
     the existing audio engine's playAmbient(), which builds
     /static/audio/global/gateway_ambient.mp3 from the "gateway" key. The file
     is NOT present yet → the <audio> element simply errors internally and the
     engine's tryPlay()/fade() swallow it; nothing here throws or logs. */
  function startGatewayAmbient() {
    try {
      if (window.Archive19Audio && typeof window.Archive19Audio.playAmbient === "function") {
        window.Archive19Audio.playAmbient("gateway");
      }
    } catch (e) {
      /* fail silently — audio is purely decorative on the gateway */
    }
  }

  function activate(chest) {
    var theme = resolveTheme(chest); // ONE coin per click drives art AND dest
    chooseTheme(theme); // cookie + session set BEFORE navigation

    // Reduced motion: skip the reveal entirely, go straight there (D22).
    if (prefersReduced) {
      window.location.assign(destFor(theme));
      return;
    }

    var state = { theme: theme, navigated: false };

    // Defensive: if the reveal DOM is missing for any reason, just navigate.
    if (!reveal || !revealGhost || !revealCake) {
      navigateOnce(state);
      return;
    }

    // open the chest lid
    chest.classList.add("is-opening");

    // arm the reveal overlay with the matching art + veil tint
    reveal.classList.remove("to-horror", "to-sea");
    reveal.classList.add("is-active", theme === "horror" ? "to-horror" : "to-sea");

    var obj = theme === "horror" ? revealGhost : revealCake;
    // restart the animation cleanly
    obj.classList.remove("is-playing");
    void obj.offsetWidth; // reflow to reset
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
    var ms = 1100 + 250; // --gw-reveal + slack
    window.setTimeout(function () {
      navigateOnce(state);
    }, ms);
  }

  // wire all chests: real <button>s already handle Enter/Space → click.
  var chests = document.querySelectorAll(".gw-chest");
  Array.prototype.forEach.call(chests, function (chest) {
    chest.addEventListener("click", function () {
      activate(chest);
    });
  });

  // Optional ambient bed: arm a one-shot start on the first user gesture
  // anywhere on the page (autoplay-legal). Fail-silent if the file is absent.
  (function armAmbient() {
    var started = false;
    function once() {
      if (started) return;
      started = true;
      startGatewayAmbient();
    }
    var opts = { once: true, passive: true };
    document.addEventListener("pointerdown", once, opts);
    document.addEventListener("keydown", once, opts);
    document.addEventListener("touchstart", once, opts);
  })();
})();
