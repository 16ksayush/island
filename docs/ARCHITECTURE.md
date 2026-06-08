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
Browser (corridor grid / island map)
   │  GET /level/{id}  (SSR page)        │  GET /api/levels/{id}/photos
   ▼                                      ▼
FastAPI (main.py) ── reads theme cookie ── renders level.html
   │                                      │
   ▼ drive_service.py ──GD_API_KEY (os.environ)──► Google Drive API (under GD_ROOT_FOLDER)
        • list parent's children → discover which numbered folders exist (dynamic scaling)
        • numbered folder {id} present → list its images (audio = LOCAL /static/audio/{theme}/level_{id}.mp3)
        • numbered folder {id} ABSENT  → 1 random image + 1 random audio from Drive `missing/` (both proxied; see §5, D6/D9)
   ▼
Browser proxies image bytes (and missing-level fallback audio) via /api/levels/{id}/media/{file_id}; never sees the key.
Existing-level audio is loaded directly from /static/audio/... (no Drive, no key).
```

## 4. Endpoints
| Method | Path | Purpose | Response |
|---|---|---|---|
| GET | `/` | Landing page; dynamic grid sized to configured levels; theme from cookie. | HTML (`index.html`) |
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
`GET /api/levels/{id}/photos` — missing level (`available: false`): exactly one fallback image + one fallback audio, both proxied (D6/D9):
```json
{
  "level": 3,
  "available": false,
  "images": [ { "file_id": "<driveImgId>", "url": "/api/levels/3/media/<driveImgId>" } ],
  "fallback_audio": { "file_id": "<driveAudioId>", "url": "/api/levels/3/media/<driveAudioId>" }
}
```
Notes: each image element is an object (`file_id` + proxied `url`), never a bare Drive URL (key isolation). `fallback_audio` is `null` for existing levels; for a missing level it is the proxied stock track the frontend uses in place of `/static/audio/{theme}/level_{id}.mp3`. Error cases: unknown `id` outside the discovered set → `404`; `file_id` not resolvable under the level's folder (or `missing/`) → `404`; upstream Drive failure → `502`.

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
- Absent numbered folder → list the Drive `missing/` folder (which holds stock images **and** stock audio) and return **1 random image + 1 random audio**, both proxied through the media endpoint.
- `GD_ROOT_FOLDER` is data (config); `GD_API_KEY` is the only secret. The parent folder is shared "Anyone with link → Viewer".

## 6. Audio (GitHub-hosted, per-theme) + crossfade engine
- All audio served as static files from `static/audio/` — no Drive, no API key.
- Landing: loop `global/{theme}_ambient.mp3`.
- Level page (existing level): play `static/audio/{theme}/level_{id}.mp3` (Horror and Sea have distinct tracks).
- Level page (missing level): use the random fallback audio served by the backend from the Drive `missing/` folder (proxied), not a local file.
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
│   ├── index.html         # landing: swaps Corridor Grid ⇄ Island Map
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
