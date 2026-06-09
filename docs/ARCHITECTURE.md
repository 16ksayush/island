# Architecture — Archive 19: Dual-Atmosphere Dynamic Gallery

Status: **Design locked — Discovery COMPLETE, asset reality confirmed.** FastAPI + Jinja2 SSR, dual-theme, dynamic level count.

## 1. Theme state machine (D1: cookie + sessionStorage)
```
First visit ──► no cookie ──► default = horror (D3)
Toggle (any page) ──► set cookie `theme=horror|sea` + sessionStorage ──► reload/repaint
SSR (every route) ──► read `theme` cookie ──► render correct .theme-* class server-side (no flash)
Client JS ──► reconcile cookie ⇄ sessionStorage, drive audio + transitions
```
The toggle is a small persistent control rendered into every template. Setting the theme is client-side (`document.cookie` + `sessionStorage`); the server only *reads* the cookie.

## 2. Asset split (D9)
- **Images → Google Drive** (dynamic, proxied). One **parent** folder (`GD_ROOT_FOLDER`) with numbered child folders `0..18` + `missing/`.
- **Audio → GitHub repo** (`static/audio/`, version-controlled, served static). Never in Drive.

## 3. Data flow
```
Browser (haunted map / archipelago map — both illustrated, hotspot-based)
   │  GET /level/{id}  (SSR page)        │  GET /api/levels/{id}/photos
   ▼                                      ▼
FastAPI (main.py) ── reads theme cookie ── renders level.html
   │                                      │
   ▼ drive_service.py ──GD_API_KEY (os.environ)──► Google Drive API (under GD_ROOT_FOLDER)
        • list parent's children → discover which numbered folders exist (dynamic scaling)
        • numbered folder {id} present → list its images (audio = LOCAL /static/audio/{theme}/level_{id}.mp3)
        • numbered folder {id} ABSENT  → 1 random image from Drive `missing/` (proxied); audio = a random LOCAL per-theme track (REQUIREMENTS §11)
   ▼
Browser proxies image bytes (and missing-level fallback audio) via /api/levels/{id}/media/{file_id}; never sees the key.
Existing-level audio is loaded directly from /static/audio/... (no Drive, no key).
```

## 4. Endpoints
| Method | Path | Purpose | Response |
|---|---|---|---|
| GET | `/` | Landing page; illustrated map of 19 hotspots per theme (Horror haunted map §8.3 / Sea archipelago map §9), discovery drives sealed styling; theme from cookie. | HTML (`index.html`) |
| GET | `/level/{id}` | Dedicated level page; theme-styled (room/beach). | HTML (`level.html`) |
| GET | `/api/levels` | Configured levels + availability flag (real vs missing-fallback). | `{ "levels": [{ "id": 0, "available": false }, ...] }` |
| GET | `/api/levels/{id}/photos` | Image refs for a level + fallback audio ref when missing (proxied URLs back to our media endpoint). | see §4.1 |
| GET | `/api/levels/{id}/media/{file_id}` | Proxy/stream a single Drive file's bytes (image OR missing-level audio). | image/* or audio/mpeg |
| GET (static) | `/static/audio/global/{theme}_ambient.mp3` | Landing ambient per theme. | audio/mpeg |
| GET (static) | `/static/audio/{theme}/level_{id}.mp3` | Per-level track (per-theme, D11). | audio/mpeg |

### 4.1 Payload schemas (JSON)
`GET /api/levels` →
```json
{ "levels": [ { "id": 0, "available": false }, { "id": 1, "available": true }, ... ] }
```
`GET /api/levels/{id}/photos` — existing level (`available: true`):
```json
{
  "level": 1,
  "available": true,
  "images": [ { "file_id": "<driveId>", "url": "/api/levels/1/media/<driveId>" } ],
  "fallback_audio": null
}
```
`GET /api/levels/{id}/photos` — missing level (`available: false`): exactly one proxied fallback image; `fallback_audio` is `null` (missing-level audio is a random LOCAL per-theme track chosen client-side — REQUIREMENTS §11):
```json
{
  "level": 3,
  "available": false,
  "images": [ { "file_id": "<driveImgId>", "url": "/api/levels/3/media/<driveImgId>" } ],
  "fallback_audio": null
}
```
Notes: each image element is an object (`file_id` + proxied `url`), never a bare Drive URL (key isolation). `fallback_audio` is **always `null`** now (both existing and missing levels) — a missing level's audio is a random LOCAL per-theme track the frontend picks from `audio_track_ids` (REQUIREMENTS §11); the field is retained for payload stability. Error cases: unknown `id` outside the discovered set → `404`; `file_id` not resolvable under the level's folder (or `missing/`) → `404`; upstream Drive failure → `502`.

Route signatures (FastAPI):
```
@app.get("/")                                      def index(request: Request)
@app.get("/level/{level_id}")                      def level_page(request: Request, level_id: int)
@app.get("/api/levels")                            def list_levels()
@app.get("/api/levels/{level_id}/photos")          def level_photos(level_id: int)
@app.get("/api/levels/{level_id}/media/{file_id}") def media_proxy(level_id: int, file_id: str)  # StreamingResponse
```
Theme cookie is read inside `index` / `level_page` via `request.cookies.get("theme", "horror")`.

## 5. Dynamic level + missing handling (drive_service.py)
- Source of truth: the **children of `GD_ROOT_FOLDER`**. List them once → the numeric-named folders define which levels exist (dynamic scaling). The grid renders exactly those; gaps still render a door/island flagged `available: false`.

### 5.1 Level → folder map (in-memory, discovery-derived)
No hand-edited level→folder JSON file is shipped (would duplicate the Drive truth and drift). Instead the map is built once at startup (and cached) by listing the parent's children, e.g.:
```python
# folder_index: dict[int, str]  -> {1: "<folderId>", 2: "<folderId>", 8: "<folderId>", ...}
# missing_folder_id: str        -> id of the "missing/" child
# levels: list[int]             -> sorted span min(0)..max(discovered), with available = id in folder_index
```
`folder_index` maps each present numeric level to its Drive folder ID; the span 0..max defines which tiles render (absent ids → `available: false` → missing fallback). Cache invalidation: process restart, or an optional TTL/manual refresh (see risk list). If a declarative override is ever wanted, it would be an optional `LEVELS_OVERRIDE` env list, not a committed file.
- **Confirmed real structure** (parent folder `all ages`, name changeable): present folders `1, 2, 8–18`; **absent** `0, 3, 4, 5, 6, 7` → these resolve via the missing fallback. Images named `{n}.{i}.jpeg` but fetched by Drive file ID, so naming is irrelevant to the code.

> ## ⚠️ CRITICAL — Drive access method
> A plain `GD_API_KEY` (Google API key) can read **only publicly-shared** Drive files via the Drive API v3 (`files.list` with `'<folderId>' in parents`, then `files.get?alt=media`). Therefore the `all ages` parent folder (and its children) **must be shared "Anyone with the link → Viewer."** If the content must stay private, the API-key approach won't work and we'd need an OAuth2 **service-account JSON** instead (different secret, different client). This choice gates the backend implementation.
- Absent numbered folder → list the Drive `missing/` folder (stock images) and return **1 random image**, proxied through the media endpoint. Fallback **audio** is a random LOCAL per-theme track chosen client-side, not Drive (REQUIREMENTS §11) — so `missing/` only needs images and a missing level never 502s over absent audio.
- `GD_ROOT_FOLDER` is data (config); `GD_API_KEY` is the only secret. The parent folder is shared "Anyone with link → Viewer".

