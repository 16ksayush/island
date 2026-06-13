# M16 — Chest-chooser gateway design notes

UI_UX_DESIGNER · TD step for M16 (`/` neutral gateway + chest reveals) · 2026-06-13

These notes are the visual/interaction contract the FRONTEND_ENGINEER builds the
real `templates/gateway.html` + `static/gateway.js` + scoped `static/style.css`
rules from. They are **design intent + class/z-stack + motion storyboard**,
faithful to `docs/REQUIREMENTS.md` §17 and `docs/ARCHITECTURE.md` §17 (D14–D24).

> **PAINTED-BACKDROP REVISION (2026-06-13).** The gateway scene is now a **PAINTED
> RASTER backdrop** — `static/img/gateway/gateway-bg.jpg` (a dragon on a glittering
> gold/jewel hoard inside a torch-lit stone vault, with a moonlit pointed archway
> behind it and two wall torches) — set as a full-bleed `cover` background on
> `.gateway`. This **REPLACES the earlier hand-drawn CSS+SVG scene** (the
> `.gw-lair` vault/arch/pillars/torches, the `.gw-dragon`, and the
> `.gw-hoard--back/front` treasure SVGs were all deleted). It **revises the earlier
> "pure CSS + inline SVG, no raster" intent for the gateway** — consistent with the
> landing maps, which are also raster `background: cover` paintings. Only the
> **interactive FRONT layer stays CSS+inline-SVG**: the three chest `<button>`s, the
> `<h1>` speech-bubble heading, the `.brand-logo`, the `.gw-scrim`, and the z-90
> reveal ghost/cake. The chests/bubble/logo are sized with `clamp()`/flex and are
> **NOT pinned to painted pixels** — the painting covers/crops independently behind
> them. The mockup references the image at the RELATIVE path
> `../../static/img/gateway/gateway-bg.jpg` (opened via `file://`); **production uses
> the absolute `/static/img/gateway/gateway-bg.jpg`.** No new JS dependency, no new
> secret (NF-M16-7).

Pure CSS + inline SVG for the front layer + one raster backdrop image — no
GIF/Lottie, no new JS dependency, no new secret (NF-M16-3 / NF-M16-7, M14/M9
ethos).

The companion **clickable mockup** makes this tangible:
- `design/mockups/gateway.html` — the neutral chest-chooser with a working
  cursive heading, three responsive chests (middle largest), and a WORKING reveal
  animation on click/Enter/Space for each chest: ghost-zoom (chest 1), random
  ghost-or-cake (chest 2), cake-zoom (chest 3). On reveal-complete it navigates to
  the existing `level-horror.html` / `level-sea.html` mockups (standing in for
  `/map/horror` / `/map/sea`) to prove the handoff. Honors
  `prefers-reduced-motion`; chests are keyboard-activable with `aria-label`s.
- Split assets (mirroring the M14 `m14-scene.css` / `m14-toggle.js` split):
  `design/mockups/m16-gateway.css` + `design/mockups/m16-gateway.js`.

---

## 0. What this page is (and is NOT)

`/` is a **theme-neutral gateway** (D14/D16). It carries **NO `.theme-horror` /
`.theme-sea` class** on `<html>`/`<body>` — that absence is the neutral signal,
and it means **no shared `.theme-*` rule applies here** (R-M16-10). Everything the
gateway draws lives under its own `.gateway` namespace, with its own scoped custom
properties declared **on the `.gateway` element, NOT on `:root`** (NF-M16-6 —
editing `:root` would bleed into the maps/levels). The gateway ignores any
pre-existing `theme` cookie for its own render (D16/Q-M16-12); it only WRITES the
cookie when a chest is chosen (M16R9).

It is NOT the map anymore. The two maps relocate verbatim to `/map/horror` +
`/map/sea` (D14/D18) and are out of scope here (only their URLs changed).

---

## 1. The painted backdrop + the horror×fantasy "mix" palette (scoped tokens)

> **PAINTED-BACKDROP REVISION (2026-06-13).** The whole scene is now a **single
> painted raster image**, not hand-drawn CSS gradients + SVG. See the boxed note
> at the top of this doc. The palette tokens below are kept ONLY for the FRONT
> layer (heading bubble, focus ring, ink) — the moon/sun/seam *field* gradients
> and the dragon/lair/hoard SVG tokens were **deleted** with the scene they fed.

The backdrop reads as **both realities at once** — a torch-lit stone vault where a
dragon broods on a gold hoard under a cool moonlit archway: haunted-gothic gloom +
warm fantasy treasure, neither pure Horror nor pure Sea. That horror×fantasy "mix"
is now carried entirely by the **painting** (`gateway-bg.jpg`).

**Backdrop wiring** (`.gateway` background — full-bleed `cover`, mirroring the
landing-map cover pattern):

