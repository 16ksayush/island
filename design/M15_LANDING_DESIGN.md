# M15 — Programmatic, fully-responsive landing design notes (N7 HYBRID)

UI_UX_DESIGNER · TD step for M15 (`/` landing redesign — SVG-map → mobile-list) ·
2026-06-09 · **REVISED to the USER-LOCKED N7 HYBRID** (rich filtered SVG scenery
+ drift-free nav layered ON TOP of a painted raster BACKDROP per theme).

These notes are the **design intent + class/z-stack/SVG contract** the
FRONTEND_ENGINEER builds against. They are faithful to `docs/ARCHITECTURE.md`
§15 (USER-LOCKED — N2 map→list reflow, then **N7 HYBRID** at §15.2.3/§15.3/§15.4/
§15.7) and `docs/REQUIREMENTS.md` §17. They **extend the M14 vocabulary**
(`design/M14_LEVEL_PAGE_DESIGN.md`, `.horror-scene`/`.sea-scene`, `level-env-*`,
`.level-ambient`, the tokens, the reduced-motion + R-H5 idiom) — this is the SAME
world as the M14 level pages.

**The N7 change vs the prior (N2) notes — why this revision exists.** The user
reviewed the prior **pure-SVG** mockups, approved the *functional model* (SVG map →
mobile list, drift-free nav, reflow at 768px) but judged the hand-authored vector
art **"feels cheap" / too simple** vs the existing detailed PAINTED maps. The
resolution is the **HYBRID**: keep the proven functional model, but layer the
(now ELEVATED, filter-crafted) SVG scenery + the 19 nav nodes **ON TOP OF the
existing painted raster maps reused as an ambient `cover` BACKDROP** per theme.
Painterly DEPTH comes from the reused painting (z-0); the crisp SCALABLE,
drift-free structure + scenery detail + interaction come from the SVG (z-2); a
themed legibility scrim/fog (z-1) sits between so the busy painting never fights
the SVG or the labels.

- **NOT pure-SVG / NOT no-raster anymore.** The two EXISTING maps are REUSED as
  backdrops: Horror `static/img/horror/landing-map.v2.jpg`, Sea
  `static/img/light/landing-map.v2.webp` (kept on disk — §15.4 reversal).
- The **backdrop `cover` crop and the SVG `viewBox` are TWO INDEPENDENT
  full-viewport layers, NOT pixel-aligned.** The SVG carries ALL structure (the
  doors/islands + 19 nodes in its own `viewBox`); the painting is only depth
  behind it — so the backdrop crop introduces **ZERO drift**.
- **Template + theme-scoped CSS only; `app/main.py` untouched** (§15.6).

The companion **clickable mockups** make this tangible (all standalone, no
backend, Tailwind CDN + inline CSS, a working theme toggle):

- `design/mockups/landing-horror.html` — Horror **corridor of doors** elevated
  SVG scene OVER the REAL painted `landing-map.v2.jpg` backdrop (desktop) + the
  mobile `.nav-list`, with a working toggle.
- `design/mockups/landing-sea.html` — Sea **treasure-map archipelago** elevated
  SVG scene OVER the REAL painted `landing-map.v2.webp` backdrop (desktop) + the
  mobile `.nav-list`, with a working toggle.
- shared `design/mockups/m15-landing.css` — the z-stack (`.nav-backdrop` z-0 →
  `.atmosphere` scrim z-1 → `.layer`/`.nav-map` z-2), node legibility backing, the
  768px boundary; `design/mockups/m15-toggle.js` swaps theme + backdrop painting.

Both mockups carry the **real 768px media-query toggle** between `.nav-map` and
`.nav-list` — **resize the window** to feel the true reflow (SVG scenic map
wide → clean vertical list narrow), and the **theme toggle** swaps
`.theme-horror` ⇄ `.theme-sea` on `<html>` so the reviewer feels both realities
from either file.

---

## 0. The problem these solve

Today `/` overlays **19 absolute %-positioned `.map-hotspot` anchors** on a
fixed-aspect **raster** map (`coords`/`sea_coords` hand-calibrated to the art).
On any other screen ratio the hotspots **drift off** their painted location and
the map letterboxes; the current mobile "fix" is a **130–175vw pannable scroll
surface** (`style.css` L869–1027) — not a reflow. M15 removes both fragilities:

1. **Desktop/tablet** — one inline `<svg viewBox="0 0 1600 900">` holds BOTH the
   high-fidelity scenery AND the 19 nav targets in ONE coordinate system, so art
   + hotspots scale as a single unit and **never drift** at any aspect ratio.
2. **Phone** — the same 19 targets **true-reflow** into a clean stacked vertical
   `.nav-list` of ≥44px rows — no pannable hack, no horizontal scroll.

