/* M15 mockup theme toggle — swaps .theme-horror <-> .theme-sea on <html> + <body>,
   mirroring the real SSR-class mechanism so reviewers feel both realities. Also:
   - swaps the toggle icon/label,
   - swaps any [data-horror]/[data-sea] copy (h1, banner, list names),
   - shows only the active theme's per-theme scene block (.scene-horror-only /
     .scene-sea-only) inside the SVG, so one .nav-map serves both worlds here.
   Mockup-only; the real build SSRs the correct theme arm + keeps theme.js. */
(function () {
  var root = document.documentElement;
  var btn = document.getElementById("theme-toggle");

  function isSea() { return root.classList.contains("theme-sea"); }

  function applyCopy() {
    var sea = isSea();
    var icon = btn && btn.querySelector(".toggle-icon");
    var label = btn && btn.querySelector(".toggle-label");
    if (icon) icon.textContent = sea ? "🌙" : "🌊";
    if (label) label.textContent = sea ? "Enter the Corridor" : "Sail to the Sea";

    document.querySelectorAll("[data-horror][data-sea]").forEach(function (el) {
      el.textContent = sea ? el.getAttribute("data-sea") : el.getAttribute("data-horror");
    });
    // Per-theme SVG scene + node groups: show only the active theme's markup.
    document.querySelectorAll(".scene-horror-only").forEach(function (el) {
      el.style.display = sea ? "none" : "";
    });
    document.querySelectorAll(".scene-sea-only").forEach(function (el) {
      el.style.display = sea ? "" : "none";
    });
  }

  if (btn) {
    btn.addEventListener("click", function () {
      root.classList.toggle("theme-horror");
      root.classList.toggle("theme-sea");
      document.body.classList.toggle("theme-horror");
      document.body.classList.toggle("theme-sea");
      applyCopy();
    });
  }
  applyCopy();
})();