```css
.gateway {
  background:
    url(/static/img/gateway/gateway-bg.jpg) center top / cover no-repeat,
    #0c0814;                 /* dark fallback if the image is missing */
  background-attachment: fixed, fixed;
}
```

- `center top / cover` fills any viewport and **crops gracefully at the edges**,
  keeping the dragon's head **uncropped** even on tall/narrow screens (the
  composition has its dragon head high-centre, so `top` anchoring protects it).
- The mockup uses the RELATIVE path `../../static/img/gateway/gateway-bg.jpg`
  (opened via `file://`); production uses the absolute
  `/static/img/gateway/gateway-bg.jpg`.

All FRONT-layer tokens are declared on `.gateway` (NOT `:root`, NOT `.theme-*`):

```css
.gateway {
  --gw-ink:        #fdf3df;  /* warm parchment text / hint                    */
  --gw-focus:      #ffd970;  /* focus ring — gold, legible on the painting    */
  --gw-reveal:     1100ms;   /* chest-open → zoom-to-fullscreen duration      */
  --gw-ease:       cubic-bezier(0.6, 0.02, 0.2, 1);
  --gw-t:          1.5s;     /* matches the app --t-transition for parity      */
  /* --- DARK glowing speech-bubble set (sign-off pass 2026-06-13) --- */
  --gw-bubble:     #140e1f;  /* smoky dark balloon fill (near-obsidian violet) */
  --gw-bubble-2:   #241634;  /* lifted smoky edge for the bubble gradient      */
  --gw-bubble-ink: #ffce5a;  /* GLOWING amber cursive text (AAA on the fill)   */
  --gw-bubble-glow:#ffb000;  /* amber rim/halo glow around the dark bubble     */
}
```

> **Removed tokens (no longer used after the painting replaced the SVG scene):**
> `--gw-night/-2`, `--gw-dawn/-2`, `--gw-seam`, `--gw-ink-soft`, `--gw-amber`,
> `--gw-azure`, `--gw-wood/-2`, `--gw-band/-2`, `--gw-gold/-deep`, `--gw-dragon`,
> `--gw-dragon-lit`, `--gw-arch`, `--gw-torch`. (The chest SVGs carry their own
> literal wood/brass fills inline, so they need no scoped tokens.)

### The decorative SCRIM (replaces the old fog band)

A single inert `.gw-scrim` (`position:fixed; inset:0; pointer-events:none;
aria-hidden`) lays a vertical gradient over the painting: a **soft TOP scrim** so
the speech bubble stays legible near the painted dragon's head, a **transparent mid
band** so the painted dragon/arch read at full strength, and a **stronger BOTTOM
scrim** that gives the chests a consistent dark "floor" no matter how the painting
crops across aspect ratios. It is tuned NOT to wash the painting out. (The old
drifting `.gw-atmosphere` fog SVG/CSS was removed — the painting carries its own
atmosphere.)

### History — the hand-drawn scene this revision REPLACES (2026-06-13)

> The earlier gateway built the dragon's-lair scene by hand in **CSS + inline
> SVG**: a `.gw-lair` (stone vault + pointed arched doorway + pillars + two
> flickering `.gw-torch` braziers), a big rim-lit central guardian `.gw-dragon`
> (3/4 head, ribbed membrane wings, clawed forelimbs, spined tail — built to dodge
> a "flat bat/moth" failure), `.gw-hoard--back/--front` treasure piles, and a
> `.gw-atmosphere` fog band. The user then generated a **painted** dragon-vault
> backdrop, so all of those hand-drawn layers (and the scoped tokens that only fed
> them) were **deleted** in favour of `gateway-bg.jpg`. The interaction contract,
> the chests, the speech-bubble heading, the logo and the reveal are unchanged —
> only the *art delivery* changed (hand-SVG → raster), consistent with the landing
> maps which are also raster paintings.

### Responsive cropping (NF-M16-1)

The painting **covers/crops** behind everything; only the FRONT layer reflows. On
wide screens the dragon's head sits high-centre with the bubble just below it and
the chest row resting on the painted gold band. On narrow screens the painting
stays `center top` (head uncropped), the bubble shrinks + wraps to the upper band
(`width:min(82vw,18rem)`, never clips), and the chest row becomes a centred column
(DOM order 1→2→3, middle still largest by its larger `clamp()` width) sitting on
the painted hoard. The chests/bubble/logo scale via `clamp()`/flex **independent of
the painted pixels** — verified at 1600×900 and 390×780: no horizontal scroll,
chests never clipped, middle largest, dragon head uncropped.

### Contrast / accessibility of the palette