The two SSR representations are CSS-media-query-toggled at **one ~768px
boundary** (`display:none`), so exactly **one is in the a11y tree per
breakpoint** (19 links each, 38 hrefs in the HTML, never both shown — NF-M15-7).

---

## 1. The HYBRID z-stack (both themes) — the contract the engineer implements

Per ARCHITECTURE §15.2.3 (N7). Back → front; all decor `pointer-events:none` +
`aria-hidden`; the interactive nav rides `.layer` (now z-2) so it stays
clickable/focusable. **The new z-0 `.nav-backdrop` sits BENEATH the existing
`.atmosphere`, which moves to z-1 and gains a themed legibility scrim:**

```
(paint)  html,body background ........ --page-bg-image token (theme field gradient — still there)
  z-0    .nav-backdrop  (NEW div) .... fixed full-viewport, pointer-events:none, aria-hidden
           └─ background-image:cover .. the EXISTING painted map, REUSED as ambient depth:
                  Horror: url(/static/img/horror/landing-map.v2.jpg)   (theme-conditional)
                  Sea:    url(/static/img/light/landing-map.v2.webp)   background-size:cover, center
                  (cover-crop is FINE — decoupled from the SVG viewBox → zero drift)
  z-1    .atmosphere (existing div) ... fixed full-viewport, pointer-events:none, aria-hidden
           ├─ themed SCRIM ............ semi-opaque wash knocking the painting back for legibility:
           │      Horror: deep-navy radial wash | Sea: soft azure→white wash (kept light/airy)
           ├─ background: --vignette .. focal glow (moonlit doorway / low sun) + edge vignette
           ├─ ::before / ::after ...... Horror fog bands (exist, reused) | Sea soft haze (optional)
           └─ ambient decor ........... REUSED leaf spans, full-bleed & viewport-relative:
                  Horror: .horror-ambient → .horror-ghost / -twinkle / -star
                  Sea:    .sea-ambient    → .sea-balloon / -bird / -cloud
  z-2    .layer (existing wrapper) ..... brand logo + sr-only h1 + theme toggle
           ├─ .nav-map  (inline SVG) ... DESKTOP/TABLET (≥768px): ONE <svg viewBox="0 0 1600 900">
           │      ├─ .nav-scene <g> .... ELEVATED filter-crafted illustration, LAYERED OVER the
           │      │                       painting (DECORATIVE, aria-hidden, focusable=false; §3/§4/§5)
           │      └─ 19× .nav-node <a> . interactive door/island targets IN the same viewBox (id 0..18)
           │             ├─ .nav-node-glyph <g> ... door (Horror) / island (Sea) vector; drop-shadow LIFT
           │             ├─ .nav-node-hit <rect> .. transparent ≥44px hit target (if glyph < target)
           │             ├─ .nav-node-plate ....... small OPAQUE themed backing behind the number (R-M15-11)
           │             └─ .nav-node-label <text> level number (always visible)
           └─ .nav-list (stacked list)   PHONE (≤767px): <nav><ul> of 19 .nav-list-item rows
                  (.nav-map hidden) — CSS-toggled, MUTUALLY EXCLUSIVE
```

**The key hybrid insight (do not lose it):** the z-0 `.nav-backdrop` (`cover`,
may crop painted edges) and the z-2 `.nav-map` SVG (`viewBox="0 0 1600 900"
preserveAspectRatio="xMidYMid meet"`) are **TWO INDEPENDENT full-viewport
layers, NOT pixel-aligned.** All structure — the doors/islands AND the 19 nodes —
rides the SVG `viewBox`; the painting is only depth behind. So `cover`-cropping
the backdrop across aspect ratios introduces **ZERO node drift** (the old
fragility came from pinning `%` hotspots to a fixed-aspect bitmap; here the
interactive nodes are fully decoupled from the backdrop crop).

### 1.1 The painted backdrop (z-0 `.nav-backdrop`) — REUSE, not regenerate

- Mechanism (LOCKED, §15.4): a dedicated `<div class="nav-backdrop"
  aria-hidden="true">` with a **theme-conditional CSS `background-image`**
  (`.theme-horror .nav-backdrop { background-image:url(…horror map…) }` /
  `.theme-sea .nav-backdrop { … sea map … }`), `position:fixed; inset:0;
  z-index:0; background-size:cover; background-position:center;
  pointer-events:none`. CSS `background-image` (not `<img>`) keeps it purely
  decorative (no `alt`/a11y surface, no reflow), trivially `cover`-crops, and is
  theme-scoped in one place.
- The two `.v2` maps are KEPT on disk and REFERENCED (not regenerated). The
  Cloudinary gallery photos are untouched.
- **Active-theme preload (NF-M15-6):** SSR emits a `<link rel="preload"
  as="image" fetchpriority="high" href="…ACTIVE-theme map…">` keyed off the
  `theme` cookie — first paint pays for ONE backdrop; the inactive theme's
  backdrop loads only on toggle (lazy). Tradeoff vs the N2 pure-SVG: one extra
  raster on first paint, mitigated by preloading only the active theme.

