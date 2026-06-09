# M14 — Atmospheric level/island page design notes

UI_UX_DESIGNER · TD step for M14 (`/level/{id}` immersive redesign) · 2026-06-09

These notes describe the visual/interaction design the FRONTEND_ENGINEER builds
against. They are **design intent + class/z-stack contract**, faithful to
`docs/ARCHITECTURE.md` §14 and `docs/REQUIREMENTS.md` §16. Pure CSS + inline SVG;
**no raster backgrounds or frame images** (user's HARD constraint 1). One Horror
room scene and one Sea shore scene for ALL level ids (HARD constraint 2). CSS/SVG
gilded (Horror) / driftwood-rope-shell (Sea) frame (HARD constraint 3).

The companion **clickable mockups** make this tangible:
- `design/mockups/level-horror.html` — Horror room, available slideshow state.
- `design/mockups/level-sea.html` — Sea shore, available state.
- `design/mockups/level-fallback.html` — sealed/missing ("Chudail-not-found")
  state with a **working theme toggle** so the reviewer can feel BOTH themes'
  fallback treatment from one file.

All three carry a working theme toggle that swaps `.theme-horror` ⇄ `.theme-sea`
on `<html>`, so the contrast between the two realities is felt directly (the
~1.5s `--t-transition` repaint is preserved).

---

## 0. The problem these solve

Today `/level/{id}` is one small framed photo floating in ~70% flat dead space
(Horror = near-black; Sea = NO scenery at all — the `.atmosphere` div is empty
because `.horror-scene` is gated `{% if theme != 'sea' %}`). The redesign fills
the viewport with a full-bleed, decorated **room** (Horror) / **shore** (Sea)
scene behind the photo, and reframes the photo as a deliberate, ornate centerpiece
— so the page reads as the immersive environment its landing map promises, not a
photo on a void. Same richness tier as the M9/M10 landing maps, reusing their
exact token + `.atmosphere` + ambient-decor vocabulary (NF-M14-1).

---

## 1. The z-stack (both themes) — the contract the engineer implements

Per ARCHITECTURE §14.3. Back → front, all decor `pointer-events:none` +
`aria-hidden`, all content on `.layer` (z-1) so it stays clickable/legible:

```
(paint)  html,body background ........ --page-bg-image token (theme field gradient)
  z-0    .atmosphere (existing div) ... fixed full-viewport, pointer-events:none
           ├─ background: --vignette .. focal glow (moonlit window / low sun) + edge vignette
           ├─ ::before / ::after ...... fog bands (Horror; reused) — kept subtle on level page
           ├─ .level-env-* (NEW divs) . gradient ENVIRONMENT bands:
           │      Horror: .level-env-wall  + .level-env-floor (+ baseboard seam)
           │      Sea:    .level-env-sky   + .level-env-sea + .level-env-sand (+ horizon/surf)
           ├─ scene SVG ............... Horror: .horror-scene (EXISTS, kept)
           │                            Sea:    .sea-scene (NEW twin — mirrors the contract)
           └─ .level-ambient (NEW) .... decor wrapper holding the REUSED landing leaf spans
                  Horror: .horror-ghost / .horror-twinkle / .horror-star
                  Sea:    .sea-balloon / .sea-bird / .sea-cloud
  z-1    .layer (existing content) .... header (logo + title + toggle), note, .level-stage, footer
           └─ .level-stage ............ THE FRAME: themed ornate mount + OPAQUE backing scrim
                  (slideshow #slideshow/#track/.slide/.slide-img/.slide-caption UNCHANGED inside)
```

Key invariants (NF-M14-4 / NF-M14-7 — HARD GATE):
- `.atmosphere` stays `aria-hidden="true"`; every `<svg>` inside (incl. the new
  `.sea-scene`) carries `focusable="false"`; NO interactive element, NO `tabindex`
  anywhere in `.atmosphere`. The new env bands are plain decorative `<div>`s.
- `.level-stage` rides `.layer` (z-1) and is **opaque enough** that field/glow/fog/
  decor never bleed onto the photo (R-M14-1 — the R-H5 guard generalized to BOTH
  themes; Sea gets the symmetric treatment it lacked).
- The Sea `.sea-scene` block lives in a NEW `{% if theme == 'sea' %}` branch — the
  structural complement of the existing `{% if theme != 'sea' %}` guard around
  `.horror-scene`. Horror's existing block is preserved byte-for-byte.

---

## 2. Horror — "inside a moonlit room"

### Environment (the dead space, filled)
Extend the corridor vocabulary into a room reading (ARCHITECTURE §14.2):
- **Field** — `--page-bg-image` (unchanged token): navy vertical gradient + cool
  moonlight wash high-center.
- **Wall** — `.level-env-wall`: a flat dark navy gradient band occupying the upper
  ~62% of the viewport (the back wall). Faint vertical seams (a low-opacity
  `repeating-linear-gradient`) suggest old panelling / wallpaper without noise.
- **Floor** — `.level-env-floor`: lower ~38%, a `repeating-linear-gradient` of
  warm-dark boards pushed into perspective with a slight `scaleY`/`skew` and a
  gradient fade toward the wall, so it reads as floorboards receding away.
- **Baseboard seam** — a thin `.level-env-floor::before` (or a 1–2px inset shadow
  line) where wall meets floor: a moonlit skirting highlight that grounds the room.
- **Picture-rail shadow** (optional, faint) — a soft horizontal shadow band behind
  the frame so the centerpiece reads as "hung on the wall."
- **Existing `.horror-scene`** stays: the moonlit doorway/window glow now reads as
  the room's window; the cloaked figure (very low opacity, off to the side, never
  behind the photo) as the room's occupant; the edge claws as corner shadows. Fog
  bands stay but **subtler** on the level page (they must not cross into the stage).