| Foreground | Background sampled | Ratio | Verdict |
|---|---|---|---|
| `--gw-bubble-ink` `#ffce5a` heading | dark bubble fill `#140e1f` | ~9.6:1 | AAA |
| `--gw-focus` `#ffd970` ring | mid field `#2a2138` | ~9.6:1 | AAA |
| `--gw-ink` `#fdf3df` (secondary marks) | darkest field `#100c1a` | ~16.5:1 | AAA |
| `--gw-ink-soft` `#c9bcd6` | mid field `#2a2138` | ~6.3:1 | AA |

> The heading text now lives **inside the dark bubble** (amber on near-obsidian),
> so its contrast is fixed at ~9.6:1 regardless of where the bubble sits over the
> busy scene — comfortably AAA and well past the requested AA-for-large bar.

The cursive heading sits over the **dark** (left/centre) portion of the field by
design (it is centred above the chests, where the field is twilight, not the warm
corner) so its contrast is comfortably AAA. A soft `text-shadow` scrim
(`0 2px 18px rgba(10,8,20,0.7)`) guards it even where the warm wash creeps in
(NF-M16-2). Chest `aria-label`s carry the accessible name (symbols are decorative),
so contrast of the symbols themselves is not a text-legibility gate — but they're
drawn light-on-dark anyway.

---

## 2. The cursive heading "choose a chest" — TRANSPARENT glowing caption (lowered)

> **Sign-off revision 2026-06-13 (latest).** The dark balloon covered the painted
> dragon's FACE, so the heading is now a **TRANSPARENT** treatment: NO balloon fill,
> NO border, NO box-shadow, NO tail/pseudo-elements — just the glowing amber cursive
> text sitting directly over the painting. It is **smaller** (`font-size: clamp(1.4rem,
> 4.4vw, 2.6rem)`) and **lowered** (`.gw-heading { margin: auto auto 0 }` banks the
> free space above it so it sits in the lower-middle), keeping the painted dragon's
> head/face fully visible up top. Legibility over the busy painting comes from a
> layered `text-shadow` — a dark halo (`0 2px 6px rgba(0,0,0,0.92)` + `0 0 4px`) plus
> the amber glow (`0 0 12px rgba(255,176,0,0.7)`, `0 0 26px rgba(255,140,0,0.45)`).
> Still the real semantic `<h1 class="gw-heading" id="gw-heading">` with the Cinzel
> Decorative face. The earlier dark-balloon/tail/pulse description below is retained
> as history (superseded). The `--gw-bubble*` tokens are now unused and can be dropped
> at build time.
>
> --- *superseded (dark balloon pass) below* ---
>
> **Sign-off revision 2026-06-13.** The dragon **speaks the prompt** from a smoky
> **DARK** speech balloon with **GLOWING AMBER cursive** text. The balloon fill is
> a near-obsidian violet radial (`--gw-bubble #140e1f` → `--gw-bubble-2 #241634`)
> with a smoky inset shadow; the text is glowing amber `--gw-bubble-ink #ffce5a`
> carrying a layered amber `text-shadow` halo; the balloon has a thin amber border
> + an amber outer glow that gently **pulses** (`gw-bubble-pulse`, frozen under
> reduced-motion). The triangular **pointer/tail** (`.gw-heading::before` glowing
> edge + `::after` dark fill, both centred) aims **straight UP toward the central
> dragon's mouth**; a faint smoky breath-trail (`.gw-speech` sibling, `aria-hidden`)
> bridges balloon→mouth on wide screens. CRITICAL invariant kept: this is **still
> the page's real semantic `<h1 class="gw-heading" id="gw-heading">`** — element/
> class/id and the cursive Cinzel Decorative face unchanged; only the styling
> becomes the bubble (tail = pseudo-elements, trail = decorative sibling).
>
> **Contrast / legibility.** Amber `#ffce5a` text on the `#140e1f` smoky fill is
> **≈ 9.6:1 → AAA** (well past the AA-for-large-display bar the user asked for; it
> would pass AA even at body-text size). On narrow screens the bubble stays centred
> but **drops to the mid band below the reared head** and is constrained to
> `width:min(80vw,18rem)` so the amber text **wraps to two lines and never clips**
> (verified at 360px / 390px); its tail still aims up to the cropped-overhead head.


**Font choice (Q-M16-5): `Cinzel Decorative`** as the gateway display face, with a
system fallback stack of `"Luminari", "Papyrus", "Pirata One", cursive, serif`.

Rationale: M15's two faces are theme-CODED — `Pirata One` reads pure gothic-horror,
`Tangerine` reads pure airy-calligraphy-Sea. The neutral gateway needs a face that
**bridges gothic + fantasy**: `Cinzel Decorative` is an ornate, flared Roman-display
letterform with engraved/inscriptional fantasy gravitas (think rune-stone /
storybook title) that also carries a dark-fairytale edge — it reads as neither
"haunted house" nor "beach," but "the threshold of a tale." It is a Google Font, so
it loads via the **exact M15 pattern** (non-blocking, `display=swap`), and degrades
to the system cursive/serif fallback with no first-paint block (M16R11).