### 1.2 The legibility scrim/fog (z-1 `.atmosphere`)

The busy painting must not fight the crisp SVG or wash out labels. The existing
`.atmosphere` div (now z-1) carries, per theme:

- a **semi-opaque themed scrim** layered into its `background`: Horror a deep-navy
  radial wash (`rgba(8,12,24,0.30)`→`rgba(5,7,13,0.74)`) that re-darkens the
  corridor; Sea a soft azure→white wash (`rgba(224,242,254,0.42)`→
  `rgba(56,189,248,0.34)`) that keeps the world bright/airy while taming contrast;
- the existing **`--vignette`** focal glow (moonlit doorway / low sun) + edge
  vignette, reused unchanged;
- the existing **fog `::before/::after`** (Horror drifting bands; Sea optional
  soft haze), reused unchanged.

The scrim is the single dial: dial opacity up if a backdrop region still washes a
label below AA, down if the painting reads too muddy. The per-node opaque backing
(§1.3) is the belt-and-braces guarantee on top of the scrim.

### 1.3 Per-node opaque backing (R-M15-11) — legible over ANY backdrop region

Because the painting varies wildly region-to-region, every node carries a small
**opaque themed backing + a drop-shadow LIFT** so its number stays legible no
matter what paint sits behind it:

- **Horror:** the door face is itself opaque; the whole `.nav-node-glyph` gets a
  CSS `drop-shadow(0 6px 10px rgba(0,0,0,0.7))` (the feDropShadow analog) so the
  door lifts off the painting, plus a dark amber-ringed `.nav-node-plate` available
  where a number would otherwise sit on translucent scenery.
- **Sea:** each island carries a `.nav-node-plate` (opaque `#fffaf0` sand placard,
  `opacity:0.94`) behind the number + a `drop-shadow(0 5px 9px rgba(2,40,70,0.45))`
  island lift.

This generalizes the M14 / R-H5 backing technique to "over any backdrop region."

Key invariants (NF-M15-7 — the a11y hard gate):

- **Never both displayed.** `.nav-map` and `.nav-list` are toggled by
  mutually-exclusive media queries at the single 768px boundary via
  `display:none`. The hidden one is out of the a11y tree + tab order. QA asserts
  exactly one is rendered-visible per width → 19 links in the a11y tree, not 38.
- **Decorative vs interactive is explicit.** The `.nav-scene` `<g>`, the z-0
  `.atmosphere` ambient blocks, and any optional mobile header banner are ALL
  `aria-hidden="true"` + `focusable="false"` on SVGs + **NO `tabindex`** +
  `pointer-events:none`. The ONLY focusable/keyboard-navigable elements are the
  19 `.nav-node` `<a>`s (desktop) / `.nav-list-item a`s (mobile) — real links.
- **One template source drives both representations** from the SAME
  `levels`/`available_ids`/`sea_names`, so they cannot drift (R-M15-10).

---

## 2. The desktop/tablet scene container — `.nav-map` (one viewBox)

A single inline `<svg class="nav-map" viewBox="0 0 1600 900"
preserveAspectRatio="xMidYMid meet" role="navigation" aria-label="…">` rendered
inside the existing `.layer`, replacing the `.horror-map`/`.sea-map` `<img>` +
absolute hotspots in BOTH arms. **All paths AND all 19 nav `<a>`s are children of
this ONE viewBox** — that is the structural fix for the old drift.

- `width:100%; max-width:min(96vw,72rem); height:auto;` — the intrinsic 16:9
  `viewBox` aspect drives height; `meet` guarantees no node is ever clipped, at
  most mild centered letterboxing on extreme ratios.
- **The 19 `.nav-node` `<a>`s are authored in document order id 0..18** so tab
  order = id order (R-M15-8). Each is a real `<a href="/level/{id}">` carrying
  the `aria-label`, wrapping a decorative `.nav-node-glyph <g>` + always-visible
  `.nav-node-label <text>` (level number).

### Node anatomy + states

| Part | Element | Role |
|---|---|---|
| `.nav-node` | `<a href="/level/{id}">` | the interactive link; focusable; carries `aria-label`. Hover/focus affordance. |
| `.nav-node-glyph` | `<g>` (decorative) | door (Horror) / island (Sea) vector for this node, drawn at its viewBox coords |
| `.nav-node-hit` | `<rect>` transparent | per-node hit target sized so the node maps to **≥44×44 CSS px at the ~768px tablet floor** (R-M15-7). Added when the visible glyph alone is under target. |
| `.nav-node-label` | `<text>` | always-visible level number (replaces the old hidden `.map-hotspot-id`) |
| `.nav-node--sealed` | modifier on `<a>` | availability twin of the old `.is-sealed`; sealed skin; **still navigates** to `/level/{id}` |