## 6. Audio (GitHub-hosted, per-theme) + crossfade engine
- All audio served as static files from `static/audio/` — no Drive, no API key.
- Landing: loop `global/{theme}_ambient.mp3`.
- Level page (existing level): play `static/audio/{theme}/level_{id}.mp3` (Horror and Sea have distinct tracks).
- Level page (missing level): play a **random LOCAL per-theme track** (`static/audio/{theme}/level_*.mp3`, picked client-side from the `audio_track_ids` list the server passes in) — its own `level_{id}.mp3` does not exist (REQUIREMENTS §11).
- Crossfade: navigating into `/level/{id}` fades the global ambient **out** while fading the level track **in** (no clashing lines); reverse on return.
- Defensive auto-play handling: resume/start on first user gesture; fail silently if blocked.

## 7. Project structure
```
island/
├── app/
│   ├── __init__.py
│   ├── main.py            # routes, theme cookie, dynamic level loop, Jinja2
│   └── drive_service.py   # Drive client under GD_ROOT_FOLDER, child discovery, missing/ image+audio fallback (httpx, os.environ key)
├── static/
│   ├── style.css          # .theme-horror / .theme-sea utility classes
│   └── audio/
│       ├── global/  horror_ambient.mp3, sea_ambient.mp3
│       ├── horror/  level_0.mp3 … level_18.mp3
│       └── sea/     level_0.mp3 … level_18.mp3
│   (missing-level fallback image+audio come from the Drive `missing/` folder, not here)
├── templates/
│   ├── index.html         # landing: swaps Haunted Map ⇄ Archipelago Map (both hotspot-based)
│   └── level.html         # level page: swaps room ⇄ beach by theme
├── tests/                 # pytest + TestClient (Drive mocked): routes, discovery, missing fallback, theme cookie
├── docs/
├── requirements.txt       # fastapi, uvicorn, jinja2, httpx (+ pytest/httpx test deps)
├── .env.example           # GD_API_KEY= , GD_ROOT_FOLDER=
├── .gitignore
└── render.yaml / Procfile
```
Note: `static/` and `templates/` sit at the repo root (per PRD), not under `app/`. Audio (`static/audio/`) is committed to git; only `.env` (the key) is ignored.

---

# 8. Horror Atmosphere Redesign (M9 / HR1–HR8, NF-HR1–NF-HR6)

Status: **Design proposed (H1).** Scope is the **Horror theme visuals only** — a cinematic haunted-corridor scene on the landing page (`index.html`) and a calmer "inside a room" variant inside each level page (`level.html`). **SEA theme, backend, routes, payloads, audio, and all JS data-flow are OUT OF SCOPE and are not touched.** This section is additive to §1–§7 above; the CRITICAL Drive note (§5) and all prior decisions stand unchanged.

## 8.1 Constraints honoured (re-read against the real code)
- The redesign reuses the **existing primitives only**: the `<div class="atmosphere" aria-hidden="true">` already injected in both templates, the `.layer` content wrapper, the `--page-bg-image` / `--vignette` / `--t-transition` tokens, and the existing `prefers-reduced-motion` block at the end of `static/style.css`.
- Every new rule is scoped under a `.theme-horror …` selector. Nothing is added to `:root`, `html, body` base rules, `.theme-sea`, or any shared (`.level-tile`, `.level-stage`, slideshow) selector except where the prefix `.theme-horror` makes it horror-only.
- No template structural change is required. The scene is built **entirely behind existing content** via the already-present `.atmosphere` div plus CSS pseudo-elements. Optional inline-SVG silhouettes, if accepted (HQ2/HQ5), go inside the existing `.atmosphere` div in horror-only Jinja blocks — see §8.3.

## 8.2 Layering model (z-index stack, back to front)
All decorative layers sit **behind** the content and are `pointer-events: none`, so the door grid and toggle stay fully interactive.

```
z-index   layer                         lives in / mechanism
-------   ---------------------------   ----------------------------------------------------
 (paint)  navy field gradient           html,body background  ← via --page-bg-image token (horror palette)
   0      .atmosphere (existing div)     fixed full-viewport overlay, pointer-events:none
            ├─ background: --vignette    moonlit-doorway radial glow + corridor vignette (token)
            ├─ ::before  → fog band A    blurred linear-gradient, low + drifting (animated)
            └─ ::after   → fog band B    second blurred band, offset speed/opacity (animated)
   0.x     .atmosphere > svg (OPTIONAL)  inline decorative silhouettes (doorway frame, cloaked
            (.horror-silhouette)         figure, edge clawed hands); pointer-events:none; aria-hidden
   1       .layer (existing)             header + door grid + footer — UNCHANGED, on top, clickable
   5       .slide-nav (level page)       unchanged
```

Key point: there are **only two real DOM additions possible**, and both are optional/inside the existing div. The moonlight glow, vignette, and fog are produced by the `.atmosphere` element's `background` + its `::before`/`::after` pseudo-elements — **zero new DOM** for the core scene. This guarantees the door grid (`.layer`, z-index 1) always renders above and remains clickable.

## 8.3 CSS-vs-asset approach — recommended default: pure CSS/SVG (HQ1, HQ2)
> **⚠️ Shipped design (2026-06-09) overrides this recommendation for the Horror landing.** The landing adopted the **raster fallback** path (see "Raster fallback" below): a full-bleed illustrated map (`static/img/horror/landing-map.v2.jpg`) replaces the door grid, with %-positioned clickable hotspots (`.horror-map` / `.map-hotspot`) over the art. The per-level page still uses the pure CSS/SVG atmosphere described here. The recommendation below remains accurate for the level page and for the decorative silhouettes/fog on both pages.

**Recommendation: pure CSS + optional inline SVG. No raster image.** Rationale: near-zero bytes (NF-HR1), fully responsive, theme-isolated, instantly themeable, no licensing/attribution, no extra network request, no blocking asset.

### Tokens that change (all inside `.theme-horror` only)
The horror block in `static/style.css` (currently lines 38–61) is the only token surface edited:

- `--bg` / `--bg-2`: shift from charcoal (`#0d0d0d` / `#161210`) toward **deep navy/blue** (e.g. `--bg: #0a0e1a`, `--bg-2: #121a2e`) to read as moonlit night rather than flat black. Amber accent (`#ffb000`) and all `--tile-*`/`--fg`/`--muted` tokens stay as-is so the door tiles and text contrast are preserved.
- `--page-bg-image`: replace the single faint amber radial with a **layered gradient** — a low navy-to-near-black vertical field plus a soft cool moonlight wash high-center. Conceptually:
  ```
  --page-bg-image:
    radial-gradient(ellipse at 50% -5%, rgba(150,170,210,0.10), transparent 55%),  /* moon wash */
    linear-gradient(180deg, #0d1322 0%, #0a0e1a 60%, #05070d 100%);                /* navy field */
  ```
- `--vignette`: tighten into a **central moonlit-doorway glow + heavier corridor edges** — a small warm/cool radial at center (the doorway light at the end of the hall) wrapped by a darker, more enclosed vignette than today:
  ```
  --vignette:
    radial-gradient(ellipse 30% 45% at 50% 42%, rgba(190,205,235,0.16), transparent 60%),  /* doorway glow */
    radial-gradient(ellipse at center, rgba(0,0,0,0) 22%, rgba(2,4,10,0.92) 100%);          /* vignette */
  ```

### New CSS classes / pseudo-elements introduced (horror-scoped)
- `.theme-horror .atmosphere::before` and `.theme-horror .atmosphere::after` — two **low drifting fog bands**: wide blurred (`filter: blur(…)`) linear-gradients of translucent pale grey-blue, anchored near the bottom of the viewport, at different opacities/heights. These animate via transform/opacity only (see §8.5).
- `.horror-silhouette` (OPTIONAL, only if HQ2 = yes) — wrapper class on inline `<svg>` placed inside `.atmosphere`; `position:absolute; pointer-events:none;` with variants:
  - `.horror-silhouette--doorway` (centered moonlit doorway frame, low opacity),
  - `.horror-silhouette--figure` (a single faint cloaked figure, placed off-center so it does **not** sit under a door tile — see risk R-H1),
  - `.horror-silhouette--claws` (clawed-hand silhouettes anchored to the left/right viewport edges, behind the grid gutter).
  All silhouettes are `aria-hidden` and live in a `{% if theme != 'sea' %}` Jinja block inside the existing `.atmosphere` div.