> Note for the engineer: `Cinzel Decorative` is technically a decorative *serif*,
> not a connected script. The requirement word is "cursive" in the loose
> display-lettering sense; `Cinzel Decorative` satisfies the **neutral, bridges
> horror+fantasy** intent better than any connected script (connected scripts skew
> either spidery-horror or pretty-Sea). If the user specifically wants a *flowing
> connected* hand, the documented alternative is **`Eagle Lake`** (a gothic-storybook
> script) — swap is one font-family line. **Flagged for sign-off (see §9).**

Font load (head of `gateway.html`, mirrors `templates/level.html` M15 block):

```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link rel="stylesheet"
  href="https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@700;900&display=swap" />
```

Type spec:

| Property | Value |
|---|---|
| family | `"Cinzel Decorative", "Luminari", "Papyrus", cursive, serif` |
| weight | 900 (heading) |
| size | `clamp(2.2rem, 8vw, 5rem)` — fills phone→desktop without overflow |
| letter-spacing | `0.04em` |
| color | `--gw-ink`, with the gold seam echoed via a subtle `text-shadow` warm rim |
| line-height | 1.05 |
| text-align | center |
| margin | top `clamp(2rem, 8vh, 6rem)`, bottom `clamp(1.5rem, 5vh, 3rem)` |

The heading is the page's real `<h1 lang="en">choose a chest</h1>` (assistive-tech
reachable, NF-M16-2). Casing is **lowercase "choose a chest"** verbatim from the
user request / Q-M16-5. Nothing else textual on the page (M16R2).

---

## 3. The three chests — component anatomy

**Uniform wooden chests, differentiated ONLY by the symbol** (Q-M16-11 / M16R5).
Each chest is ONE inline-SVG drawing inside a real focusable `<button>`. No text
on the chest (M16R5). The symbol floats on the chest lid.

```
<button class="gw-chest gw-chest--1" aria-label="Open the moon chest — enter the haunted corridor">
  <svg class="gw-chest-art" aria-hidden="true" focusable="false"> … lid + body + lock + SYMBOL … </svg>
</button>
```

Symbols (inline SVG, `aria-hidden`):
- **Chest 1 — moon:** a crescent moon (cool silver-lilac fill `#dfe4ff`, faint glow).
- **Chest 2 — half-sun/half-moon (largest):** a disc split down the vertical axis —
  left half a crescent-moon cut (cool), right half a sun with rays (warm amber). It
  visually states "either realm" (D21).
- **Chest 3 — sun:** a full sun with rays (warm amber `#ffce6b`, glow).

### Chest STATES (the engineer implements all five)

| State | Visual |
|---|---|
| **rest** | Lid closed, sitting flat; soft drop shadow; symbol glows gently (slow opacity breathe, reduced-motion-frozen). |
| **hover / focus** | Chest lifts ~6px (`translateY`), shadow deepens, symbol glow intensifies, a thin gold rim (`--gw-band`) brightens. Focus adds a **visible focus ring** `0 0 0 3px var(--gw-focus)` (NF-M16-2 — keyboard parity). |
| **active (pressed)** | Quick ~2px press-down for tactile feedback. |
| **opening** | On activation: lid rotates open (`transform: rotateX(-110deg)` about its back-top hinge, ~280ms `--gw-ease`), a warm/cool light spills from inside, and the reveal element (ghost/cake) begins to emerge from the chest mouth. The chest stays put; the reveal takes over the viewport (§5). |
| **disabled** | (not used — all three always active.) |

### Layout & responsiveness (M16R4 / NF-M16-1)

The chests live in a flex container `.gw-chests` that **reflows by viewport**, with
the **middle chest always the largest**:

```
WIDE (≥ 720px):   row, baseline-aligned, gap clamp(1rem,3vw,3rem)
                  [ chest1 ]   [  CHEST 2  ]   [ chest3 ]
                    1.0x          1.5x           1.0x        (middle 50% larger)

NARROW (< 720px): column, centred, vertical gap clamp(1rem,4vh,2rem)
                       [  CHEST 2  ]   ← largest still reads as the hero, placed FIRST
                       [ chest1 ]      ← (or keep DOM order 1/2/3 and just scale —
                       [ chest3 ]         see note below)
```

Sizing uses `clamp()` so nothing clips on a 320px phone or overflows a wide
desktop:

```css
.gw-chest        { width: clamp(116px, 22vw, 220px); }   /* side chests */
.gw-chest--2     { width: clamp(168px, 32vw, 320px); }   /* middle: ~1.45–1.5x */
```