**States:**

- **Available** — Horror: lit door, warm amber under-glow, `--accent` ring; Sea:
  sunlit island, palm + azure surf ring. Number in `--fg`.
- **Available · hover/focus-visible** — Horror: amber glow intensifies
  (`--accent` SVG `filter`/`stroke`), the door reads "open"; Sea: azure glow + a
  gentle lift. **Visible focus indicator** = an explicit SVG focus `<rect>`/
  `outline` drawn on the node (the M14 focus-visible idiom) — load-bearing for
  R-M15-8 because SVG focus rings are easy to lose.
- **Sealed** (`id ∉ available_ids`) — Horror: boarded/dimmed door, amber → ash,
  faint chain/plank; Sea: half-submerged island, azure → slate, dimmed.
  `aria-label` carries the sealed wording (below). Still a focusable link.

### Sizing / legibility at the tablet floor (R-M15-7, the watch-item)

At ~768px the whole `viewBox` renders smallest. The design budget:

- `.nav-node-label` font-size in **viewBox units ≈ 26–32** (of the 900-tall
  canvas) → ≈ 22–27 CSS px at 768px render — comfortably legible.
- `.nav-node` glyph + `.nav-node-hit` rect ≈ **92×92 viewBox units** → ≈ 44–52
  CSS px at 768px render — clears the ≥44px tap target by construction.
- Nodes are **spaced so they never overlap** at any scale (positions chosen with
  ≥110 viewBox-unit centers apart). Where the illustration would wash a label
  below WCAG AA, the node carries a small opaque themed backing disc/plate (the
  generalized R-H5 / M14 `.level-stage` technique): Horror dark plate + amber
  number; Sea light sand/parchment plate + deep-azure number.

---

## 3. The phone representation — `.nav-list` (stacked vertical list)

Below 768px the SVG map is `display:none` and the same 19 targets render as a
flat, accessible list — a TRUE reflow into normal document flow (the page scrolls
vertically; **no horizontal scroll, no pannable surface**):

```
<nav class="nav-list" aria-label="Choose a door | Choose an island">
  <ul>
    <li class="nav-list-item[ nav-list-item--sealed]">
      <a href="/level/{id}" aria-label="…SAME string as the SVG node…">
        <span class="nav-list-id">{id}</span>
        <span class="nav-list-name">…name / 'Door {id}' / sealed wording…</span>
      </a>
    </li>  <!-- id 0..18 in order -->
  </ul>
</nav>
```

- **Rows ≥44px by construction** — `.nav-list-item a { min-height: clamp(2.75rem,
  8vw, 3.25rem); }` floored at 2.75rem (44px), full-row width, generous padding,
  comfortable gaps so adjacent rows never crowd. This is the phone-side ≥44px
  guarantee (NF-M15-2).
- **`.nav-list-id`** — a themed leading number chip (Horror: amber-on-dark door
  numeral; Sea: azure-on-sand island numeral). **`.nav-list-name`** — the label
  text: Sea surfaces `sea_names[id]` ("Prison", "Graveyard"…); Horror shows
  "Door {id}" (or the sealed wording).
- **Available vs sealed** — available rows carry the theme accent + a `›`
  chevron affordance; `--sealed` rows are dimmed/boarded (Horror) /
  submerged-azure→slate (Sea) and surface the sealed wording inline. Every row
  **still navigates** to `/level/{id}`.
- **`aria-label` parity (R-M15-10):** the `<a href>` + `aria-label` wording is
  **byte-identical** to the SVG node's, so a screen-reader user hears the same
  names at every breakpoint.
- **Accessible font-scaling path (R-M15-9):** SVG `<text>` ignores user
  font-size preferences; this HTML list uses real `rem`/`clamp()` text that DOES
  scale with browser/OS zoom — so the list is the genuine font-scaling path, not
  an afterthought. It must be designed as a first-class, usable representation.
- **Optional reduced header banner** — the phone arm MAY keep a compact,
  decorative-only reduced SVG scene band above the list (still
  `aria-hidden`/`focusable="false"`, **NO nav `<a>`s**) so the theme reads on
  phones. The mockups include this banner to show the intent.

### Sealed wording (PRESERVED verbatim — test contract)

- **Horror:** `aria-label="Level {id} (sealed — fallback content)"` ·
  `.nav-list-name` shows "Sealed".
- **Sea:** `aria-label="Level {id} — {sea_names[id]} (sunken — fallback
  content)"` · `.nav-list-name` shows the name + "(sunken)".

---

## 3.5 The elevated-SVG technique list (N7 — both themes)

Per §15.3, the SVG must read RICH (not flat) so it holds its own OVER and
complements the painting. Real SVG craft used in the mockups (the engineer keeps
the same `<filter>`/gradient/ornament vocabulary at build polish):