### Raster fallback (only if the user supplies an image, HQ1 alt)
If a designer-supplied background is preferred over CSS, the **single** integration point is the `--page-bg-image` token in `.theme-horror`:
```
--page-bg-image: url(/static/img/horror/corridor.webp);
```
File committed under `static/img/horror/` (new dir). Byte budget: **≤ 150 KB, WebP, ~1920px wide**, `background-size: cover; background-attachment: fixed` (already set on `html,body`). Even then, fog + glow can remain CSS overlays on top. This is the fallback, **not** the recommendation.

## 8.4 Per-level treatment — same mechanism, calmer (HQ3)
The level page already carries the identical `.atmosphere` div and the same `.theme-horror` tokens, so the redesigned background **automatically** applies — replacing today's flat black with the navy/glow/vignette scene. To protect slideshow legibility we add a horror-scoped, page-context override so the level page is **more enclosed and dimmer** than the landing:

- Reuse the SAME mechanism (tokens + `.atmosphere`); do not invent a parallel system.
- A `.theme-horror .level-stage` already has `inset 0 0 120px rgba(0,0,0,0.85)` (line 320–322) which keeps the slide area dark/legible — we keep it. Optionally deepen the stage backdrop slightly so the photos sit in a darker "room."
- Reduce fog presence on the level page (lower opacity / fewer bands) and soften the central glow so it does not wash across the slideshow. This can be done with a body-context selector, e.g. a horror-only rule that targets the level page (the level template's `<main>` is `.level-stage`; the landing has the door grid `<section>`). Practical approach: dial the doorway glow down via a level-only modifier class on `<body>` **OR** rely on `.level-stage`'s own inset shadow + a reduced-opacity `.atmosphere::before/::after`. Recommended: a horror-only attribute/class hook is unnecessary — the existing `.level-stage` overlay already isolates the photos; we simply keep fog subtle so it never crosses into the stage. No new template wiring beyond what already exists.
- **Legibility guard (accessibility):** the slideshow images and the slide dots/nav must keep their current contrast. Fog and glow stay strictly in the fixed background layer (z-index 0); `.level-stage` (z-index via `.layer`) sits opaque on top, so photos are never overlaid by fog. This must be visually verified (see R-H2).

## 8.5 Motion plan — transform/opacity only, reduced-motion gated (HQ4)
- **Fog drift:** the two `.atmosphere::before/::after` bands translate slowly on the X axis (`transform: translateX()`) over a long duration (e.g. 40–70s, linear, infinite, alternate), at different speeds for parallax. Transform-only = GPU-composited, no layout/paint thrash (NF-HR1).
- **Moonlight flicker:** a very subtle, slow `opacity` oscillation on the doorway-glow layer (e.g. 6–10s ease-in-out, amplitude small enough to feel like a candle/distant light, not a strobe — accessibility: no rapid flashing, stays well under 3 flashes/sec).
- **Reduced motion:** the existing block at `static/style.css` lines 467–475 already neutralises `animation-duration`/`iteration-count` globally. To be explicit and safe, the new keyframed layers will ALSO be wrapped so that under `@media (prefers-reduced-motion: reduce)` they render as a **static** frame (fog visible but still, glow at steady opacity). We will not rely solely on the global kill-switch for the new animations; we add an explicit static fallback for the horror fog/glow.

## 8.6 Theme isolation guarantee (HR-isolation)
- Every new rule begins with `.theme-horror`. The `.theme-sea` token block (lines 64–84) and all `.theme-sea …` skins are untouched, so SEA renders **pixel-identical** to today.
- The only token block edited is `.theme-horror` (lines 38–61). `:root` defaults and the shared `html,body` rule are unchanged.
- Optional SVG silhouettes live in `{% if theme != 'sea' %}` blocks inside the already-present `.atmosphere` div; SEA never emits them.
- **No JS change** (theme.js, audio-engine.js, the inline prefetch script, and the slideshow script are all untouched). **No route, payload, schema, audio file, or backend change.** Confirmed against §3/§4 — the redesign is purely `static/style.css` (+ optional inline SVG in templates' existing `.atmosphere` div).

## 8.7 Performance (NF-HR1)
- Pure-CSS path adds **negligible bytes** (a few KB of CSS rules; inline SVG, if used, a few hundred bytes each) and **zero extra network requests** — no `<img>`, no font, no blocking asset.
- All animation is `transform`/`opacity` only → compositor-friendly, no reflow, no main-thread paint storms; will not contend with the landing prefetch worker pool (index.html lines 114–180) or the level slideshow eager-preload (level.html lines 156–222).
- `.atmosphere` is already `position: fixed` (no scroll-linked layout work). The fog `filter: blur()` is applied to two small fixed layers only; if profiling shows blur cost on low-end devices, the blur radius can be reduced or pre-baked into the gradient (no API/contract impact).
- No change to caching, Cache-Control, or media proxy behaviour.

## 8.8 Recommended defaults for open questions (HQ1–HQ5)
- **HQ1 (CSS vs raster):** Pure CSS/SVG. Raster only if a designer asset is mandated; budget ≤150 KB WebP under `static/img/horror/`.
- **HQ2 (silhouettes yes/no):** Include the **moonlit doorway** + **edge clawed-hands** (low opacity, edges only). Make the **cloaked figure** optional and OFF by default pending a visual check (see R-H1) — it is the highest risk of competing with the grid.
- **HQ3 (per-level intensity):** Same mechanism, dialed down — keep `.level-stage` inset shadow, reduce fog/glow so the slideshow stays legible.
- **HQ4 (motion):** Subtle transform/opacity fog drift + slow glow flicker; explicit static fallback under reduced-motion.
- **HQ5 (scope of figure/claws across pages):** Landing only for the cloaked figure; clawed-hand edges may appear on both but should be very faint on the level page to avoid framing the slideshow.

## 8.9 Technical risks / flags for PM (HR redesign)
- **R-H1 (visual competition):** A cloaked-figure silhouette risks sitting under/behind a door tile and looking like a glitch, or drawing the eye away from clickable doors. Recommend OFF by default; if enabled, anchor it in a gutter region and keep opacity very low. Needs a design eyeball.
- **R-H2 (contrast / accessibility):** Fog + lowered navy luminance could reduce contrast of the `--muted` label text ("Door"/"Sealed") and the slide dots. **Action: run a WCAG AA contrast check** on `--fg`/`--muted`/`--accent` against the new navy `--bg` before freeze; bump `--muted` lightness if it fails.
- **R-H3 (flicker safety):** Moonlight flicker must stay subtle and slow (no rapid luminance flashing) to avoid photosensitivity issues; cap amplitude/frequency, and it must fully freeze under reduced-motion.
- **R-H4 (blur perf on low-end):** `filter: blur()` on fog layers can be costly on weak GPUs/mobile. Mitigation noted in §8.7 (reduce radius or bake into gradient). Low severity, but flag for QA on mobile.
- **R-H5 (level-page glow wash):** If the central glow is too strong on the level page it can wash over the slideshow edges. Mitigation: reduced glow + the existing `.level-stage` inset shadow keep photos in a dark frame; verify visually.
- **R-H6 (ambiguity — "horror background instead of flat black"):** Confirm whether the per-level page wants the *full* corridor scene (fog + glow) or just the navy field + vignette (no fog). Recommend the calmer navy+vignette with minimal fog; PM to confirm desired intensity.

---

# 9. Sea (Light) Landing Map (M10 / SR1–SR9, NF-SR1–NF-SR6)

Status: **BUILT + SECURITY-APPROVED + QA-VERIFIED (full suite 140 passed / 0 failed), pending commit (2026-06-09).** Design locked, USER SIGNED OFF (art used as-is for the Sea/light theme, island names exposed in `aria-label`, no mobile grid fallback). The design body below is the **as-built reference** and matches the shipped code. Scope was the **Sea & Island (light) theme landing only** — the dynamic island grid (`index.html`, the `{% else %}` branch) was replaced with a full-bleed illustrated archipelago map (`static/img/light/landing-map.v2.webp`, 214 KB, 1399×768) whose 19 painted island locations are %-positioned clickable hotspots → `/level/{id}`, mirroring the shipped M9 Horror map (§8.3 "Raster fallback" / `.horror-map` machinery). The one-line calibrate-JS selector is now `.horror-map, .sea-map`. **HORROR theme, backend, routes, payload schemas, audio engine, prefetch, Drive/missing logic, and deploy config are OUT OF SCOPE and are not touched.** This section is additive to §1–§8; the CRITICAL Drive note (§5), all decisions D1–D12, and the shipped M9 design stand unchanged. Default theme stays **Horror** (D3).

## 9.1 Constraints honoured (re-read against the real code)
Verified against `templates/index.html` (lines 50–172), `static/style.css` (`.horror-map`/`.map-hotspot`/`.calibrate` rules at 241–412 + the mobile block 528–625 + `.theme-sea` tokens 84–104), and the supplied art.
- **The hotspot machinery is already partly theme-neutral.** In the shipped Horror markup the anchor class is **`.map-hotspot`** (not `.horror-map-hotspot`), with children `.map-hotspot-ring` / `.map-hotspot-id` and the modifier `.is-sealed`. But **every CSS rule for them is prefixed `.theme-horror`** (style.css 353–412), so the classes are *named* generically yet *styled* horror-only. This is the seam we exploit: the **markup contract is already shared**; only the **CSS scoping** needs a parallel `.theme-sea` skin.
- **The container/image classes are horror-specific:** `.horror-landing`, `.horror-map`, `.horror-map-img`, `.horror-map-hotspots`, `.horror-map-toggle`, `.horror-ambient`, `.horror-ghost`. The `?calibrate` aid toggles `.calibrate` on **`.horror-map` only** (index.html line 271) — so it does NOT currently reach a Sea map.
- **NF-SR4 hard gate:** the Horror branch markup, its `coords` dict, `static/img/horror/landing-map.v2.jpg`, and all `.theme-horror …` CSS must remain byte-identical. Any refactor must preserve Horror's emitted HTML and computed styles exactly.

## 9.2 Class/markup strategy — RESOLVES SQ1 (the pivotal decision)
**Recommendation: a third, low-risk path between "full shared component" and "full duplicate" — keep Horror's emitted markup byte-identical, reuse the already-shared `.map-hotspot*` contract for BOTH themes, and add a thin parallel Sea container skin. Do NOT rename or restructure the Horror branch, and do NOT introduce a shared Jinja partial in this milestone.**

Rationale (weighing DRY vs NF-SR4):
- A full shared `_map_landing.html` macro is the cleanest DRY outcome, but to satisfy NF-SR4 it must emit **byte-identical** Horror HTML (same class names, same attribute order, same whitespace, same decorative SVG block). Proving byte-equality of a refactored macro against the current hand-written Horror branch is a large, fragile QA surface for a frontend-only change whose explicit top constraint is "Horror untouched." The risk (R-S1) outweighs the savings for one extra theme.
- The hotspot leaf contract (`.map-hotspot` + `.map-hotspot-ring` + `.map-hotspot-id` + `.is-sealed`) is **already generic and already shared-by-name**. We reuse it verbatim in the Sea branch — that is the meaningful DRY win, and it needs **zero change to Horror**.
- Only the *container* wrappers differ per theme. We add Sea-named container classes (`.sea-map`, `.sea-map-img`, `.sea-map-hotspots`, `.sea-landing`) styled under `.theme-sea …`, parallel to the `.horror-*` set. No `.horror-*` rule is touched; no `:root` neutral is edited.

### Recommended Sea-branch markup skeleton (replaces lines 116–171, the `{% else %}` body)
```html
{% else %}
<!-- ===== SEA LANDING: full-bleed illustrated archipelago map ===== -->
{% set available_ids = levels | selectattr('available') | map(attribute='id') | list %}
{#- (x%, y%) = center of each painted island number, measured from THIS art (§9.3) -#}
{% set sea_coords = { 0:[13.0,21.0], 1:[22.0,28.0], ... } %}
{% set sea_names  = { 0:'Ruin', 1:'Gate', ... } %}            {# §9.3, SQ3 #}
<div class="layer sea-landing">
  <h1 class="sr-only">Tour-de-Anshika — choose an island</h1>

  {# Optional ambient decoration (drifting boats/gulls/clouds) — SQ4, §9.6.
     Off by default; if enabled it lives here, aria-hidden + pointer-events:none. #}

  <!-- Global theme toggle, overlaid clear of the painted pill (§9.4, SR6). -->
  <button id="theme-toggle" type="button" class="theme-toggle sea-map-toggle"
          aria-label="Toggle between Horror and Sea themes">
    <span class="toggle-icon" aria-hidden="true">🌙</span>
    <span>Enter the Corridor</span>
  </button>

  <div class="sea-map" aria-label="Map of Tour-de-Anshika — choose an island">
    <img class="sea-map-img"
         src="/static/img/light/landing-map.v2.webp"   {# §9.4 optimized asset #}
         alt="An illustrated archipelago map of Tour-de-Anshika with numbered islands"
         fetchpriority="high" decoding="async" />
    <div class="sea-map-hotspots">
      {% for id, xy in sea_coords.items() %}
      <a class="map-hotspot{% if id not in available_ids %} is-sealed{% endif %}"
         href="/level/{{ id }}"
         style="left: {{ xy[0] }}%; top: {{ xy[1] }}%;"
         aria-label="Level {{ id }} — {{ sea_names[id] }}{% if id not in available_ids %} (sunken — fallback content){% endif %}">
        <span class="map-hotspot-ring" aria-hidden="true"></span>
        <span class="map-hotspot-id" aria-hidden="true">{{ id }}</span>
      </a>
      {% endfor %}
    </div>
  </div>
</div>
{% endif %}
```
Note the `{% if theme != 'sea' %}…{% else %}…{% endif %}` top-level branch is **unchanged in shape** — only the body of the `{% else %}` (Sea) arm is replaced. The Horror arm (lines 50–114) and the shared `.atmosphere` block (lines 14–48, whose decorative SVGs are already gated `{% if theme != 'sea' %}` so Sea emits an empty `.atmosphere`) are left exactly as-is.

### Calibrate JS — must now select BOTH maps
The aid at index.html lines 262–273 currently does `document.querySelector(".horror-map")`. Change it to a selector that matches either container so SR4's "calibrate against THIS art" works for Sea:
```js
var map = document.querySelector(".horror-map, .sea-map");
if (map) map.classList.add("calibrate");
```
and the calibrate CSS gains a Sea-scoped twin of the Horror rules (style.css 405–412): `.theme-sea .sea-map.calibrate .map-hotspot { … }` / `.theme-sea .sea-map.calibrate .map-hotspot-id { display:flex; }`. This is a one-line JS change with no behavioral effect outside `?calibrate` (R-S4 mitigation). **Optional cleaner alternative:** put a shared marker class `js-calibratable` on both `.horror-map` and `.sea-map` and select that — avoids the JS ever needing to learn new container names again. Recommended: the two-selector form (smallest diff).

## 9.3 Sea coords + names source-of-truth (SR3/SR4, SQ3)
**Coords live in the Sea branch as a Jinja `sea_coords` dict**, exactly mirroring Horror's inline `coords` (index.html 60–65) — a per-theme literal, not a shared file, so the two layouts never cross-contaminate (R-S4). Implementation fine-tunes via `?calibrate`. **First-pass estimates measured from `static/img/light/landing-map.png`** (origin top-left, % of the art box, = center of each painted island number):

```python
sea_coords = {
  0:[13.0,21.0], 1:[22.0,28.0], 2:[33.0,22.0], 3:[46.0,25.0], 4:[62.0,25.0],
  5:[10.0,51.0], 6:[21.0,50.0], 7:[37.0,50.0], 8:[22.0,67.0], 9:[62.0,48.0],
  10:[13.0,80.0], 11:[27.0,80.0], 12:[70.0,92.0], 13:[50.0,78.0], 14:[64.0,79.0],
  15:[40.0,90.0], 16:[37.0,79.0], 17:[50.0,92.0], 18:[84.0,75.0]
}
```
These are deliberately distinct from Horror's `coords` (the archipelago layout is unrelated to the haunted-map layout). They are a starting point; S3/S7 will nudge them under `?calibrate`.

**Names (SQ3) — RESOLVED with a recommended default: expose names in `aria-label` only; visible UI stays numbers-only.** A `sea_names` dict is the single source of truth:
```python
sea_names = {
  0:'Ruin', 1:'Gate', 2:"Witch's Hut", 3:'Mausoleum', 4:'Echoed Abyss',
  5:'Prison', 6:'Graveyard', 7:'Hallo', 8:'Sunken Temple', 9:'Forbidden',
  10:'Cavern', 11:'Sepulcher', 12:'Watch Tower', 13:'Pit', 14:'Final Keep',
  15:'Haunted Tower', 16:'Cursed Orchard', 17:"Dragon's Dew", 18:'Forgotten Memory'
}
```
- Feeds `aria-label="Level {id} — {name}"` (e.g. `"Level 5 — Prison"`), giving screen-reader users the same place-name a sighted user reads off the painted art (SR7, NF-SR2). The painted numbers on the art remain the only *visible* labels (the `.map-hotspot-id` stays hidden except under `?calibrate`, identical to Horror), so we never double-print a name on top of the illustration.
- This is purely additive to the Horror pattern (Horror's `aria-label` is `"Level {id}"`); Horror is not given names (out of scope, byte-unchanged).
- **Caveat → SQ6:** the names are macabre (Graveyard, Mausoleum, Dragon's Dew). They are surfaced verbatim from the art. If the user does not want eerie place-names announced under the sunlit Sea theme, the fallback is numbers-only `aria-label`s (drop `sea_names`). Flagged to the user (§9.8, SQ6).

## 9.4 Image optimization spec — RESOLVES SQ2 / R-S2 (NF-SR1)
The source `static/img/light/landing-map.png` is **2.7 MB** and **must not ship as-is**. The art is a dense painterly illustration (photographic-class gradients), so PNG cannot hit budget — drop PNG.
- **Format:** ship **WebP (lossy, quality ≈ 80)**, mirroring the Horror precedent (640 KB JPG). Provide a `<picture>` only if a JPEG fallback is judged necessary for ancient browsers; WebP is universally supported in all current evergreen targets, and the Horror map already ships a single `<img>` (no `<picture>`), so for consistency and simplicity **a single `<img src=".webp">` is the recommendation**. (If S2 finds a stubborn delta, a progressive JPEG at the same budget is the acceptable alternative — pick ONE, do not ship both unconditionally.)
- **Byte budget:** target **≤ 400 KB** (within NF-SR1's 300–600 KB band; aligns with Horror's 640 KB while being a touch leaner for a slightly wider image). Hard ceiling 600 KB; S6/S7 verify the committed file size.
- **Dimensions:** downscale to **~1600 px wide** (the desktop fit caps at `100vw`/`100vh`; >1600 px buys nothing on this layout). Preserve the native aspect ratio — the supplied art is wide landscape (~16:9, materially wider than the Horror map's ~1.25:1, which matters for §9.5 responsive math). Record the exact final WxH in S2 so the responsive rules use the true ratio.
- **Filename convention:** `static/img/light/landing-map.v2.webp` (the `.v2` mirrors the Horror asset name `landing-map.v2.jpg` and lets the original `.png` be removed or retained as the design source without shipping it to the browser). The `<img src>` and the `.sea-map::before` blurred-fill `url(...)` (if §9.5 reuses that pattern) both point at the `.webp`.
- **Loading:** `fetchpriority="high"` + `decoding="async"` on the `<img>` (mirrors Horror, NF-SR1). The idle prefetch worker (index.html 186–261) is **unchanged** — it only warms `/api/levels/.../media/...` image URLs and never touches the landing art, so the map load and prefetch don't contend. The map `<img>` is not render-blocking and does not gate the landing ambient audio (audio start is the inline script at 177–185, independent of image decode).

## 9.5 Responsive plan — RESOLVES SQ5 (NF-SR3, R-S5)
**Core invariant (mirrors Horror):** the hotspot layer (`.sea-map-hotspots`, `position:absolute; inset:0`) is a child of the SAME box as the `<img>` (`.sea-map`, `position:relative; line-height:0`). Because both share one box and hotspots are positioned in `%`, the `[x%,y%]` coordinates hold at **every** rendered size and aspect ratio **as long as the image is shown un-cropped (`object-fit` equivalent of `contain`, i.e. natural `width:auto/height:auto` fit, never `cover`)**. Cropping (`cover`) would break alignment — so we mirror Horror's "fit the WHOLE map, letterbox the remainder" model, not a cropping hero.

- **Desktop / tablet (default, > 768px):** reuse Horror's desktop approach exactly — `.sea-map-img { width:auto; height:auto; max-width:100vw; max-height:100vh; display:block }` inside a flex-centered `.sea-landing`. The whole map is visible, centered, no crop, no scroll. Letterbox margins are filled by a blurred/brightened copy of the art via `.sea-map-landing::before` (Sea analog of style.css 261–271) — for the Sea palette use a light wash (sky-blue/sand) instead of the storm-red/purple Horror wash, so margins read as open sea/sky, not a void.
- **Mobile (≤ 768px and ≤ 480px):** **adopt Horror's pan-to-fit model, NOT a grid fallback.** Because the Sea art is *wider* (~16:9) than the Horror map (~1.25:1), fitting-to-viewport on a portrait phone makes it even tinier and the 6% hotspots collapse well below the ~44px touch floor. So mirror style.css 549–625: pin `.sea-landing` to the viewport (`position:fixed; inset:0; overflow:auto; overscroll-behavior:contain; touch-action:pan-x pan-y`), render `.sea-map-img` **larger than the viewport** (`width:130vw` ≤768px, `width:175vw` ≤480px), keep the blurred fill + toggle `position:fixed`, and widen `.map-hotspot` to `7%` at ≤480px for tap-target insurance. The wider aspect ratio means the vertical pan range is larger than Horror's — acceptable, and the start corner (`align-items/justify-content:flex-start`) puts island 0 (top-left) in view first.
- **Small-screen grid fallback (SQ5 sub-question) — RECOMMEND NO.** Retaining the old island grid under a breakpoint would (a) contradict SR1's "replaces the grid" (forcing the R-S6 softening), (b) require keeping the now-dead grid markup + its `.theme-sea .level-tile` CSS alive, and (c) diverge the two themes' mental models (Horror has no grid fallback). The pan-to-fit model is already proven on Horror mobile and keeps both themes consistent (NF-SR6). **Default: drop the grid; pan-to-fit on mobile. SR1 "replaces" stays literally true, R-S6 is closed.** (If the user insists on a mobile grid, that's the only thing that reopens R-S6 and keeps the grid markup — flagged as the SQ5 user decision in §9.8.)

## 9.6 Decorative ambient layer — SQ4 (SR9, "Could")
**Recommendation: defer / off by default; design the hook so it's a trivial add-on, not a blocker.** The Horror landing has `.horror-ambient` > 6 `.horror-ghost` inline SVGs drifting in the side margins (index.html 71–79, CSS 286–317), reduced-motion-frozen (CSS 520–525). The Sea analog would be a `.sea-ambient` block (aria-hidden) holding a few inline-SVG **drifting sailboats / gulls / clouds** positioned in the letterbox margins, animated transform/opacity only, gated by the existing global `prefers-reduced-motion` block plus an explicit static-frame fallback (mirroring CSS 520–525). Keep it parallel to `.horror-scene`/`.horror-ambient`: same z-layer (`z-index:0`, behind `.sea-map` at z-1), same `pointer-events:none`. Because the default is "clean" (SR9 is "Could"), S5 can ship without it and add it later with zero contract change. **Default: off; hook documented.**

## 9.7 Theme-isolation proof (NF-SR4 — hard gate)
**What changes (the entire diff surface):**
1. **`templates/index.html`** — only the body of the `{% else %}` (Sea) arm (lines 116–171) is replaced with the §9.2 map skeleton; the `sea_coords`/`sea_names` dicts are added inside that arm. Plus the one-line calibrate-JS selector change (`.horror-map` → `.horror-map, .sea-map`).
2. **`static/style.css`** — a NEW block of `.theme-sea .sea-map* { … }` rules (parallel to the M9b Horror block), plus a Sea-scoped calibrate twin and Sea mobile breakpoints. All rules are prefixed `.theme-sea`.
3. **`static/img/light/landing-map.v2.webp`** — the new optimized asset (the raw `.png` is not shipped to the browser).

**Why Horror is provably unaffected:**
- No `.horror-*` selector, no Horror-branch markup, no `coords` dict, and `static/img/horror/landing-map.v2.jpg` are edited. The Horror arm of the `{% if theme != 'sea' %}` branch emits byte-identical HTML.
- The shared `.map-hotspot*` *classes* are reused by name, but their **styling is selector-scoped** (`.theme-horror .map-hotspot` vs new `.theme-sea .map-hotspot`), so the Sea rules can never apply to a Horror page and vice-versa. No bare `.map-hotspot { … }` rule is added.
- No `:root` neutral, no shared `html,body`, no `.atmosphere`, no `.layer`, no `.theme-toggle` base rule is edited (the toggle base at 628–659 already serves both themes; we only add a Sea-scoped *position* override `.sea-map-toggle`, analogous to `.horror-map-toggle`).
- The calibrate-JS change is additive (`querySelector` matches an extra selector); on a Horror page `.sea-map` doesn't exist, so behavior is identical.

**Why the Sea LEVEL page is unaffected:** M10 touches only the Sea *landing* (`index.html` `{% else %}`). `level.html`, `.theme-sea .level-stage` (style.css 860+), the room/beach presentation, slideshow, and per-level audio are untouched.

**Confirmed zero backend/route/payload/JS-engine change:** No edit to `app/main.py`, `app/drive_service.py`, routes (§4), payload schemas (§4.1), the audio engine, the prefetch worker, or `/api/levels*`. The map is a static asset + SSR template branch only (matches NF-SR5).

## 9.8 Recommended defaults for open questions (SQ1–SQ6)
- **SQ1 (class strategy):** **RESOLVED — reuse the already-shared `.map-hotspot*` leaf contract for both themes; add Sea-scoped container classes (`.sea-map*`); do NOT rename Horror, do NOT introduce a shared macro this milestone.** DRY where it's free (hotspots), isolated where it's risky (containers/palette). Architect call; no user input needed unless they want full DRY (reopens R-S1).
- **SQ2 (format/budget):** **RESOLVED — single WebP `landing-map.v2.webp`, q≈80, ~1600px wide, ≤400 KB (hard ceiling 600 KB).** Progressive JPEG is the only-if-needed alternative. No user input needed.
- **SQ3 (labels):** **RESOLVED (default) — names in `aria-label` only (`"Level 5 — Prison"`), visible UI numbers-only.** Coupled to SQ6: if eerie names shouldn't be announced under Sea, fall back to numbers-only labels.
- **SQ4 (ambient decoration):** **RESOLVED (default) — off; `.sea-ambient` hook documented for a later trivial add.** No user input needed.
- **SQ5 (responsive):** **RESOLVED (recommended) — scale-to-fit + letterbox on desktop, pan-to-fit on mobile (mirror Horror); NO grid fallback (keeps SR1 literal, closes R-S6).** The single residual user choice is whether they *insist* on a mobile island-grid fallback (the only thing that reopens R-S6 / retains the grid markup).
- **SQ6 (art/theme naming mismatch):** **NEEDS USER CONFIRMATION (content/brand).** The "light/Sea" art carries macabre place-names (Graveyard, Mausoleum, Haunted Tower, Dragon's Dew) and a *painted* toggle pill. Confirm: (a) this art is intended for the Sea (light) theme as-is; (b) the Sea theme keeps its sunlit azure palette/copy ("Enter the Corridor" / 🌙) despite the names; (c) whether the eerie names should be exposed in `aria-label` (SQ3) or suppressed.

## 9.9 Technical risks / flags for PM (M10) — R-S1…R-S6 confirmed + expanded
- **R-S1 (Horror regression from shared refactor):** **MITIGATED by the §9.2 decision** — no `.horror-*` rule or Horror markup is touched, and no shared macro is introduced, so the refactor surface that could regress Horror is eliminated. Residual: the one-line calibrate-JS selector change → QA confirms Horror `?calibrate` still highlights `.horror-map` (S7). Severity downgraded to low.
- **R-S2 (byte budget blown):** Mandatory §9.4 optimization (≤400 KB WebP); the raw 2.7 MB PNG is never shipped. S6 (security) + S7 (QA) verify the committed asset size. Open.
- **R-S3 (toggle clash with painted pill):** The art paints a decorative toggle pill **top-right**. **Mitigation: place the real `.sea-map-toggle` top-right too (`position:absolute; top:1rem; right:1rem; z-index:6`, mirroring `.horror-map-toggle`) so the live control sits directly OVER the painted pill region**, reading as "the pill is the button." Copy/icon: 🌙 "Enter the Corridor" (the existing Sea toggle text). Verify at S5/S7 that the live toggle visually lands on/near the painted pill and doesn't look duplicated; if the painted pill peeks out awkwardly, nudge the overlay to fully cover it or shift it down-left. Low-med severity, visual eyeball needed.
- **R-S4 (coord drift):** Closed by the distinct `sea_coords` dict (§9.3) measured against THIS art + the calibrate aid now reaching `.sea-map` (§9.2). S3/S7 fine-tune.
- **R-S5 (mobile usability):** Addressed by the pan-to-fit model (§9.5) proven on Horror; the wider Sea aspect ratio means a longer vertical pan — QA mobile pass at S7 confirms all 19 islands are reachable and hotspots clear ~44px.
- **R-S6 (grid-removal vs fallback conflict):** **Closed under the recommended default (§9.5: no grid fallback)** — SR1's "replaces the grid" stays literally true and the grid markup is deleted. **Reopens only if the user picks a mobile grid fallback at SQ5**, in which case SR1 must be softened to "replaces above breakpoint" and S3's grid markup is retained.
- **R-S7 (NEW — painted pill is baked into the optimized image):** Because the toggle pill is part of the art, it ships in the WebP regardless. If branding later changes the toggle, the painted pill can't be edited without re-exporting the art. Low severity; note for maintainability (NF-SR6). Document the art source so a re-export is possible.
- **R-S8 (NEW — landscape pan range on mobile may bury low-id islands):** The ~16:9 art panned at 130–175vw puts the bottom-row islands (12, 17, 15) far down the scroll. The start corner shows 0–4; ensure no island is unreachable and consider a subtle "pan to explore" affordance. Low severity; QA at S7.

**Resolved-with-default (no user input required to proceed):** SQ1, SQ2, SQ3 (pending SQ6), SQ4, SQ5 (the scale/pan model). **Needs an explicit USER decision:** SQ6 (art-for-Sea confirmation + eerie-names-in-aria + palette stays azure) and the SQ5 sub-question (do they *insist* on a mobile grid fallback — default is no). Everything else is an architect call locked by a "go."

---

# 10. Hosting / Deployment fit (M8 / HostR1–HostR11, HostC1–HostC4, HostQ1–HostQ5)

Status: **Host CHOSEN — Render (D13, user-decided 2026-06-09); HostQ1 RESOLVED.** The architect recommendation (Render primary; Fly.io / HF Spaces fallbacks) was accepted as-is — no new code or config required (the committed `render.yaml` Blueprint stands). Remaining open Qs = cold-start tolerance (HostQ2), domain (HostQ3), Drive-sharing confirm (HostQ4), traffic/region (HostQ5), and `/api/refresh` auth (R-D6, §10.5); these shape the deploy but do not block starting it. This section scores the five candidate hosts (REQUIREMENTS §12.3 / HostC3) against the architectural ground truth and the HostR# requirements, then recommends a **primary + fallback**. It is additive to §1–§9 and changes no decision D1–D12, no route (§4), no payload (§4.1), and no backend behavior. The diff for M8 is **doc + (only if a non-Render host is chosen) one new config artifact + README deploy instructions** (REQUIREMENTS §12.5).

## 10.1 Architectural ground truth restated (what the host MUST satisfy)
This app is a **persistent Python ASGI server with state in the running process** — not a static site, and not (without rework) a stateless serverless function. The host-disqualifying properties are:
- **Persistent process + `lifespan` startup discovery + in-memory cache.** On boot the FastAPI `lifespan` lists the Drive parent's children to build the level→folder map (§5.1) and holds it plus a bounded LRU of image bytes **in process memory**. `POST /api/refresh` rebuilds that in-process state. A host that recycles the process per request (serverless) re-discovers on every cold instance and a refresh on instance A is invisible to instance B (HostC2).
- **Server-side secret `GD_API_KEY`** read via `os.environ`, **never** sent to the browser (F10 / HostR3, SECURITY_ENGINEER veto). The host must inject env secrets and keep them server-side. A pure static host (GitHub Pages) cannot hold a secret at all (HostC1).
- **SSR Jinja2** every request (theme cookie read server-side, §1) — no static prebuild.
- **Drive byte-proxy streaming** (`StreamingResponse`, §4) — sensitive to per-invocation execution-time and egress-bandwidth caps on serverless tiers.
- **Static `/static/audio/`** served reliably (all audio in-repo, D9 / HostR11).
- **Health check `/api/levels`** (HostR6) + graceful degradation when env unset.

## 10.2 Host-fit decision matrix (HostR1–HostR11)
Legend: ✅ satisfies · ⚠️ satisfies with caveat · ❌ fails. "Cache survives" = does the in-memory LRU + discovery map persist across requests within a warm instance (it **never** survives a cold start on any free tier — see R-D5).

| Property / Requirement | **Render** (web service) | **Fly.io** (machine) | **HF Spaces** (Docker) | **Vercel** (serverless) | **GitHub Pages** (static) |
|---|---|---|---|---|---|
| Free tier (HostR7) | ✅ free web service | ✅ small-machine free allowance | ✅ free | ✅ free (hobby) | ✅ free |
| Persistent ASGI process + `lifespan` (HostR1) | ✅ long-lived Uvicorn | ✅ long-lived VM | ✅ long-lived container | ❌ ephemeral per-invocation | ❌ no server at all |
| Holds server-side secret (HostR2/HostR3) | ✅ `sync:false` env | ✅ `fly secrets` | ✅ Space "Secrets" | ⚠️ env exists, but secret reused per cold fn | ❌ cannot hold a secret |
| In-memory cache survives across requests (R2) | ⚠️ within warm instance; lost on spin-down | ✅ within warm machine; lost only on stop | ⚠️ within warm Space; lost on sleep | ❌ not across cold invocations | ❌ n/a |
| Secret injection mechanism (HostR2) | dashboard env (`sync:false`) | `fly secrets set` | Space Settings → Secrets | project env vars | none |
| Auto-deploy from GitHub `main` (HostR5) | ✅ `autoDeploy:true` (committed) | ⚠️ via GH Action / `fly deploy` (not native push) | ⚠️ Git push to Space remote, or GH sync | ✅ native Git integration | ✅ native (but static only) |
| Public HTTPS URL (HostR4) | ✅ `*.onrender.com` | ✅ `*.fly.dev` | ✅ `*.hf.space` | ✅ `*.vercel.app` | ✅ `*.github.io` |
| Custom domain (HostQ3) | ✅ free | ✅ free | ⚠️ limited | ✅ free | ✅ free |
| Serves `static/audio/` (HostR11) | ✅ | ✅ | ✅ | ⚠️ static OK, but app is split fn+static | ✅ (static only) |
| Python 3.13 + `requirements.txt` (HostR8) | ✅ `PYTHON_VERSION=3.13.0` | ✅ via Dockerfile base | ✅ via Dockerfile base | ⚠️ runtime pin + handler wrapper | ❌ no Python |
| Health check `/api/levels` (HostR6) | ✅ `healthCheckPath` (committed) | ⚠️ `[checks]` in `fly.toml` | ⚠️ container healthcheck | ❌ no long-lived process to check | ❌ n/a |
| Streamed Drive bytes vs free limits (HostR9/§12.5) | ⚠️ bandwidth fair-use; proxy egress counts | ⚠️ egress allowance | ⚠️ fair-use | ❌ per-fn exec-time + bandwidth caps hurt streaming | ❌ n/a |
| Cold-start behavior (HostR9/HostQ2) | ⚠️ spins down ~15 min idle → ~30–60s cold start (+ re-discovery) | ⚠️ scale-to-zero optional; can stay warm within allowance | ⚠️ sleeps on inactivity → wake delay | ❌ frequent cold starts, re-discovery each time | ✅ none (but no app) |
| Effort given what's committed | ✅ **lowest** — `render.yaml` + `Procfile` already in repo; apply Blueprint, set 2 env vars | ⚠️ author a `Dockerfile` + `fly.toml`, run `fly launch` | ⚠️ author a `Dockerfile` (port **7860**), make a (public) Space, set Secrets | ❌ **highest** — rework cache/discovery + `vercel.json` + handler | n/a — re-architect away from secure proxy |
| **Verdict** | ✅ **PRIMARY** | ✅ **FALLBACK A** | ⚠️ **FALLBACK B** | ❌ poor fit as-is | ❌ not viable |

### 10.2.1 Why Vercel is a poor fit as-is (HostC2 expanded)
FastAPI *can* run as a Vercel Python serverless function, but the architecture breaks on four points:
1. **Lifespan discovery doesn't fit the model.** Serverless functions don't run a persistent `lifespan`; discovery would have to move to **per-request** (slow, re-lists Drive on cold start) or to a **build-time manifest** (defeats dynamic scaling / D5) or to an **external cache** (e.g. Upstash Redis / Vercel KV).
2. **In-memory cache + `POST /api/refresh` don't persist.** Each cold instance has its own memory; a refresh on one instance is invisible to others and is wiped on recycle (R2). Surviving state requires an external store — a new dependency the project doesn't have.
3. **Streaming Drive bytes hits caps.** Per-invocation execution-time and egress-bandwidth limits on the hobby tier are hostile to proxying/streaming image bytes through the function (the LRU that mitigates this can't be relied on — see point 2).
4. **Cold starts** add latency on top of (1).

**Rework it would need:** move discovery to per-request or a scheduled manifest build; back the cache + refresh with an external KV/Redis (Upstash); accept ephemeral per-instance memory; possibly offload media proxying to signed redirects (which risks the F10 key-isolation gate if done naively). **Tradeoff:** this is a meaningful re-architecture of §5/§5.1 and the cache/refresh model for **no benefit** over a free persistent host — so Vercel is rejected for M8 unless HostQ1 flips to "re-architect."

### 10.2.2 Why GitHub Pages is not viable (HostC1)
Static-only: no Python process (fails HostR1), cannot hold `GD_API_KEY` (fails HostR2/HostR3), cannot proxy Drive bytes (fails F8/F10). Making it work means a fully client-side app that either **exposes the API key in the browser** (hard F10/HostR3 violation, SECURITY veto) or drops the secure proxy entirely. **Rejected.**

## 10.3 Recommendation — Primary: Render · Fallback A: Fly.io · Fallback B: HF Spaces
**Primary: Render free web service.** It is the only candidate already fully Blueprinted in the repo (`render.yaml` with `autoDeploy:true`, `healthCheckPath:/api/levels`, `PYTHON_VERSION=3.13.0`, `GD_API_KEY`/`GD_ROOT_FOLDER` as `sync:false`), satisfies HostR1–HostR8 + HostR10/HostR11 with **zero new code or config**, and its only material weakness (cold-start spin-down, HostR9) is acceptable for a free portfolio/demo app (HostQ2 lean). Effort to deploy: apply the Blueprint, set two env vars, push to `main`.

**Fallback A: Fly.io** — if Render's ~15-min spin-down / ~30–60s cold start is judged too rough, Fly's free small-machine allowance can keep a machine warmer and gives a persistent VM. Cost: one new artifact (`Dockerfile` + `fly.toml`) and a non-native deploy path (GH Action or `fly deploy`).

**Fallback B: Hugging Face Spaces** — free Docker FastAPI, secrets via Space Settings. Caveats: the container must listen on **port 7860**, the **Space is public** (acceptable — D8 says the app is public/no-auth, but note source visibility), and it **sleeps on inactivity** (same cold-start class as Render).

**Position on the blocking open questions:**
- **HostQ1 (architecture commitment):** **KEEP the FastAPI Drive-proxy + in-memory-cache architecture → persistent web service.** Do not re-architect to static/serverless. Re-architecting touches the backend, the F10/HostR3 secret-isolation model, and the §5.1 cache/refresh design for no free-tier benefit; GitHub Pages is out (HostC1) and Vercel needs external-store rework (§10.2.1). This is the architect lean and aligns with REQUIREMENTS §12.4 HostQ1.
- **HostQ2 (cold start acceptable):** **ACCEPT free-tier spin-down** for this demo. First visit after idle waits ~30–60s (process boot **plus** Drive re-discovery — R-D5); steady-state is warm and fast. Optional mitigation in §10.4 if the user wants to reduce it.

## 10.4 Concrete deploy shape for the recommended host (Render)
**Already in place (no change):** `render.yaml` (Blueprint: `type:web`, `plan:free`, `branch:main`, `buildCommand: pip install -r requirements.txt`, `startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT`, `autoDeploy:true`, `healthCheckPath:/api/levels`) and `Procfile` (kept as a portability artifact for Fly/Railway/Heroku-style hosts).

**Env vars to set in the Render dashboard (Environment tab — never in git):**
- `GD_API_KEY` — **secret** (`sync:false` → Render prompts for it; never read from the committed file).
- `GD_ROOT_FOLDER` — the parent Drive folder ID/link (config, `sync:false` here so it stays a dashboard fill-in; the app degrades to an empty gallery until set).
- `PYTHON_VERSION=3.13.0` — already in `render.yaml`.

**Start command / health check:** as committed above; Render polls `/api/levels` for readiness.

**Cold-start mitigation options (HostQ2 — pick one, all optional):**
1. **Accept it** (architect default for a demo): document the first-hit delay; no extra work.
2. **External uptime pinger** (e.g. UptimeRobot / cron-job.org) hitting `/api/levels` every ~10–14 min to keep the instance warm within free fair-use. Lowest effort, no code; note it consumes free-tier compute minutes and is a grey-area "keep-warm."
3. **Move to a host that idles less** (Fly.io, Fallback A) — only if (1)/(2) prove insufficient.

**`POST /api/refresh` post-deploy:** the cache builds automatically on `lifespan` startup; a manual refresh (after adding/removing Drive folders without redeploying) is a one-off authenticated-by-obscurity `POST` to `https://<app>.onrender.com/api/refresh`. **Flag (S-sec):** confirm with SECURITY_ENGINEER whether `POST /api/refresh` should be protected (it mutates in-process state and triggers Drive listing) — see §10.5 R-D6. On a spin-down host the cache is rebuilt on every cold start anyway, so manual refresh matters only within a warm session.

**If a fallback host is chosen instead:** author the minimal new artifact **only then** — Fly.io needs a `Dockerfile` (Python 3.13 base, `pip install -r requirements.txt`, `CMD uvicorn app.main:app --host 0.0.0.0 --port 8080`) + `fly.toml` (internal port 8080, `[checks]` on `/api/levels`); HF Spaces needs a `Dockerfile` listening on **port 7860** + Space "Secrets". Neither is committed unless that host is selected (REQUIREMENTS §12.5).

## 10.5 Risks / flags for PM (M8)
- **R-D1 (Render spin-down UX):** free tier idles after ~15 min → next visitor waits ~30–60s. Acceptable per HostQ2 lean, but it **is** a visible first-impression cost for a portfolio piece. PM to confirm the user accepts it or wants the §10.4(2) pinger / Fly.io fallback.
- **R-D2 (cold start re-runs Drive discovery):** because discovery is in `lifespan`, every cold boot re-lists the Drive parent — so the first post-idle request pays boot **+** a Drive round-trip. If the parent has many children this adds to the perceived cold-start time. Bounded by Drive list latency; flag for QA timing on the deployed instance.
- **R-D3 (HF Spaces = public Space + port 7860):** Fallback B exposes the **source** publicly and pins the container to 7860. App content is already public (D8), but source visibility may not be desired. Note before choosing HF.
- **R-D4 (Railway not free — HostC4):** the committed `Procfile` stays valid as a process declaration, but Railway should **not** be assumed free (usage-based trial credit only). Keep it as a portability/fallback artifact, not the HostR7 answer.
- **R-D5 (in-memory LRU resets on every cold start — host-independent):** on **any** free tier the bounded image-byte LRU + discovery map are wiped when the process recycles/spins down. This is inherent to the architecture (R2), not a host bug; the cache is a warm-session optimization, not durable state. No action needed beyond awareness; an external cache (Redis) is explicitly out of scope for M8.
- **R-D6 (`POST /api/refresh` exposure — for SECURITY review):** the refresh endpoint mutates in-process state and triggers an outbound Drive listing with the server-side key. It currently has no documented auth. **SECURITY_ENGINEER to rule** whether it needs protection (token/header) before the app is public, or whether read-only impact + rate-limit is acceptable.
- **R-D7 (free-tier egress vs streamed Drive bytes — HostR9):** the proxy streams image bytes through the host, counting against free-tier bandwidth/fair-use. Low traffic (HostQ5 lean) keeps this well under limits; the LRU reduces repeat Drive egress while warm. Flag if traffic expectations rise.
- **R-D8 (HostQ4 Drive sharing must hold in prod):** the deployed `GD_API_KEY` can only read the Drive parent if it stays **"Anyone with the link → Viewer"** (D12). If access is restricted, every fetch 502s in production (cf. §11). Confirm D12 unchanged before/at deploy — a hard runtime precondition, not just a config.