- **DOM order is always 1, 2, 3** (moon, half, sun) so keyboard/tab order and screen
  reader order read left-to-right "moon, both, sun." On narrow screens we DO NOT
  reorder the DOM (a11y) — the column simply stacks 1→2→3 and the middle chest is
  still visibly the largest by its `clamp()` width. (The ASCII above shows an
  optional `order:` hero-first variant; the **recommended build keeps DOM order**
  for predictable focus traversal — flagged minor in §9.)
- No horizontal scroll at any width; `.gw-chests { flex-wrap: wrap }` is the safety
  net on awkward mid-widths.
- The reveal zoom (§5) is `position:fixed; inset:0`, so it fills the **actual**
  viewport regardless of the chest's rendered size (NF-M16-1).

---

## 4. The z-stack / DOM contract

```
(paint)  .gateway background ............ PAINTED dragon-vault raster, cover (§1)
  z-0    .gw-scrim (aria-hidden) ........ DECORATIVE scrim, fixed inset:0, p-e:none
            └─ top scrim (bubble legibility) + transparent mid + bottom "floor"
  z-1    .gw-stage (content) ............. <h1> SPEECH BUBBLE + .gw-chests (3 buttons)
            └─ .gw-stage-fill (aria-hidden) flexible spacer → pushes chests to hoard
  z-5    .brand-logo (REAL link) ......... overlaid top-left app logo (M16R15), home
  z-90   .gw-reveal (aria-hidden) ........ fixed inset:0, pointer-events:none, HIDDEN
            ├─ .gw-reveal-ghost (SVG) ....  shown+animated for horror picks
            ├─ .gw-reveal-cake  (SVG) ....  shown+animated for sea picks
            └─ .gw-reveal-veil  ..........  full-bleed wash that fades the gateway out
```

> **Painted-backdrop revision (2026-06-13).** The painting IS the backdrop (the
> `.gateway` `cover` background), so the former z-0 decorative SVG layers
> (`.gw-atmosphere` fog, `.gw-lair` vault/arch/pillars/torches, `.gw-dragon`
> guardian, `.gw-hoard--back/--front` treasure, `.gw-speech` breath-trail) are all
> **GONE**. What remains on top of the painting: the inert `.gw-scrim` (z-0), the
> content stage at z-1 (the DARK glowing speech-bubble `<h1>` near the painted
> dragon's head + the three chest buttons resting on the painted gold hoard, pushed
> there by the `.gw-stage-fill` flex spacer), the `.brand-logo` at z-5, and the
> z-90 reveal. The bubble's tail is still the `<h1>` `::before` (glowing amber edge)
> + `::after` (dark fill) pseudo-elements aimed UP at the painted mouth. Everything
> stays BELOW the z-90 reveal, so the open→zoom still covers the WHOLE viewport (the
> painting included). The chest focus ring keeps its strengthened dark contrast
> collar + soft glow under the gold ring so it stays clearly visible over the busy
> painted gold (NF-M16-2 / §9 a11y invariant 9).

**App brand mark (M16R15 — top-left, present on every page incl. the gateway).**
The gateway carries the same shared logo as the maps/level pages — `<a class="brand-logo"
href="/"><img class="app-logo" src="/static/img/logo/create_thumb.png" …></a>`, the white
rounded 44px badge from `static/style.css` (§"App brand mark"). It links to `/` (self) as
the persistent home affordance. It is a REAL link, NOT `aria-hidden`, and sits at z-5 —
above the content stage, BELOW the z-90 reveal overlay so the zoom fully covers it. The
only gateway-specific delta is the focus ring: the gateway has no `.theme-*` `--accent`,
so `.brand-logo:focus-visible` uses the scoped `--gw-focus` gold instead of `var(--accent)`.

Invariants (NF-M16-2):
- The painting is a plain CSS `background` (not a DOM node, never focusable).
  `.gw-scrim`, `.gw-stage-fill` and `.gw-reveal` (incl. its `<svg>`s) are all
  `aria-hidden="true"`, `pointer-events:none`, every decorative `<svg>` is
  `focusable="false"`, and **no element carries a `tabindex`** (no interactive
  decoy). SECURITY/QA gate this. The `<h1>` text itself stays a real heading (the
  bubble is only its styling); its decorative tail is a pseudo-element with no node.
- The focusable controls on the page **remain exactly** the three chest
  `<button>`s **plus the `.brand-logo` home link** (a real, expected control —
  M16R15). The richness pass adds **zero** new interactive elements.
- `.gw-reveal` starts `display:none` / `visibility:hidden`; it is promoted to
  `position:fixed; inset:0` and shown only at activation.

---

## 5. Reveal motion storyboard (the centerpiece — D24)

Two reveals share one timeline; only the inner SVG differs (ghost vs cake). The
flow is **chest-open → emerge → zoom-to-fullscreen + fade gateway → navigate**.
All motion is GPU-cheap `transform: scale()/rotate()` + `opacity` (NF-M16-3).

