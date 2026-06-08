/* =========================================================================
   Archive 19 — Theme persistence + toggle (T7, D1/D3)

   State machine (docs/ARCHITECTURE.md §1):
     - SSR already rendered the correct .theme-* class from the `theme` cookie
       (default horror). This script only reconciles + handles the toggle.
     - Persistence: cookie `theme=horror|sea; path=/` (SSR reads it) MIRRORED to
       sessionStorage (D1). On load we reconcile the two; if they disagree the
       cookie wins for SSR consistency, and we re-sync sessionStorage.
     - Toggle (client-side): write cookie + sessionStorage, then reload so the
       server re-renders the correct theme flash-free.
   ========================================================================= */
(function () {
  "use strict";

  var VALID = { horror: true, sea: true };
  var DEFAULT_THEME = "horror";

  function readCookie() {
    var m = document.cookie.match(/(?:^|;\s*)theme=(horror|sea)\b/);
    return m ? m[1] : null;
  }

  function writeCookie(theme) {
    // 1 year, path=/ so every route (and the SSR read) sees it. SameSite=Lax
    // is appropriate for a same-site navigation preference cookie.
    var oneYear = 60 * 60 * 24 * 365;
    document.cookie =
      "theme=" + theme + "; path=/; max-age=" + oneYear + "; SameSite=Lax";
  }

  function readSession() {
    try {
      return window.sessionStorage.getItem("theme");
    } catch (e) {
      return null;
    }
  }

  function writeSession(theme) {
    try {
      window.sessionStorage.setItem("theme", theme);
    } catch (e) {
      /* storage may be unavailable (private mode) — degrade silently */
    }
  }

  // The theme the server actually rendered (class on <html>).
  function ssrTheme() {
    var root = document.documentElement;
    return root.classList.contains("theme-sea") ? "sea" : "horror";
  }

  function applyClass(theme) {
    var root = document.documentElement;
    var body = document.body;
    [root, body].forEach(function (node) {
      if (!node) return;
      node.classList.remove("theme-horror", "theme-sea");
      node.classList.add("theme-" + theme);
    });
  }

  // Reconcile cookie <-> sessionStorage against what SSR painted.
  function reconcile() {
    var rendered = ssrTheme();
    var cookie = readCookie();
    var session = readSession();

    // Cookie is the SSR source of truth. Make sure it exists and matches what
    // was rendered; mirror to sessionStorage.
    var effective = VALID[cookie] ? cookie : rendered;
    if (cookie !== effective) writeCookie(effective);
    if (session !== effective) writeSession(effective);

    // Defensive: if for some reason the rendered class drifted from the
    // effective theme (e.g. stale cache), correct the DOM without a reload.
    if (rendered !== effective) applyClass(effective);
    return effective;
  }

  function setTheme(theme) {
    if (!VALID[theme]) theme = DEFAULT_THEME;
    writeCookie(theme);
    writeSession(theme);
    // Reload for flash-free SSR repaint (LOCKED DECISION: reload acceptable).
    window.location.reload();
  }

  function currentTheme() {
    return reconcile();
  }

  function wireToggle() {
    var btn = document.getElementById("theme-toggle");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var now = currentTheme();
      setTheme(now === "horror" ? "sea" : "horror");
    });
  }

  // Expose for page scripts (audio needs to know the active theme).
  window.Archive19Theme = {
    current: currentTheme,
    set: setTheme,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      reconcile();
      wireToggle();
    });
  } else {
    reconcile();
    wireToggle();
  }
})();
