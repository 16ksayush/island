/* M14 mockup theme toggle — swaps .theme-horror <-> .theme-sea on <html>,
   mirroring the real SSR-class mechanism so reviewers feel both realities.
   Updates the toggle icon/label + swaps any [data-horror]/[data-sea] copy so
   the headings/captions/note read correctly per theme. Mockup-only; the real
   build keeps theme.js + the SSR cookie mechanism. */
(function () {
  var root = document.documentElement;
  var btn = document.getElementById("theme-toggle");

  function isSea() { return root.classList.contains("theme-sea"); }

  function applyCopy() {
    var sea = isSea();
    // Toggle button affordance
    var icon = btn && btn.querySelector(".toggle-icon");
    var label = btn && btn.querySelector(".toggle-label");
    if (icon) icon.textContent = sea ? "🌙" : "🌊";
    if (label) label.textContent = sea ? "Enter the Corridor" : "Sail to the Sea";
    // Any element with both data-horror / data-sea swaps its text per theme.
    document.querySelectorAll("[data-horror][data-sea]").forEach(function (el) {
      el.textContent = sea ? el.getAttribute("data-sea") : el.getAttribute("data-horror");
    });
    // Per-theme scene blocks: show only the active theme's scene markup.
    document.querySelectorAll(".scene-horror-only").forEach(function (el) { el.hidden = sea; });
    document.querySelectorAll(".scene-sea-only").forEach(function (el) { el.hidden = !sea; });
  }

  if (btn) {
    btn.addEventListener("click", function () {
      root.classList.toggle("theme-horror");
      root.classList.toggle("theme-sea");
      // keep <body> class in sync if present (matches the real templates)
      document.body.classList.toggle("theme-horror");
      document.body.classList.toggle("theme-sea");
      applyCopy();
    });
  }
  applyCopy();
})();