### Timeline (ghost — chest 1, or chest 2 → horror)

```
t=0ms      ACTIVATE. JS computes dest=/map/horror, theme="horror".
           Archive19Theme.choose("horror")  → writeCookie + writeSession, NO reload.
           .gw-reveal un-hidden; .gw-reveal-ghost gets .is-playing.
0–280ms    LID OPENS. Chest 1's lid rotateX(0 → -110deg) about back-top hinge.
           A warm-cool light disc blooms at the chest mouth (opacity 0→1).
           Ghost SVG sits small at the chest's centre (scale ~0.18, opacity 0).
180–520ms  GHOST EMERGES. Ghost translateY rises out of the chest (~ -40px),
           opacity 0→1, with a faint wobble (skewX ±2deg) so it "floats up."
           Body has the soft ghost drift the app already uses.
420–1100ms ZOOM TO FULLSCREEN. Ghost scale 0.3 → 14 (origin = its on-screen centre,
           which is the chest), translate toward viewport centre, easing --gw-ease
           (slow anticipate, then rush). Simultaneously .gw-reveal-veil opacity
           0→1 (a deep-navy wash for horror / warm wash for sea) so the gateway
           fades out behind the growing figure. By ~950ms the viewport is the
           ghost + veil; the chests are gone.
~1100ms    animationend on the ghost's transform animation → handoff:
           if (!hasNavigated) { hasNavigated = true; location.assign(dest); }
+ GUARD    A setTimeout(navigate, --gw-reveal + 250ms) fires the SAME guarded
           navigate if animationend never arrives (R-M16-9 / D24).
```

### Timeline (cake — chest 3, or chest 2 → sea)

Identical timeline; swaps the SVG and the veil tint:
- **0–280ms** chest 3 lid opens; a warm golden light spills out.
- **180–520ms** the **cake** rises out of the chest (candles lit, a tiny flame
  flicker — slow, reduced-motion-frozen), opacity 0→1.
- **420–1100ms** cake `scale 0.3 → 14` to fullscreen; `.gw-reveal-veil` fades a
  **warm sky/sand wash** (`#fde7c0`-ish) over the gateway.
- **~1100ms** animationend → `location.assign("/map/sea")` (guarded), theme already
  set to `"sea"` at t=0.

### Chest 2 (half-sun/half-moon, largest) — D21 random

```
ACTIVATE chest 2:
  var theme = Math.random() < 0.5 ? "horror" : "sea";   // ONE coin, per click
  // SAME outcome drives BOTH the reveal art AND the destination:
  if (theme === "horror") → play the GHOST timeline → /map/horror
  else                    → play the CAKE  timeline → /map/sea
```

The coin is computed ONCE and stored, so the art and the destination can never
disagree within a click (D21). Each open re-rolls.

### Reduced-motion path (NF-M16-2 / D22 — designed explicitly)

Under `@media (prefers-reduced-motion: reduce)` AND a JS `matchMedia` guard, the
reveal is **skipped entirely**:

```
ACTIVATE (reduced motion):
  theme = (chest1 ? "horror" : chest3 ? "sea" : coin);
  Archive19Theme.choose(theme);     // cookie + session, still set first (M16R9)
  location.assign(dest);            // immediate — NO zoom, NO lid, NO flashing
```

Belt-and-suspenders: the CSS reveal keyframes are ALSO frozen inside the global
reduce block (so even if `.is-playing` were applied, nothing animates). No flicker
anywhere exceeds the app's "well under 3 flashes/sec" bar (R-M16-4). The candle/
moon glows freeze to a steady opacity.

---

## 6. Cookie-before-navigate wiring (M16R9 / NF-M16-4 / D19)

The chest selection MUST set the theme cookie + sessionStorage **synchronously
before** navigating, reusing the `static/theme.js` contract so the destination
subpage SSR-paints the chosen theme flash-free (R-M16-3). The architect adds a
no-reload `Archive19Theme.choose(theme)` export (D19) that does
`writeCookie(theme) + writeSession(theme)` WITHOUT `location.reload()`:

```
chest activate
  → theme = horror | sea (chest2 = coin)
  → Archive19Theme.choose(theme)          // writeCookie + writeSession, NO reload
  → if reduced-motion: location.assign(dest)  [done]
  → else: play reveal; on animationend (guarded) → location.assign(dest)
```