- **`feTurbulence` grain** — a faint canvas/paper texture painted over the scene
  (`type="fractalNoise"` + `feColorMatrix` to tint; Horror near-black `overlay`,
  Sea warm-sepia `multiply`) so the vector doesn't look digitally flat.
- **`feGaussianBlur` fog / glow / haze** — Horror low floor fog + moonlight shaft;
  Sea sun-glow halo + sea-foam shimmer. Soft, bounded blur radius.
- **`feDropShadow` LIFT** — doors / islands / compass cast a shadow so they sit
  ABOVE the painting (also exposed as CSS `drop-shadow` on `.nav-node-glyph`).
- **`feSpecularLighting` + `fePointLight` sheen** — a metallic glint on the
  Horror sconce mounts; a bright glint on the Sea sun disc.
- **Multi-stop gradients + layered depth** — wall/floor/sky/sea gradient fields,
  receding perspective ranks (Horror), layered clouds + swell lines (Sea).
- **Ornamentation** — Horror: wall sconces, corner cobwebs, moonlight shaft,
  edge claw shadows. Sea: compass rose, dashed sailing routes, surf rings, palms,
  huts/towers.
- **`mix-blend-mode` + partial transparency** — the non-focal scene fields
  (walls/floor, sky/sea) are translucent (`multiply`/plain alpha) so the painting
  shows THROUGH them (hybrid integration), while nodes + labels stay fully opaque
  and backed for legibility (§1.3).

## 4. Horror — "corridor of doors" (elevated SVG scene, OVER the painting)

A hand-authored, layered illustration of a haunted hallway drawn in the
`viewBox`, LAYERED OVER the painted backdrop (N7) and RICHER than M14's
gradient-band shorthand (Q-M15-2, USER-LOCKED). Tokens: `--bg`/`--bg-2` navy
field, `--accent` amber. The wall/floor fields are translucent + `multiply` so
the painting reads through; doors/sconces/moonlight stay crisp and lifted.

- **(a) Perspective corridor** — receding wall/floor/ceiling paths converging on
  a vanishing point a little above center; multi-stop linear gradients carry
  depth (navy `#0d1322` near → near-black `#05070d` far, the M9 `--page-bg-image`
  palette). A `--vignette`-style **moonlit doorway glow** (radial, pale
  blue-white `rgba(190,205,235,…)`) sits at the far end as the focal vanishing
  point — exactly the existing `#hr-moon` radial elevated into the scene.
- **(b) The 19 doors = the `.nav-node-glyph`s** — each a detailed door (frame,
  two recessed panels, a round amber handle, a faint amber under-glow strip at
  the threshold), positioned along BOTH side walls in two receding ranks so
  perspective places near doors larger / far doors smaller (a real depth read).
  Door numbers (`.nav-node-label`) are always visible on the door face.
- **(c) Atmospheric detail** — low fog wisps (the M9 `.atmosphere::before/after`
  fog vocabulary elevated as soft SVG paths/blur near the floor); a couple of
  **wall sconces** with a small flickering amber flame glow (slow opacity
  breathe, reduced-motion-frozen); faint corner-shadow claw motifs reused from
  `.horror-scene` as scene-embedded illustration, kept to the edges so they never
  sit under a door node.
- **(d) Reused z-0 ambient** — `.horror-ambient` ghosts / twinkles / shooting
  stars drift in the atmosphere BEHIND the corridor (existing keyframes + reduce
  freeze, re-homed unchanged).