### Framed centerpiece — gilded portrait frame
The frame IS the `.level-stage` panel, theme-skinned (no markup change to the
slideshow inside):
- Thick **warm amber/brass gradient border** (`--accent` family), with a layered
  `box-shadow`: an outer drop shadow for lift off the wall + an inner amber bevel
  for gilt depth. Keep the existing opaque dark backing (`#0a0d16` + inset scrim)
  so the photo stays legible (R-M14-1).
- **Ornamental corner scrollwork** as inline-SVG `.level-stage` children (or
  `::before/::after`), `aria-hidden`, `pointer-events:none` — small gilded
  filigree in the four corners, amber gradient fill. Evokes an antique portrait
  frame, playful-spooky, not gory.
- The slide-nav arrows, dots, and M11 `.slide-caption` (amber-parchment on dark
  scrim) are preserved verbatim and stay legible against the dark mount.

### Ambient decor (reused, on `.level-ambient`)
Bring the landing's `.horror-ghost` / `.horror-twinkle` / `.horror-star` spans
into the level page's `.atmosphere` via the NEW `.level-ambient` wrapper. Subtle/
sparse (Q-M14-5): a few drifting ghosts in the side gutters, faint twinkles along
the top, occasional shooting star. They reuse the existing `@keyframes` + the
existing reduced-motion freeze rules for free (the reduce selectors already match
`.horror-ghost`/etc.). Per-instance positions for the level page are ADDED as
`.theme-horror .level-ambient .horror-ghost--N { … }` overrides — never edited
onto the landing's `.horror-ambient` rules (R-M14-3).

---

## 3. Sea — "sunlit shore" (NEW scene, mirrors the Horror contract)

The Sea `.atmosphere` is empty today; this is the biggest visible fix.

### Environment
- **Field** — `--page-bg-image` (unchanged token): azure sky → `#7dd3fc`/`#38bdf8`
  sea, with the warm-sun radial top-right.
- **Sky** — `.level-env-sky`: upper band, soft azure→pale gradient; the existing
  `--vignette` soft-light radial reads as a low sun glow.
- **Sea** — `.level-env-sea`: mid band, deeper azure with a couple of gentle
  `repeating-linear-gradient` swell lines (very low contrast) for water texture.
- **Horizon** — a crisp thin highlight line where sky meets sea.
- **Surf / shoreline** — `.level-env-sand::before` (or a dedicated band): a soft
  white foam arc where sea meets sand.
- **Sand** — `.level-env-sand`: warm sand foreground (the `--tile-bg` sand family),
  a gentle gradient with faint speckle so the frame sits "on the beach."