Cookie format is byte-identical to today: `theme=horror|sea; path=/; max-age=1yr;
SameSite=Lax`. In the **mockup**, `m16-gateway.js` writes the same cookie + session
itself (it can't load the real `theme.js`) and navigates to the local
`level-horror.html` / `level-sea.html` files as stand-ins for the map subpages — so
the reviewer sees the full open→zoom→handoff without a backend.

---

## 7. Accessibility summary (NF-M16-2)

- Three chests are real `<button type="button">` controls — mouse/touch AND
  keyboard (Enter/Space) activate them (M16R10).
- Each has a descriptive `aria-label` (symbols are text-free):
  - chest 1: `"Open the moon chest — enter the haunted corridor"`
  - chest 2: `"Open the twin chest — enter a random realm"`
  - chest 3: `"Open the sun chest — enter the sunlit archipelago"`
- Visible focus ring on every chest (`--gw-focus`, ≥3px, AA-contrast). The ring
  keeps a dark contrast collar + soft glow under the gold so it stays legible
  against the busier/darker torch-lit vault backdrop.
- Real `<h1 lang="en" id="gw-heading">choose a chest</h1>` present for assistive
  tech — unchanged semantics; the speech-balloon is styling only (tail = pseudo-
  element, breath-trail = decorative `aria-hidden` sibling).
- Decorative layers (`.gw-scrim`, `.gw-stage-fill`, `.gw-reveal` + all decorative
  `<svg>`) are `aria-hidden` + `pointer-events:none` + `focusable="false"` + NO
  `tabindex`. The painted backdrop is a CSS `background`, never a DOM node.
- `prefers-reduced-motion` skips the reveal and goes straight to the destination
  (§5), and freezes ALL remaining gateway motion — the chest symbol-glow, the
  lid/inner-glow, the cake candle flame, the reveal veil/objects, AND the dark
  bubble's `gw-bubble-pulse` glow. The bubble holds its lit amber-on-dark state
  statically. (The old ambient animations — fog, torch flicker, hoard glints,
  dragon breath/eye/wing — are gone with the SVG scene the painting replaced.)
- WCAG AA contrast maintained for the heading + focus rings against the mix field
  (§1 table).

---

## 8. Responsive breakpoint behavior (NF-M16-1 — summary)

| Breakpoint | Layout |
|---|---|
| `≥ 720px` (tablet/desktop) | `.gw-chests` is a **row**, baseline-aligned; side chests `clamp(116px,22vw,220px)`, middle `clamp(168px,32vw,320px)` (~1.5×). Heading `clamp(2.2rem,8vw,5rem)`. |
| `< 720px` (phone portrait) | `.gw-chests` is a **column** (`flex-direction:column`), centred; DOM order preserved (1,2,3); middle still visibly largest via its larger `clamp()`. Generous tap targets (≥44px). |
| any | `flex-wrap:wrap` safety net; no horizontal scroll; reveal `position:fixed inset:0` fills the true viewport. |

One raster backdrop (`gateway-bg.jpg`, 1584×672, ~378 KB) plus a few KB of CSS +
inline SVG (chests + reveal) + one Google-Font request (non-blocking). The image
loads `cover` like the landing maps; the dark `#0c0814` fallback colour shows if it
is ever missing (graceful, no error).

---

## 9. Handoff notes / deviations + open visual questions

- **No architectural deviation.** This design follows ARCHITECTURE §17 D14–D24
  exactly: `/` = neutral `.gateway` (no `.theme-*`, scoped tokens, no `:root`
  edit — D16/NF-M16-6); maps at `/map/horror`+`/map/sea` (D14); pure CSS+SVG
  reveal, scale+fade, `animationend` + guarded fallback timer (D24); reduced-motion
  skips the reveal (D22); chest 2 = client `Math.random()<0.5` (D21);
  `Archive19Theme.choose()` cookie-before-navigate (D19/M16R9).
- **Mockup-only simplifications (NOT build intent):** the mockup writes the cookie
  itself and navigates to the local `level-horror.html`/`level-sea.html` files in
  place of `/map/horror`//`/map/sea` (no backend). The real build calls
  `Archive19Theme.choose()` from the loaded `theme.js` and assigns the real
  subpage URLs. The mockup inlines/links its own CSS rather than editing
  `static/style.css`; the build moves these rules into a scoped `.gateway` block in
  `static/style.css` and bumps `style.css?v=` (NF-M16-9).
### Painted-backdrop revision (2026-06-13) — supersedes the hand-drawn scene
- The user generated a **painted dragon-vault backdrop** and we switched the
  gateway from the hand-drawn CSS+SVG scene to that raster. **Build contract:** set
  the `.gateway` background to
  `url(/static/img/gateway/gateway-bg.jpg) center top / cover no-repeat, #0c0814`
  with `background-attachment: fixed` (mirror the landing-map cover pattern); the
  mockup uses the relative `../../static/img/gateway/gateway-bg.jpg`. The image is
  already committed at `static/img/gateway/gateway-bg.jpg` (1584×672, ~378 KB).
- **Removed:** the `.gw-lair` (+ `.gw-torch`), `.gw-dragon`, `.gw-hoard--back/front`
  and `.gw-atmosphere` (+ `.gw-speech`) blocks and the scoped tokens that only fed
  them (see §1 "Removed tokens"). **Added:** a single inert `.gw-scrim` gradient
  overlay (top + bottom scrim, transparent middle) + a `.gw-stage-fill` flex spacer
  that pushes the chest row down onto the painted hoard.
- **Front layer (scales independently of the painting):** the speech-bubble `<h1>`
  pins to the upper band near the painted dragon's head; the three chest buttons
  (middle largest) rest on the painted gold hoard in the lower-centre; the
  `.brand-logo` stays top-left. All sized with `clamp()`/flex — NOT pinned to
  painted pixels. The z-90 reveal still covers the whole viewport, painting included.
- **Untouched:** `m16-gateway.js`, every JS hook, the 3 chest buttons + `.brand-logo`,
  the reveal ghost/cake/veil. No `.theme-*` / `:root` edits; theme-neutral.
- **Verified visually** at 1600×900 and 390×780: painting fills + dragon head
  uncropped; all three chests + symbols + logo fully visible and legible on the
  hoard; bubble reads near the dragon; no horizontal scroll on mobile; middle chest
  visibly largest; gold focus ring (dark collar + glow) clearly visible over the
  painted gold.

### Dragon + bubble sign-off revision (2026-06-13) — HISTORY (hand-drawn scene, now replaced)
- The user reviewed the torch-lit-vault render and gave three decisions, all now
  applied (see §1 "SIGN-OFF REVISION" + §2): (1) **bigger/brighter/more central**
  rim-lit dragon; (2) **rising-centre guardian** pose — reared head/neck behind the
  middle chest, wings to BOTH sides, forelimbs gripping the hoard, tail curling
  right; (3) **dark glowing-amber** speech bubble replacing the light parchment.
- To dodge the earlier "flat bat/moth" failure with a now-central dragon, "dragon"
  is carried by a big LIT 3/4 **head** (long snout, jaw + fangs, brow, two horn
  pairs, glowing slit eye) and **ribbed membrane wings** with wrist-claws — not the
  silhouette. The figure is rim-lit (warm torch + cool archway) so it is never a
  near-black blob. Verified visually at **1600×900** and **390×780** (also 360×740):
  the head reads unmistakably as a dragon and dominates centrally; all three chests
  + symbols + the logo stay fully visible/un-overlapped; the dark bubble's amber
  text is legible and wraps without clipping; no horizontal scroll on mobile.
- Untouched: `m16-gateway.js`, all JS hooks (`.gw-chest`/`[data-theme]`/`#gw-reveal`
  /`#gw-reveal-ghost`/`#gw-reveal-cake`/`.gw-reveal-veil`/per-chest `.gw-lid`/
  `.gw-inner-glow`/`.gw-symbol`), the 3 chest buttons + `.brand-logo`, and the
  z-90 reveal overlay. No `.theme-*` / `:root` edits; all new styling stays scoped
  to `.gateway` via `--gw-*` tokens.

### Design sign-off (2026-06-13) — all three visual questions RESOLVED
- **Visual Q1 (font, Q-M16-5) → RESOLVED: `Cinzel Decorative`.** User confirmed the
  decorative-serif display face (engraved storybook gravitas, bridges horror+fantasy).
  Family stays `"Cinzel Decorative", "Luminari", "Papyrus", cursive, serif`, weight 900,
  loaded via the M15 non-blocking Google-Fonts pattern. The `Eagle Lake` connected-script
  alternative is NOT taken (kept here as history only).
- **Visual Q2 (narrow-screen order) → RESOLVED: reading order 1→2→3.** On phones the
  chests stack in DOM order moon → twin → sun, middle still largest, tab order ==
  reading order. The "hero middle chest floated to top via CSS `order`" alternative is
  NOT taken.
- **Visual Q3 (gateway audio, Q-M16-6) → RESOLVED: neutral ambient bed (user-supplied).**
  The user will provide the mp3. The gateway loops a theme-neutral ambient and crossfades
  into the destination theme's ambient when a chest opens (reuse the §6 audio-engine
  crossfade; the chest tap is a user gesture so playback is autoplay-legal).
  **Asset location (build contract for G5):** the file goes at
  `static/audio/global/gateway_ambient.mp3` — same `global/` namespace + `*_ambient.mp3`
  convention as `horror_ambient.mp3` / `sea_ambient.mp3`, served at
  `/static/audio/global/gateway_ambient.mp3`. The frontend-engineer wires the gateway to
  play this bed on load (gesture-gated, defensive like the existing engine) and hands off
  to the destination theme's ambient through the reveal. If the file is absent at build
  time, the gateway degrades to silent (no error) — graceful, matching the engine's
  fail-silent posture.