- **Mood:** playful-spooky, not gory (a gift for the user's sister) — the moonlit
  hall reads as an inviting "choose your door" gallery, not a threat.

---

## 5. Sea — "treasure-map archipelago" (elevated SVG scene, OVER the painting)

A hand-authored, layered sunlit sea-map drawn in the `viewBox`, LAYERED OVER the
painted backdrop (N7) — warm, adventurous, treasure-map whimsy. Tokens:
azure/sand `.theme-sea` palette. The sky/sea fields are translucent so the
painted map glows through; islands/sun/compass stay crisp and lifted.

- **(a) Layered sky → sea → sand** — multi-stop gradients: azure `#e0f2fe` top →
  `#7dd3fc`/`#38bdf8` mid-sea → warm sand `#fef9ef`/`#fcd9a8` shores; a **sun with
  a radial glow** top-right (the existing `--page-bg-image` sun position), layered
  cloud paths, a crisp horizon line, and a textured sea surface with low-contrast
  wave/foam path detail.
- **(b) The 19 islands = the `.nav-node-glyph`s** — each a detailed little island
  (sand mound, a palm or two, a hut/landmark, a white surf ring), dotted across
  the sea in the `viewBox` like a treasure map. Island numbers
  (`.nav-node-label`) are always visible on a small sand placard.
- **(c) Treasure-map flourishes** — a **compass rose** (NE corner), **dashed
  sailing routes** linking islands (decorative dotted curves), a subtle
  parchment/paper grain, and a hand-drawn coastline feel for the
  hand-illustrated bar.
- **(d) Reused z-0 ambient** — `.sea-ambient` balloons / gulls / clouds drift in
  the atmosphere (existing keyframes + reduce freeze, re-homed unchanged).
- **Mood:** bright, airy, sunny — the painted island NAMES (Prison, Graveyard,
  Dragon's Den…) are the Sea world's island names per the SQ6 sign-off; the
  palette/copy stay sunlit azure ("Enter the Corridor" / 🌙).

---

## 6. Persistent chrome (M15R4) — logo + toggle + ambient

All three are PRESERVED and re-homed into the new `.layer`:

- **Brand logo** — `<a href="/" class="brand-logo"><img class="app-logo"
  src="/static/img/logo/create_thumb.png" …></a>`, overlaid top-left, present on
  every page. Gets a subtle scrim if the scene would drop it below AA.
- **Theme toggle** — `<button id="theme-toggle" class="theme-toggle …"
  aria-label="Toggle between Horror and Sea themes">` — PRESERVED verbatim
  (`id="theme-toggle"` is a test contract). Overlaid top-right. Copy: Horror
  arm → 🌊 "Sail to the Sea"; Sea arm → 🌙 "Enter the Corridor" (preserved
  strings). M15 may add a `.nav-map`/`.nav-list`-context position override (the
  analog of the old `.horror-map-toggle`/`.sea-map-toggle`).
- **`sr-only <h1>`** — preserved per theme ("Tour-de-Anshika — choose a
  destination" / "— choose an island").
- **Ambient decor** — reused leaf vocabulary (§4d / §5d), re-homed in the z-0
  atmosphere, `aria-hidden`/inert, existing keyframes + reduce freeze unchanged.
- **Scripts** — `playAmbient` audio bootstrap + the idle-time available-level
  prefetch script kept byte-for-byte; the `?calibrate` block is **removed**
  (M15R7), the map `<img>` `fetchpriority="high"` is **dropped** (no `<img>`).

---

## 7. Responsive — the single 768px boundary (§15.2.4, NF-M15-1)

Mobile-first. ONE load-bearing boundary, mutually-exclusive queries:

```css
/* phone: list only */
.nav-map  { display: none; }
.nav-list { display: block; }

/* tablet + desktop */
@media (min-width: 768px) {
  .nav-list { display: none; }
  .nav-map  { display: block; }
}
```

- **Phone (≤767px, floor ~320px):** `.nav-list` shown, `.nav-map` hidden. 19
  full-width ≥44px rows, vertical scroll, optional reduced header banner. No
  horizontal scroll.
- **Tablet (~768–1023px):** `.nav-map` shown — the **smallest scene render
  scale**, the R-M15-7 legibility/≥44px watch point (sized in §2).
- **Desktop (≥1024px):** `.nav-map` scales up to its `max-width` cap; richest
  read. No node drifts (same viewBox).
- **Landscape phone** (wide but <768px) uses the list (boundary is width-based).
- Fluid primitives: `viewBox`+`preserveAspectRatio="…meet"` for the scene;
  `clamp()`/`min()`/`max()` for the `.nav-map` cap and `.nav-list` row
  height/padding/type. No fixed-pixel layout, no `width:130vw` pannable surface.

---

## 8. Reduced motion + a11y (NF-M15-7, R-M15-6/8/9) — extend, don't edit

- All new motion is `transform`/`opacity` (+ bounded SVG `filter` for fog, the
  existing cost). The reused ambient spans are ALREADY frozen by the existing
  `@media (prefers-reduced-motion: reduce)` block (same selectors) — inherited
  for free. The ONLY new freeze rules needed are for the new **sconce-flame
  breathe** (Horror) and any **sun-glow breathe** (Sea) → freeze to steady
  opacity (like the M14 sun-breathe / M9 doorway-flicker freeze). No flicker
  exceeds the M9 "well under 3 flashes/sec" bar.
- **Keyboard:** the 19 `.nav-node` `<a>`s are authored in id order 0..18 so tab
  order = id order; an explicit SVG focus `<rect>`/`outline` gives a visible
  focus indicator inside the SVG (R-M15-8). The `.nav-list` is plain HTML (no
  such concern). Visible focus on both representations.
- **Decorative inertness (incl. the new backdrop):** the z-0 `.nav-backdrop`,
  the `.nav-scene`, the z-1 `.atmosphere` + ambient blocks, and the optional
  header banner are ALL `aria-hidden`/`pointer-events:none` (SVGs also
  `focusable="false"`/no-`tabindex`). The backdrop is a CSS `background-image`
  (no `<img>`, so no `alt`/a11y surface at all). The ONLY focusable elements are
  the 19 `.nav-node` / `.nav-list-item` `<a>`s.
- **Backdrop + scrim are static** — the `.nav-backdrop` only crossfades on theme
  toggle (a `--t-transition` opacity/background transition, not a keyframe), so it
  needs no reduced-motion freeze. The only new motion to freeze remains the
  sconce-flame / sun-glow breathe (already handled).
- **Font-scaling path (R-M15-9):** the HTML `.nav-list` (real `rem`/`clamp()`
  text) is the accessible font-scaling path; the SVG map labels are kept generous
  (§2) but documented as not responding to user font scaling — by design.

---

## 9. Tokens used (NO new tokens, NO `:root` edits) — NF-M15-3

Everything is built from the EXISTING token system, theme-scoped:

| Token | Role in the landing scene |
|---|---|
| `--page-bg-image` | full-bleed field behind the SVG (navy night / sky-sea) — unchanged |
| `--vignette` | focal glow (moonlit doorway / low sun) + edge vignette — unchanged |
| `--bg`, `--bg-2` | scene gradient stops, node backing plates |
| `--accent`, `--accent-soft` | Horror amber door glow / focus ring; Sea azure surf / focus ring |
| `--fg`, `--muted` | node/list numbers + names; logo/toggle text |
| `--tile-bg`, `--tile-border`, `--tile-shadow` | Sea island sand, list-id chips, sealed plates |
| `--t-transition` (1.5s) | theme repaint crossfade on toggle — preserved |

New CSS class families (ONLY ever styled under `.theme-horror`/`.theme-sea`;
shared-by-name leaves like `.map-hotspot` was):
`nav-backdrop` (NEW, z-0 painted backdrop), `nav-map`, `nav-scene`, `nav-node`,
`nav-node-glyph`, `nav-node-hit`, `nav-node-plate` (NEW per-theme opaque node
backing), `nav-node-label`, `nav-node--sealed`, `nav-list`, `nav-list-item`,
`nav-list-item--sealed`, `nav-list-id`, `nav-list-name`. Keep
`horror-landing`/`sea-landing` as the theme-scoped landing wrapper (CSS hook).
No bare rules; no collision with the M14 level `.horror-scene`/`.sea-scene`.

The N7 hybrid REUSES the two raster maps (`landing-map.v2.jpg` /
`landing-map.v2.webp`) as the z-0 `background-image` (no new tokens, no `:root`
edits — just a theme-scoped `background-image` URL + the scrim layered into the
existing `.atmosphere` background).

---

## 10. Handoff notes / deviations from ARCHITECTURE §15

- **No deviation in model, technique, or contract — now the N7 HYBRID.** This
  design follows §15 (incl. the N7 revision at §15.2.3/§15.3/§15.4/§15.7)
  exactly: a z-0 painted `.nav-backdrop` (`cover`, theme-conditional
  `background-image`, the two REUSED `.v2` maps) → a z-1 themed scrim/vignette/fog
  `.atmosphere` for legibility → a z-2 ELEVATED filter-crafted inline-SVG
  `.nav-map` scene + 19 in-`viewBox` `.nav-node` `<a>`s; two SSR representations
  CSS-toggled at one 768px boundary; one `viewBox="0 0 1600 900"
  preserveAspectRatio="xMidYMid meet"`; 19 `.nav-node` `<a>`s in id order + 19
  `.nav-list-item a`s with byte-identical `aria-label`s;
  `nav-node--sealed`/`nav-list-item--sealed` ⇔ `id ∉ available_ids`; preserved
  logo/toggle/ambient/audio/prefetch; `?calibrate` + the pixel-pinned raster
  `<img>` + `.map-hotspot` overlay + `coords`/`sea_coords` removed; the two `.v2`
  maps KEPT (reused as backdrops, active-theme preloaded); `sea_names` KEPT as the
  `aria-label` source on BOTH representations; reuse tokens + reduce freeze; ZERO
  backend change.

### 10.0 N7 HANDOFF DELTA — what is NEW vs the prior (N2 pure-SVG) handoff

Everything from the prior handoff stands (the functional model — SVG map → mobile
list, drift-free nav, one 768px reflow, 19 nodes/list items, sealed set, preserved
chrome/audio/prefetch, zero backend). The N7 hybrid ADDS, on top of it:

1. **`.nav-backdrop` (NEW z-0 div).** A `<div class="nav-backdrop"
   aria-hidden="true">` BENEATH `.atmosphere`, `position:fixed; inset:0;
   z-index:0; background-size:cover; background-position:center;
   pointer-events:none`.
2. **Theme-conditional backdrop `background-image`.** `.theme-horror .nav-backdrop
   { background-image:url("/static/img/horror/landing-map.v2.jpg") }` /
   `.theme-sea .nav-backdrop { background-image:url("/static/img/light/landing-map.v2.webp") }`.
   The two `.v2` maps are now KEPT (the N2 "delete the maps + drop the preload" is
   REVERSED).
3. **Active-theme backdrop preload.** SSR emits `<link rel="preload" as="image"
   fetchpriority="high" href="…active-theme map…">` keyed off the `theme` cookie;
   the inactive theme's map loads lazily on toggle. (The OLD `.map-hotspot`-era
   `<img fetchpriority="high">` stays removed — that `<img>` is gone.)
4. **`.atmosphere` moves z-0 → z-1 and gains a themed SCRIM.** A semi-opaque
   themed wash layered into its `background` (Horror deep-navy radial, Sea soft
   azure→white) so the painting doesn't fight the SVG/labels. `--vignette` + fog
   `::before/::after` reused unchanged. `.layer` moves z-1 → z-2.
5. **ELEVATED SVG fidelity (the user's core feedback).** The `.nav-scene` gains
   real SVG craft: `feTurbulence` grain, `feGaussianBlur` fog/glow/haze,
   `feDropShadow` lift, `feSpecularLighting`+`fePointLight` sheen, richer
   multi-stop gradients + ornament (sconces/cobwebs/moonlight shaft | compass/
   routes/surf/palms). Non-focal fields go translucent + `mix-blend-mode` so the
   painting shows THROUGH; nodes stay crisp.
6. **`.nav-node-plate` (NEW) + per-node drop-shadow LIFT (R-M15-11).** A small
   OPAQUE themed backing behind each number + `drop-shadow` on `.nav-node-glyph`
   so labels stay legible over ANY backdrop region. (Sea already had a plate;
   Horror now gets one too + the lift.)

**What is UNCHANGED from the prior handoff:** the `.nav-map`/`.nav-list` classes,
the `viewBox`, the 768px boundary, the 19-node/19-row contract, the sealed set
{0,3,4,5,6,7}, the `aria-label` strings, the preserved logo/toggle/ambient/audio/
prefetch, and ZERO `app/main.py` change.
- **Mockup-only simplifications (NOT build intent):**
  - The mockups inline their CSS and use a lightweight `theme-toggle.js` instead
    of the real `theme.js`/`audio-engine.js`/prefetch (look/feel artifacts only).
    The real build moves these rules into theme-scoped blocks in
    `static/style.css` and keeps the real scripts.
  - The mockups draw a **representative** elevated scene (enough doors / islands,
    fog, sconces, compass, routes, `feTurbulence` grain, `feDropShadow` lift,
    `feSpecularLighting` sheen to judge fidelity + node placement). The build
    authors the full 19-node art at sign-off polish — same vocabulary, same
    `<filter>`s, same `viewBox`, same node contract.
  - **The mockups use the REAL existing maps as the z-0 `.nav-backdrop`** —
    referenced by relative path from `design/mockups/`
    (`../../static/img/horror/landing-map.v2.jpg` /
    `../../static/img/light/landing-map.v2.webp`) so the reviewer sees the ACTUAL
    hybrid effect: the painting renders behind the elevated SVG with legible
    nodes. The mockups do NOT emit the `<link rel=preload>` (a real-SSR concern);
    the backdrop is a plain theme-scoped `background-image`.
  - The mockups render BOTH `.nav-map` and `.nav-list` in the DOM and toggle them
    with the REAL 768px media query (resize to verify), exactly as the build will
    SSR both and toggle them — this is the load-bearing reflow proof. The toggle
    also swaps the `.nav-backdrop` painting (Horror ⇄ Sea) so the hybrid flip is
    felt from either file.
- **`?v=7 → ?v=8` cache-bust** on BOTH `index.html` and `level.html` `<link>` at
  build time (A-M15-4; contract-safe, guard accepts any `?v=\d+`).
- **Open visual questions flagged to PM/ARCHITECT (none block the build):**
  - **R2 (Sea labels):** this design KEEPS `sea_names` as the `aria-label` source
    on both representations and surfaces the name in the mobile `.nav-list-name`
    (per A-M15-2 sign-off). If the user prefers numbers-only Sea labels, drop
    `sea_names` — single-dict change.
  - **A-M15-3 (`landing-map.png` provenance):** keep the M10 design-source PNG as
    provenance even though the two derived `.v2` raster maps are deleted; confirm
    delete-everything vs keep-the-source.
  - **R-M15-7 (tablet-floor node detail):** if 19 fully-detailed doors/islands
    read as cluttered at the ~768px floor, the build may simplify per-node detail
    at small scale (CSS `@media`-gated SVG detail) OR nudge the map↔list boundary
    slightly up — verify with the user at N3/N6 sign-off. The mockups' node
    sizing already targets ≥44px + legible labels at 768px.
</content>
</invoke>