- **`.sea-scene` (NEW inline-SVG, twin of `.horror-scene`)** — three silhouettes
  mirroring the Horror set:
  - `.sea-silhouette--sun` (twin of `--doorway`): a low sun/cloud glow disc, faint,
    with the same subtle slow opacity breathe (reduced-motion-frozen).
  - `.sea-silhouette--palm` (twin of `--figure`): a palm/small-island silhouette
    anchored LOW and OFF to one side, so it never sits behind the photo.
  - `.sea-silhouette--wave-left` / `--wave-right` (twins of `--claw-left/right`):
    foam/wave shapes anchored to the L/R viewport edges, framing without covering.
  All `focusable="false"`, `aria-hidden`, `pointer-events:none` — identical
  inertness to the Horror scene (satisfies the test_horror_atmosphere-style
  `.atmosphere` invariants for the Sea arm).

### Framed centerpiece — driftwood + rope/shell frame
- Weathered **tan driftwood border** (the `--tile-border` sand family), warm
  light backing (sand/parchment gradient — `.theme-sea .level-stage` already has
  `linear-gradient(#fffaf0,#fdeecb)`; add a soft inner scrim so the bright
  sky/sea field can't wash the photo — the symmetric R-M14-1 guard Sea lacked).
- Soft outer `--tile-shadow` lift (azure-tinted) so the frame sits gently on sand.
- **Rope + shell corner SVGs**: a coiled-rope corner motif with a small shell/
  starfish accent, inline-SVG `.level-stage` children, `aria-hidden`,
  `pointer-events:none`. Warm, sunny, whimsical.
- M11 `.slide-caption` (deep-navy on light scrim) preserved; re-verify AA over the
  sand backing.

### Ambient decor (reused, on `.level-ambient`)
Bring `.sea-balloon` / `.sea-bird` / `.sea-cloud` to the Sea level page via the
SAME new `.level-ambient` wrapper — these render only on the Sea LANDING today.
Gentle/cheerful, sparse (a balloon or two in a sky gutter, a couple of gulls, a
drifting cloud). They reuse the existing theme-scoped keyframes + the existing
reduce freeze. Per-instance positions for the level page are ADDED as
`.theme-sea .level-ambient .sea-balloon--N { … }` overrides; the Sea LANDING's
`.sea-ambient` rules are never edited (R-M14-3, NF-M14-5). QA (L7) confirms the
Sea landing is visually unchanged.

---

## 4. Sealed / missing ("Chudail-not-found") fallback — atmospheric, not a void

Both states get the FULL environment + frame + decor (Q-M14-4). The fallback only
swaps the photo SOURCE (the single random "Chudail-not-found" image) into the SAME
framed scene — so a sealed level looks like a deliberate, eerie/forlorn portrait,
not an empty page.

The existing note keeps its literal substring **`salvaged fallback content`**
(HARD GATE — NF-M14-7) but is restyled diegetically:
- **Horror:** the note becomes a worn **brass plaque / engraved sign** below the
  frame — "This door is sealed — showing salvaged fallback content." Aged-brass
  background, engraved amber text, slight inset bevel; reads as a sign nailed to a
  sealed door.
- **Sea:** the note becomes a weathered **wooden signpost / driftwood plank** —
  "This island has slipped beneath the waves — showing salvaged fallback content."
  Bleached-wood background, carved navy text; reads as a marker on the shore.

The Jinja stays `{% if not available %}` with the same wording; only the wrapping
class/styling changes (e.g. `.level-note` + a theme skin). Text token unchanged.

---

## 5. Controls — preserved, integrated into the scene (M14R6)

- **Logo link** (`.app-logo-link`, home) — kept; placed in the scene header.
- **Theme toggle** (`id="theme-toggle"`, `aria-label="Toggle between Horror and
  Sea themes"`) — PRESERVED verbatim (test contract). Re-placed/re-styled into the
  header to suit the richer page; gets a backing/scrim if the scene would drop it
  below WCAG AA. Present on every page (F2).
- **Heading** ("Room {id}" / "Island {id}") + **footer** ("Tour-de-Anshika ·
  Level {id}") — kept, restyled to fit the scene, given a subtle scrim/glow so
  they stay legible over the field.
- **Audio crossfade** — untouched (out of scope); styling only.

---

## 6. Responsive (M14R9, R-M14-6) — mirrors M9/M10

- Frame `border` / `box-shadow` / corner-SVG scale via `clamp()`; `.level-stage`
  padding tightens at ≤480px (matches the existing `.slide-caption` mobile rule).
  The frame never crowds the photo (`.slide-img` keeps `max-height:70vh;
  object-fit:contain`).
- Environment gradient bands are viewport-relative (`%`/`vh`) → reflow with no
  horizontal scroll, no focal loss. The framed photo stays the centerpiece at
  every width.
- Ambient decor **thins** on small screens (fewer visible instances / shrink via
  the existing `clamp()` widths, as the landing does for `.horror-ghost` at
  ≤480px). Corner scrollwork/rope hides or shrinks under ~480px so it never
  overlaps the photo.

---

## 7. Reduced motion (NF-M14-4, R-M14-5) — extend the existing block

All new motion is `transform`/`opacity` only. The reused ambient spans
(`.horror-ghost`/`-twinkle`/`-star`, `.sea-balloon`/`-bird`/`-cloud`) are ALREADY
frozen by the existing `@media (prefers-reduced-motion: reduce)` rules (same
selectors) — they inherit the freeze for free on the level page. The ONLY new
freeze rules needed are for the NEW `.sea-scene` sun-breathe (freeze to steady
opacity, like the Horror doorway flicker freeze) and any `.level-env-*` motion
(most env bands are static gradients → nothing to freeze). No flicker exceeds the
M9 "well under 3 flashes/sec" bar (R-H3). Shooting-star streaks reuse the existing
reduce rule that hides them (no stray mid-sky dot).

---

## 8. Tokens used (NO new tokens, NO `:root` edits)

Everything is built from the EXISTING token system, theme-scoped (NF-M14-1/5):

| Token | Role in the level scene |
|---|---|
| `--page-bg-image` | the full-bleed field (navy night / sky-sea) — unchanged |
| `--vignette` | focal glow (moonlit window / low sun) + edge vignette — unchanged |
| `--bg`, `--bg-2` | env band base colors / photo backing |
| `--accent`, `--accent-soft` | Horror gilded frame, dots, focus rings |
| `--fg`, `--muted` | heading / footer / note text |
| `--tile-bg`, `--tile-border`, `--tile-shadow` | `.level-stage` frame body, border, lift; Sea sand |
| `--t-transition` (1.5s) | theme repaint crossfade — preserved |

New CSS class families (all ONLY ever styled under `.theme-horror`/`.theme-sea`):
`level-env-wall`, `level-env-floor`, `level-env-sky`, `level-env-sea`,
`level-env-sand`, `level-ambient` (decor wrapper), `sea-scene` +
`sea-silhouette--sun`/`--palm`/`--wave-left`/`--wave-right`, and a `level-note`
skin for the diegetic plaque/sign. No bare rules; no collision with the landing
`.horror-*`/`.sea-*` map classes (NF-M14-5).

---

## 9. Handoff notes / deviations from ARCHITECTURE §14

- **No deviation in technique or contract.** This design follows §14 exactly:
  pure CSS/SVG (raster deferred), uniform-per-theme, CSS/SVG frame on `.level-stage`,
  the `level-env-*` / `.level-ambient` / `.sea-scene` class families, the z-stack,
  the R-M14-1 legibility guard generalized to both themes, the reduced-motion +
  responsive plans, and ZERO backend change (`app/main.py` untouched — existing
  `theme`/`level_id`/`available`/`audio_track_ids` context suffices).
- **Mockup-only simplifications (NOT design intent for the build):** the mockups
  use a placeholder image (`picsum`/solid block) for the photo and do NOT include
  the real slideshow JS, the `fetch("/api/levels/...")` call, the audio engine, or
  the Cloudinary URLs — they are static look/feel artifacts. The real build keeps
  ALL of that markup/JS byte-for-byte (M14R4). The mockups also inline the relevant
  CSS rather than editing the real `static/style.css` (the build moves these into
  theme-scoped blocks in `static/style.css`).
- **A2 cache-bust:** the build should bump `style.css?v=6 → ?v=7` on BOTH templates'
  `<link>` (contract-safe; the guard accepts any `?v=\d+`).
- **Open visual questions flagged to PM/ARCHITECT:** none block the build — A1
  (raster vs pure CSS), A4 (uniform vs per-level), A5 (frame raster vs CSS) are the
  user confirm-the-default items; this design assumes the recommended defaults
  (pure CSS/SVG, uniform, CSS frame). If the user later wants painted scenery, the
  single hook is the `--page-bg-image` token per theme (deferred L5 task, ≤300 KB
  WebP) with the CSS fog/glow/decor staying as overlays.
