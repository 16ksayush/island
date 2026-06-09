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
> **⚠️ Superseded by §13 (M13, 2026-06-09):** images now live in **Cloudinary** (`all ages/{N}`, `all ages/missing`) and are served from its keyless public CDN; there is no Drive proxy. The Drive description below is historical.
- **Images → Google Drive** (dynamic, proxied). One **parent** folder (`GD_ROOT_FOLDER`) with numbered child folders `0..18` + `missing/`. *(M13: → Cloudinary, §13.)*
- **Audio → GitHub repo** (`static/audio/`, version-controlled, served static). Never in Drive. *(Unchanged by M13.)*

## 3. Data flow
> **⚠️ Superseded by §13 (M13, 2026-06-09).** The as-built flow uses **Cloudinary**: one server-side Admin API list (metadata) populates an in-process cache; the browser then loads images **directly from Cloudinary's keyless public CDN** — no `/media` proxy, no per-request external byte fetch. The Drive flow below is historical.
```
Browser (haunted map / archipelago map — both illustrated, hotspot-based)
   │  GET /level/{id}  (SSR page)        │  GET /api/levels/{id}/photos
   ▼                                      ▼
FastAPI (main.py) ── reads theme cookie ── renders level.html
   │                                      │
   ▼ cloudinary_service.py ──CLOUDINARY_URL api_secret (os.environ, server-side ONLY)──►
        Cloudinary Admin API  (ONE list at startup; re-listed every IMAGE_SYNC_INTERVAL_SECONDS)
        • list resources under "all ages/" → group by asset_folder → discover levels (dynamic scaling)
        • "all ages/{N}" present → its images → keyless CDN urls (audio = LOCAL /static/audio/{theme}/level_{id}.mp3)
        • "all ages/{N}" ABSENT  → 1 random image from "all ages/missing" (keyless CDN url); audio = a random LOCAL per-theme track (REQUIREMENTS §11)
   ▼
/api/levels/{id}/photos returns absolute keyless urls
   https://res.cloudinary.com/{cloud}/image/upload/f_auto,q_auto/{public_id}.{fmt}
Browser loads image bytes DIRECTLY from Cloudinary's CDN — no proxy, no server byte fetch, no credential.
Existing-level audio is loaded directly from /static/audio/... (no external call, no key).
```

## 4. Endpoints
> **⚠️ Superseded by §13 (M13, 2026-06-09):** the `/api/levels/{id}/media/{file_id}` proxy row is **removed** (the route no longer exists); `/api/levels/{id}/photos` `url` values are now absolute **keyless Cloudinary CDN URLs**, not proxy paths.
| Method | Path | Purpose | Response |
|---|---|---|---|
| GET | `/` | Landing page; illustrated map of 19 hotspots per theme (Horror haunted map §8.3 / Sea archipelago map §9), discovery drives sealed styling; theme from cookie. | HTML (`index.html`) |
| GET | `/level/{id}` | Dedicated level page; theme-styled (room/beach). | HTML (`level.html`) |
| GET | `/api/levels` | Configured levels + availability flag (real vs missing-fallback). | `{ "levels": [{ "id": 0, "available": false }, ...] }` |
| GET | `/api/levels/{id}/photos` | Image refs for a level (each with an absolute keyless Cloudinary CDN `url`) + fallback audio ref when missing. | see §4.1 |
| GET (static) | `/static/audio/global/{theme}_ambient.mp3` | Landing ambient per theme. | audio/mpeg |
| GET (static) | `/static/audio/{theme}/level_{id}.mp3` | Per-level track (per-theme, D11). | audio/mpeg |

### 4.1 Payload schemas (JSON)
> **⚠️ §13 (M13):** the `url` field below is now an absolute **keyless Cloudinary CDN URL** (`https://res.cloudinary.com/{cloud}/image/upload/f_auto,q_auto/{public_id}.{fmt}`) instead of the `/api/levels/{id}/media/{file_id}` proxy path. The object shape (`file_id` + `url` + optional `caption`) and the `available`/`fallback_audio` semantics are otherwise unchanged. `file_id` is now the Cloudinary `public_id`.
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
# (M13, §13) media_proxy route REMOVED — images are served by Cloudinary's CDN, not proxied.
```
Theme cookie is read inside `index` / `level_page` via `request.cookies.get("theme", "horror")`.

## 5. Dynamic level + missing handling (drive_service.py)
> **⚠️ Superseded by §13 (M13, 2026-06-09):** discovery is now done by **`app/cloudinary_service.py`**, which makes **one Cloudinary Admin API list** of `resources/image` and groups by `asset_folder` (`all ages/{N}` → level N, `all ages/missing` → fallback). `drive_service.py` is **deleted**. The dynamic-scaling and missing-fallback semantics below are preserved; the source (Drive children → Cloudinary Admin list) and the access mechanism (API key + folder sharing → `CLOUDINARY_URL` api_secret) are the only changes. The "CRITICAL — Drive access method" callout below no longer applies (no Drive, no folder-sharing precondition).
- Source of truth: the **children of `GD_ROOT_FOLDER`**. List them once → the numeric-named folders define which levels exist (dynamic scaling). The grid renders exactly those; gaps still render a door/island flagged `available: false`. *(M13: source is now the Cloudinary Admin list grouped by `asset_folder` under `all ages/`.)*

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
> **⚠️ M1 baseline — superseded.** This tree predates M11/M12/M13. As-built (M13): `app/drive_service.py` is **deleted** and replaced by `app/cloudinary_service.py`; `scripts/` (the M12 bake) is **deleted**; `app/captions.py` + `app/captions.json` (M11) are present; `.env.example` holds `CLOUDINARY_URL` + `IMAGE_SYNC_INTERVAL_SECONDS`. See the current tree in `README.md` ("Project structure") and §13.
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

---

# 11. Image captions (dual-theme) (M11 / CapR1–CapR7, NF-Cap1–NF-Cap6, CapQ1–CapQ7)

Status: **BUILT + verified — matches this design (2026-06-09; full suite 156 passed; pending commit).** The as-built code implements §11.1–§11.4 exactly: the `(level, filename)` key (§11.1) is read from `PhotoRef.name`; `app/captions.py` is the tolerant startup-cached loader re-read on `POST /api/refresh` (§11.2/§11.7); `app/main.py`'s `_ref` helper performs the caption lookup and attaches an **optional** `caption:{sea,horror}` to each image object (omitted when absent — additive, backward-compatible, §11.3); and `templates/level.html` renders a per-slide `<figcaption class="slide-caption">` theme-skinned in `static/style.css` (§11.4). Data file `app/captions.json` holds **52 images × {sea,horror} = 104 captions** (levels 1, 2, 8–18); subject = nickname "Chudail" (no PII — NF-Cap2). This section is additive to §1–§10; it changed **no route signature**, is **payload-backward-compatible** (CapR6/NF-Cap5), and touched **no decision D1–D13**. The feature is **optional/degrade-to-nothing by design**: an image with no caption renders exactly as today.

## 11.1 Caption → image key — RESOLVES CapQ1 / CapR4 (the pivotal decision)

**Recommendation: key captions by `(level, filename)`, NOT by Drive `file_id`.**

The two candidate shapes (both shown so the tradeoff is explicit):

**Candidate A — keyed by Drive `file_id` (REJECTED):**
```json
{
  "1AbCxyz_driveFileId": { "sea": "...", "horror": "..." },
  "9KmNopq_driveFileId": { "sea": "...", "horror": "..." }
}
```
- Pro: the id is exactly what the payload already exposes (`_ref` emits `file_id`), so the frontend match is trivial and the backend needs no extra lookup.
- **Con (fatal): Drive file ids are NOT stable across re-upload.** If the user re-uploads even one photo (re-crop, rotate, replace), Drive mints a **new id** and that image silently loses its caption. The user explicitly intends this as a long-lived personal gift they may tweak — fragile keys are the wrong default. It also makes the committed file unreadable to a human editor (opaque ids).

**Candidate B — keyed by `(level, filename)` (CHOSEN):**
```json
{
  "1": {
    "1.1.jpeg": { "sea": "...", "horror": "..." },
    "1.2.jpeg": { "sea": "...", "horror": "..." }
  },
  "9": {
    "9.1.jpeg": { "sea": "...", "horror": "..." }
  }
}
```
- The confirmed Drive naming convention is `{level}.{index}.jpeg` (REQUIREMENTS §7; verified in the test fixtures, e.g. `1.1.jpeg`). The backend **already carries the filename** on every `PhotoRef` (`PhotoRef.name`, `drive_service.py`), so this key is available with zero new Drive calls.
- **Stable across re-upload:** as long as the re-uploaded file keeps its `{n}.{i}.jpeg` name, the caption follows it even though the Drive id changed. This is the property the gift use-case needs.
- **Human-editable:** the committed file reads as "level → photo name → two lines," so the user can hand-edit a caption with no knowledge of Drive ids (NF-Cap6).

**Chosen schema (top-level object keyed by level-id string → filename → `{sea, horror}`):**
```jsonc
// captions.json — single source of truth (CapR3). Keys are STRINGS (JSON).
{
  "<level-id>": {
    "<filename>": { "sea": "<one-liner>", "horror": "<one-liner>" }
  }
}
```
Field rules:
- Both `sea` and `horror` are short one-liners (length budget §11.4). A caption entry **MAY be partial or absent** — a missing filename, a missing level, or a missing `sea`/`horror` sub-key all degrade gracefully to "no caption shown for that theme" (CapR6, NF-Cap1 optional rule). Loader and payload builder MUST treat absence as the normal, non-error case (never raise, never emit an empty caption box).
- Levels `0, 3–7` (missing fallback) carry **no entries** (CapR5 / CapQ6 lean = uncaptioned). The `missing/` images are re-rolled per request (R3) and have no stable identity, so per-image captions are impossible there; the default is simply no caption (an optional single generic per-theme placeholder is a later, trivial addition and is NOT designed in now).

## 11.2 Storage + load path — RESOLVES CapQ7 / CapR3

- **File + location:** a single committed **`app/captions.json`** (next to `app/main.py` / `app/drive_service.py`). Rationale: it is backend-loaded application data, not a browser asset (so NOT under `static/`, which would needlessly serve it to clients and invite scraping the whole set in one request) and not a stray repo-root file. JSON over YAML — no new dependency, mirrors the project's existing JSON payloads, and the structure is shallow.
- **Load path: load once at startup, cache in memory** — mirrors the R2 discovery-cache model (§5.1). Add a tiny module (e.g. `app/captions.py`) exposing a cached `dict[str, dict[str, dict[str, str]]]` plus a `get_caption(level_id, filename) -> dict|None` accessor. The file is read **once** in the FastAPI `lifespan` (alongside `discover_levels(force=True)`), and **re-read on `POST /api/refresh`** so a caption edit can be picked up without a redeploy (consistent with how refresh already rebuilds discovery state).
- **Loader contract (tolerant by design):**
  - Missing file → log a debug note, set the cache to an **empty map**; the feature is simply inert (every image renders uncaptioned). Never raises — this keeps local/dev/CI runs and the "captions not yet written" state working (CapR6, NF-Cap5).
  - Malformed JSON → log a warning, fall back to the empty map (fail-soft, never crash startup — same philosophy as discovery's graceful degradation).
  - Lookups are pure dict gets keyed by `str(level_id)` then `filename`; no I/O per request (no first-paint or slide-preload cost, NF-Cap5).
- **No database** (CapR3) and **no admin UI** (out of scope) — adding/editing a caption is a one-line edit to `app/captions.json` + a process restart or `POST /api/refresh`.

## 11.3 Backend payload surface — RESOLVES CapR6 (additive, backward-compatible)

**Recommendation: extend each image element with an OPTIONAL `caption` object carrying BOTH themes; let the client pick by active theme. Do NOT theme-resolve server-side.**

Each image element in `GET /api/levels/{id}/photos` grows from:
```json
{ "file_id": "<driveId>", "url": "/api/levels/1/media/<driveId>" }
```
to (caption present):
```json
{
  "file_id": "<driveId>",
  "url": "/api/levels/1/media/<driveId>",
  "caption": { "sea": "<one-liner>", "horror": "<one-liner>" }
}
```
and (caption absent — unchanged from today, no `caption` key emitted):
```json
{ "file_id": "<driveId>", "url": "/api/levels/1/media/<driveId>" }
```

Full updated `GET /api/levels/{id}/photos` — existing level with captions:
```json
{
  "level": 1,
  "available": true,
  "images": [
    {
      "file_id": "<id-a>",
      "url": "/api/levels/1/media/<id-a>",
      "caption": { "sea": "Built an entire kingdom out of one cardboard box.",
                   "horror": "The architect of the box fort. Its blueprints were never found." }
    },
    {
      "file_id": "<id-b>",
      "url": "/api/levels/1/media/<id-b>"
    }
  ],
  "fallback_audio": null
}
```
(The second element shows the partial/absent case in the same response — the `caption` key is simply **omitted** when no entry exists; clients render it uncaptioned.) Missing-level payloads (levels 0, 3–7) are **unchanged** — one proxied fallback image, no `caption`, `fallback_audio: null`.

**Why both captions, not server-resolved:** the client already knows the active theme (SSR `var theme`), and returning both lets the **theme toggle switch captions live without a refetch** — important because a visitor can toggle Horror⇄Sea on the level page and the visible slide's caption should flip instantly (CapR1, mirrors D1's no-flash model). Server-resolving by cookie would force a re-fetch on every toggle and couple the JSON endpoint to the cookie for no benefit.

**The only backend change is inside `_ref` in `app/main.py`** (the per-image serializer). It gains a caption lookup keyed by `(level_id, photo.name)` against the cached map and conditionally adds the `caption` key. To do this `_ref` needs the photo's **name** — which `PhotoRef` already carries — so the change is: pass `photo` (already passed) and read `photo.name`; no `drive_service` signature change, no new Drive call, no route-signature change (the §4 route table is unchanged).

**Backward-compatibility proof (CapR6, NF-Cap5):**
- The field is **purely additive and optional**. Clients that ignore unknown keys (today's `level.html` reads only `img.url`) are unaffected.
- **Existing tests stay green.** The `/photos` tests assert *membership/values* (`img["file_id"] in {...}`, `img["url"] == f"…/media/{img['file_id']}"`) — none assert an exact key set (no `set(img.keys()) == {"file_id","url"}`). Verified in `tests/test_backend.py` (lines ~99–103, 162–165) and `tests/test_cache.py`. Adding an optional `caption` key does not break any current assertion. **Flag for QA:** keep new caption assertions tolerant of absence; do not retrofit a strict-key assertion onto these tests.

## 11.4 Frontend display — RESOLVES CapQ2 / NF-Cap4 (theme-styled, per-slide)

**Recommendation: an overlaid bottom caption bar on each slide** (a theme-styled gradient scrim pinned to the bottom of the `.slide` figure), reading `image.caption[theme]`, updating naturally as the slideshow advances because each slide owns its own caption element.

Markup/CSS hook plan (parallel to the existing slideshow primitives, theme-scoped like §8/§9):
- In `renderImages(images)` (`level.html`), when building each `.slide` `<figure>`, also build a `<figcaption class="slide-caption">` **iff** `img.caption && img.caption[theme]` is a non-empty string. Append it inside the figure (so it travels with the slide; no separate sync logic needed, no regression to slide timing/scroll/dots). If absent → emit nothing (no empty box, CapR6).
- Use `<figcaption>` inside the existing `<figure class="slide">` — semantically correct (the caption describes the figure's image) and improves accessibility for free.
- New CSS classes (additive to `static/style.css`):
  - `.slide-caption` — base layout: absolutely positioned to the bottom of the slide, full width, padding, a bottom-up gradient scrim (`linear-gradient(transparent → rgba(0,0,0,.7))`) so text is legible over any photo, `pointer-events:none` so it never blocks swipe/scroll, single-line by default with graceful wrap allowance on small screens.
  - `.theme-horror .slide-caption` — gothic skin (amber `--accent` text, serif/condensed display feel matching the Horror tokens, slightly heavier scrim).
  - `.theme-sea .slide-caption` — sunlit skin (light text or deep-azure text on a soft scrim, lighter/airier weight matching the Sea palette).
  - These follow the §8.6 / §9.7 isolation rule: every themed rule is prefixed `.theme-horror` / `.theme-sea`; the shared `.slide-caption` base carries only neutral layout, no palette.
- **Live theme toggle:** because the payload carries both captions, the theme toggle can re-render or re-select the caption text per slide without refetching. Simplest implementation: store `img.caption` on the figure (e.g. a `data-*` or a small JS map) and, on a theme change event, update each `.slide-caption` text from the new theme key (the toggle already triggers a repaint/reload in the §1 model, so even a full reload re-runs `renderImages` and reads the new SSR `theme` — either path works; the data being present client-side is what matters).
- **Mobile behavior (NF-Cap4):** the overlay scrim sits at the slide bottom; on narrow viewports allow up to 2 lines then ellipsis (`-webkit-line-clamp`) so a caption never grows the slide box or pushes the dots/nav. If overlay crowding is observed on the smallest breakpoint, the documented fallback is to drop the caption **below** the stage on `≤480px` (a media-query swap, no markup change). Verify at QA.
- **Length budget (NF-Cap4):** soft target **≤ ~70 characters** per line (hard cap ~90 before clamp). The generation step (§11.5) writes to this budget; the CSS clamp is the safety net, not the primary control.
- **No regression:** captions live inside each existing slide figure, behind no new fetch, with `pointer-events:none`. Slide timing (3s auto-advance), prefetch/eager-preload, the audio crossfade engine, and theme isolation are untouched (NF-Cap5) — the diff is `renderImages` (add an optional `<figcaption>`) + additive `.slide-caption` CSS.

## 11.5 Caption generation pipeline (design only — NOT executed in this phase)

The execution phase (after sign-off) produces `app/captions.json` as follows:
1. **Enumerate** the 50 real images across levels `1, 2, 8–17` via the running app: `GET /api/levels/{id}/photos` yields each `{file_id, url}`; the backend also knows each `name`.
2. **View each image** through its proxy `url` (`/api/levels/{id}/media/{file_id}`) — vision-capable inspection happens here, in execution, not now.
3. **Draft `{sea, horror}`** per image under the **NF-Cap1 tone guardrail** (Sea = warm/funny-sweet; Horror = whimsical playful-gothic, cute-spooky — never creepy, never about appearance/body, never sexualizing, never unkind; subject is a real minor + a gift).
4. **Emit a 50×2 review table** (Markdown: image ref / level / filename / Sea line / Horror line) for the **user to edit and approve** (CapR7, NF-Cap3, CapQ5).
5. **Only after sign-off**, write the approved set to `app/captions.json` keyed by `(level, filename)` (§11.1). SECURITY_ENGINEER / QA review the tone of every line as a content-safety gate (NF-Cap1); any line that reads creepy / body-focused / sexualizing / unkind is rejected and rewritten.

This whole step is **gated on user sign-off** of CapQ3 (tone), CapQ4 (privacy/naming), and CapQ5 (review flow). No bytes of caption text are produced before that gate.

## 11.6 Theme-isolation + no-regression proof (NF-Cap5)

**Entire diff surface for M11:**
1. **`app/captions.json`** (NEW, committed) — the caption data, keyed `(level, filename)`.
2. **`app/captions.py`** (NEW) — tolerant startup loader + cached `get_caption()` accessor.
3. **`app/main.py`** — call the loader in `lifespan` (next to discovery) and on `POST /api/refresh`; extend `_ref` to add the optional `caption` key. **No route signature changes** (§4 table unchanged).
4. **`templates/level.html`** — `renderImages` adds an optional `<figcaption class="slide-caption">` per slide; optional toggle-driven re-select.
5. **`static/style.css`** — additive `.slide-caption` base + `.theme-horror`/`.theme-sea` skins.

Untouched: `app/drive_service.py` (no signature/behavior change — `PhotoRef.name` already exists), discovery (§5.1), the media proxy + scope guard (R1), the audio engine, the prefetch worker, both landing maps (§8/§9), and all other routes/payloads. The payload change is additive-only (§11.3). Both theme landings render byte-identical to today.

## 11.7 Recommended defaults for open questions (CapQ1–CapQ7)
- **CapQ1 (key):** **RESOLVED (architect) — `(level, filename)`.** Stable across re-upload, human-editable, available from `PhotoRef.name` with zero new Drive calls. `file_id` rejected (re-upload fragility).
- **CapQ2 (placement):** **RESOLVED (architect, default) — overlaid bottom gradient bar (`<figcaption class="slide-caption">`), theme-styled**; documented `≤480px` fallback to below-stage if overlay crowds. Visual eyeball at QA.
- **CapQ3 (tone guardrail — CRITICAL):** **NEEDS USER SIGN-OFF.** Confirm Horror = playful-gothic/cute-spooky & affectionate (never creepy/body-focused/sexualizing/unkind) and Sea = funny-sweet. Generation MUST NOT start without this.
- **CapQ4 (privacy/naming):** **NEEDS USER DECISION.** The repo + Render URL + Drive are public (NF-Cap2). Architect lean: **avoid the sister's real name and any identifying detail** (school, surname, addresses); use affectionate generic phrasing.
- **CapQ5 (review flow):** **RESOLVED (architect, default) — assistant drafts by viewing each image → 50×2 Markdown review table → user edits → approved set written to `app/captions.json`.** Confirm the review-table surface.
- **CapQ6 (missing-level images):** **RESOLVED (architect, default) — uncaptioned.** Re-rolled fallback images have no stable identity; an optional single generic per-theme placeholder is a trivial later add, not designed now.
- **CapQ7 (storage/format/location/load):** **RESOLVED (architect) — `app/captions.json`, keyed `(level, filename)`, loaded once at startup + cached + re-read on `POST /api/refresh`; tolerant loader (missing/malformed → empty map → feature inert).**

**Resolved-with-default (no user input required to proceed):** CapQ1, CapQ2, CapQ5, CapQ6, CapQ7. **Needs an explicit USER decision before generation:** CapQ3 (tone — hard content gate) and CapQ4 (privacy/naming).

## 11.8 Technical risks / flags for PM (M11) — R-Cap1…R-Cap6
- **R-Cap1 (re-upload key fragility):** keying by `file_id` would silently drop a caption when an image is re-uploaded (new Drive id). **Mitigated by the §11.1 decision** to key by `(level, filename)` — stable as long as the re-uploaded file keeps its `{n}.{i}.jpeg` name. Residual: if the user renames a file on re-upload, its caption goes inert (degrades to no caption, never errors) — document the naming convention as the contract.
- **R-Cap2 (privacy — public repo holds captions about a real minor):** `app/captions.json` is committed to a **public** GitHub repo and served (indirectly) via a public URL describing the user's sister (NF-Cap2). **Mitigations:** no real name, no identifying details (school/surname/address); affectionate generic phrasing only; user signs off on CapQ4. **Flag to PM/SECURITY for the data-flow review.**
- **R-Cap3 (content-safety gate on generation — CRITICAL):** the subject is a real **minor** and the deliverable is a **gift**; the Horror "dark" tone must stay cute-spooky, never creepy/body-focused/sexualizing/unkind (NF-Cap1). Generation is **blocked until CapQ3 sign-off**, and every generated line passes a SECURITY/QA tone review. Highest-sensitivity item in M11.
- **R-Cap4 (mobile overlay overflow):** a long caption could crowd the slide or push dots/nav on small screens (NF-Cap4). **Mitigated:** ≤~70-char budget + `-webkit-line-clamp` safety net + documented ≤480px below-stage fallback. Verify on real mobile at QA.
- **R-Cap5 (payload-shape test fragility):** an existing `/photos` test that hard-asserted the image-object key set would break on the new optional `caption` key. **Checked — none do** (current tests assert membership/values only; `tests/test_backend.py`/`tests/test_cache.py`). Flag: keep future caption tests tolerant of caption absence; do not introduce a strict-key assertion.
- **R-Cap6 (stale captions after Drive edit without refresh):** because the map is cached at startup, a caption edit needs a restart or `POST /api/refresh` to take effect (same model as discovery). Low severity; documented in §11.2. Note that `POST /api/refresh` is itself slated to be token-gated (R-D6) — the caption reload rides that same protected endpoint.

---

# 12. Build-time image baking + periodic background sync (M12 / BakeR1–7, NF-Bake1–7, BakeQ1–6, R-Bake1–8)

Status: **BUILT + verified — as-built matches this design (2026-06-09; full suite 182 passed / 0 failed; pending commit).** The as-built code implements §12.1–§12.13 exactly: `scripts/fetch_images.py` is the single paced source of truth (reuses `drive_service` discovery + the shared `download_images_paced` downloader; writes `static/img/levels/{id}/{PhotoRef.name}` + the baked `missing/` set + `manifest.json`, §12.2/§12.3/§12.4); `app/drive_service.py` adds the tolerant `load_manifest`/`load_discovery` loader (manifest PRIMARY → Drive-metadata FALLBACK → empty gallery) into the existing `DiscoveryCache` shape, plus `is_safe_name`, the shared `download_images_paced`, and the single-flight `run_sync_once`/`background_sync_loop` (§12.13); `app/main.py`'s `_ref` emits the static `url` (file_id + name preserved — caption key byte-for-byte, NF-Bake4) with a baked-else-proxy guard for un-baked dev (§12.8), the `lifespan` is manifest-PRIMARY and starts/cancels the gated background sync via `_image_sync_interval()`, and `POST /api/refresh` triggers an immediate sync (§12.13.5); `render.yaml`'s `buildCommand` runs the bake and adds `IMAGE_SYNC_INTERVAL_SECONDS=1800`; `.gitignore` ignores `static/img/levels/` (NF-Bake1, D9 audio allow-list intact). **BakeQ1 = KEEP** the `/media` proxy as a guarded, non-default fallback (R1 open-proxy guard intact — the `manifest:{lid}` sentinel does NOT bypass scope); **BakeQ4 = retry/backoff + WARN/serve-partial**; BakeQ2/Q3/Q5/Q6 as designed. SECURITY (B6) APPROVED: no secret in manifest/payload/logs (NF-Bake5), no path traversal, sync off in tests. It is additive to §1–§11; the CRITICAL Drive note (§5), all decisions D1–D13, and the shipped M9/M10/M11 features are preserved. **The hard gate NF-Bake4 held: the baked filename equals `PhotoRef.name`, so the M11 `(level, filename)` caption key keeps matching byte-for-byte (all 104 captions hold).**

## 12.1 Why this works on Render (the load-bearing fact)
The throttle we are fixing is on Drive's **download** endpoint (`files.get?alt=media`) — a burst of 52 byte-downloads returned a 403 "rate-limit" page (REQUIREMENTS §14.1, the same burst recorded in M11). Drive **metadata** calls (`files.list`, `files.get` without `alt=media`) are **not** throttled the same way. Approach A moves all `alt=media` downloads to a **single, paced, build-time** pull instead of per-request bursts.

Render makes this clean: the build env (`GD_API_KEY`, `GD_ROOT_FOLDER`, both `sync:false`) is available **during the build command**, and the build output is **part of the served instance image** — re-fetched only on redeploy, never on a cold-start spin-up. So the free-tier ephemeral runtime filesystem is a non-issue for baked images: they are baked once per deploy and ride the instance.

## 12.2 The build-time fetch/bake script — `scripts/fetch_images.py`
A single standalone script (NF-Bake7: one source of truth, used by both `render.yaml` and local dev). It is **not** imported by the app at runtime; it runs only at build/dev time.

**Responsibilities**
1. **Discover** (metadata only, not throttled): reuse `drive_service.discover_levels(force=True)` to build `folder_index` / `missing_folder_id` and the per-level scope lists (`level_images`, `missing_images`) — these already carry `PhotoRef{file_id, name}`. This is the same code path the app uses, so the bake set is exactly the discovered set (NF-Bake7, no second discovery implementation).
2. **Download** each image's bytes to `static/img/levels/{id}/{PhotoRef.name}` (and the `missing/` set to `static/img/levels/missing/{PhotoRef.name}`, BakeQ2). Download via the SAME mechanism as `resolve_media` (`files.get?alt=media` with `GD_API_KEY`), but **paced** (see below) and writing to disk rather than the LRU.
3. **Idempotent / resumable:** **skip** a file that already exists on disk with a non-zero size (so a re-run after a partial failure only pulls the remainder, and local dev re-runs are cheap). A `--force` flag re-downloads.
4. **Write a manifest** (BakeQ3): `static/img/levels/manifest.json` capturing the discovered structure (see §12.4).
5. **Throttle + retry** (NF-Bake2, the core of this milestone — see §12.3).
6. **Runnable locally** (BakeQ6): `python scripts/fetch_images.py` with the developer's `.env` (`GD_API_KEY`/`GD_ROOT_FOLDER`) populates `static/img/levels/` identically to the build.

**Script CLI shape (design, not implementation):**
```
python scripts/fetch_images.py
    [--out static/img/levels]      # base output dir (default)
    [--concurrency 2]              # max simultaneous alt=media downloads (default 2)
    [--delay 0.4]                  # seconds between request starts, per worker (default 0.4s)
    [--max-retries 5]              # retry budget per file on 403/429/5xx
    [--force]                      # re-download even if the file already exists
    [--skip-missing]               # do NOT bake the missing/ set (default: bake it)
    [--manifest]                   # write manifest.json (default: on)
```

**Pacing defaults (NF-Bake2, tuned for the 52-image set + headroom):**
- **Concurrency = 2** (a small worker pool; NOT the wide burst that tripped the 403). Single-threaded (concurrency 1) is the safest fallback if 2 still throttles.
- **Inter-request delay = 0.4 s** per worker start (so ~5 downloads/sec aggregate at concurrency 2 — well under a burst). Jittered ±20% to avoid lockstep.
- **Retry with exponential backoff + jitter on 403 / 429 / 5xx:** base 2 s, doubling (2, 4, 8, 16, 32 s), `--max-retries 5`. A 403/429 is treated as a throttle signal (back off and retry the SAME file), not a hard failure, until the retry budget is exhausted.
- **Order:** download level-by-level in ascending id; this keeps logs readable and makes a partial bake deterministic (lower levels complete first).
- These defaults bake 52 images in well under a minute at steady state while staying gentle; R-Bake5 (Render build-time limit) is verified at execution by measuring actual bake duration.

**Security in the script (NF-Bake5):** `GD_API_KEY` is read ONLY via `os.environ` (reuse `drive_service._get_api_key()`); it is never written to the manifest, never embedded in a filename/path, never logged (mirror the existing log-status-only discipline in `drive_service`). The script writes only image bytes + a manifest of `{file_id, name}` (file_id is already client-visible today in the payload, so the manifest exposes nothing new — see §12.7).

## 12.3 Static layout + URL scheme — RESOLVES BakeQ5 (NF-Bake4, the hard gate)
**Layout on disk (= served paths):**
```
static/img/levels/
├── manifest.json                       # build-written discovery manifest (§12.4)
├── 1/   2.1.jpeg-style files…          # filename == PhotoRef.name, VERBATIM
├── 2/   …
├── 8/ … 18/                            # every available level
└── missing/  <missing-set filenames>   # baked missing/ images (BakeQ2)
```
The on-disk filename is `PhotoRef.name` **verbatim** (`{n}.{i}.jpeg`, e.g. `2.1.jpeg`). Served URL = `/static/img/levels/{id}/{name}`.

**Why this preserves the caption key (NF-Bake4):** M11 keys captions by `(level, filename)` where `filename == PhotoRef.name` (`app/captions.py` `get_caption(level_id, photo.name)`). Because the baked filename **is** `PhotoRef.name`, the `(level, filename)` key is byte-identical before and after baking — all 104 captions keep matching with **zero change to `captions.json` or `captions.py`**.

**The `_ref` change (`app/main.py`) — the ONLY payload change (BakeR3):**
```python
def _ref(photo) -> dict:
    ref = {
        "file_id": photo.file_id,                                   # KEPT (back-compat)
        "url": f"/static/img/levels/{level_id}/{photo.name}",       # WAS /api/levels/{id}/media/{file_id}
        # caption block UNCHANGED — still keyed (level_id, photo.name)
    }
    ...
```
- `url` flips from the proxy path to the static path. **`file_id` and `name` stay in the payload** (back-compat for any caller; `file_id` is also the BakeQ1 fallback hook).
- For the **missing** fallback (BakeQ2 = baked), the re-rolled image's `url` is `/static/img/levels/missing/{photo.name}`. The per-visit re-roll (R3) still happens in `get_level_photos` — it just picks from the cached `missing_images` list and the URL points at the local baked copy.
- Payload **shape is unchanged**; only the `url` **value** changes (assert tolerantly — R-Bake7).

**Odd / duplicate filenames (BakeQ5 edge):** the confirmed real set is uniform `{n}.{i}.jpeg` (REQUIREMENTS §7/§14.2), so per-level filenames are unique and filesystem-safe. The script MUST nonetheless: (a) reject/skip a filename containing a path separator or `..` (defense, NF-Bake5 — no traversal via a hostile Drive name); (b) if two images in the SAME level folder share a name (would collide on disk AND would already be a broken caption key in M11), log a loud warning and suffix the second (`name` → `name#2`) — but this also signals a caption-key problem upstream, so it is flagged, not silently swallowed. With the confirmed set this branch never triggers; it exists so a future odd upload fails visibly, not silently.

## 12.4 Discovery source — RESOLVES BakeQ3 (BakeR4)
**Recommendation: a build-written manifest is the PRIMARY source at runtime; Drive metadata discovery is the FALLBACK.** This gives a **zero-Drive-call cold start** (throttle-proof, faster spin-up on Render) while keeping the app fully functional even with NO Drive credentials at runtime (a genuine static-serving model).

**`static/img/levels/manifest.json` shape (build-written):**
```json
{
  "generated_at": "2026-06-09T12:00:00Z",
  "levels": [
    { "id": 1, "available": true,
      "images": [ { "file_id": "<driveId>", "name": "1.1.jpeg" }, ... ] },
    { "id": 2, "available": true, "images": [ ... ] },
    { "id": 0, "available": false, "images": [] },
    ...
  ],
  "missing": { "images": [ { "file_id": "<driveId>", "name": "m1.jpeg" }, ... ] },
  "span": { "min": 0, "max": 18 }
}
```
- It carries exactly what discovery produces: the level span (`0..max`), each available level's `{file_id, name}` image list, and the baked `missing/` set. **No `GD_API_KEY`, no folder ids** — only `file_id` + `name`, which are already client-visible today (§12.7).
- **App read path:** a small loader in `drive_service` (mirroring `captions.py`'s tolerant-loader pattern) reads `manifest.json` at `lifespan` startup into the SAME `DiscoveryCache` shape (`folder_index` analog → "available" set, `levels` span, `level_images`, `missing_images`). The existing consumers are then UNCHANGED:
  - `_levels_payload()` → `{id, available}` from the manifest's level list (drives F1 sealed styling, unchanged user-facing semantics, BakeR4).
  - `get_level_photos(id)` → the manifest's `images` for an available level; the per-visit re-roll from `missing.images` for a missing level (R3 preserved).
- **Fallback chain (resilient):** if `manifest.json` is absent or malformed (e.g. local dev that hasn't baked, or a manifest-less build), fall back to live Drive **metadata** discovery (the current `discover_levels()` path — metadata is not throttled). If THAT also fails (no creds), degrade to the empty gallery exactly as today. So the manifest is an optimization + a no-creds-runtime enabler, never a single point of failure.
- **`POST /api/refresh` semantics (NF-Bake6):** under the manifest model, refresh **re-reads the manifest** (and re-reads captions). It does **not** download new images — new/changed images require a redeploy (re-bake). This is documented and acceptable ("won't add many more"). If the manifest is absent and refresh falls back to Drive metadata, it re-lists but still won't bake — same conclusion.

## 12.5 Keep or drop the `/media` proxy — RESOLVES BakeQ1 (BakeR7)
**Recommendation: KEEP `/api/levels/{id}/media/{file_id}` as a guarded, opt-in fallback — but it is NOT on the default request path.** The baked static URL is what `_ref` emits, so a warm gallery never calls the proxy. The proxy remains for resilience: a not-yet-baked or newly-added `file_id` (manifest says it exists, disk doesn't yet) can still resolve via Drive instead of 404-ing until the next redeploy. This pairs with the graceful build-failure policy (§12.6) and the local-dev fallback (§12.8).

- **If KEPT (recommended):** `drive_service.resolve_media()`, the byte LRU, and the route all stay, and **all existing security ACs remain in force** — R1 (`file_id` validated ∈ the level's folder OR `missing/` via the cached scope set) and R6 (echo upstream `Content-Type`). The throttle path technically still exists, but it is only reached for an un-baked id (rare, single file), never a bulk burst — so it does not reintroduce the 403 risk. Consequence for R-Bake/throttle: the bulk-throttle risk is eliminated (no bursts); only a degenerate single-file fetch remains.
- **Alternative (DROP, pure-static):** remove the route + `resolve_media()` + the byte LRU for the smallest surface. Consequence: an un-baked id 404s until redeploy, AND the build-failure policy MUST then be **fail-the-build** (§12.6) since there is no runtime safety net. Security upside: zero open-proxy surface at runtime. **Security note (NF-Bake5):** if dropped, confirm no client-reachable artifact (`file_id` in the payload/manifest) re-enables an ad-hoc proxy — it cannot, because the route itself is gone; `file_id` becomes a pure caption/back-compat token with no live endpoint behind it.
- **Default chosen:** KEEP (resilience + clean local dev), gated so it is never the bulk path. Architect notes the DROP option is a one-line follow-up if the SECURITY_ENGINEER prefers a zero-proxy runtime surface.

## 12.6 Build-failure policy — RESOLVES BakeQ4 (NF-Bake2)
Tied to the BakeQ1 decision:
- **With the proxy KEPT (recommended): retry-with-backoff, then WARN + serve-partial.** A file that still 403s after the full retry budget is **logged loudly and skipped**; the build **succeeds** and ships whatever baked. At runtime the manifest still lists that image; its static file is missing, so the app can fall back to the proxy for that one id (or, if the proxy is later dropped, it 404s for that one slide). This is the graceful path and is safe because the proxy backstops the gap.
- **If the proxy is DROPPED (pure-static): retry-with-backoff, then FAIL the build.** No partial/stale deploy — a missing image has no runtime fallback, so an incomplete bake must not ship. The deploy fails, the operator re-runs (the idempotent script resumes from where it stopped), and the prior good instance keeps serving until a clean bake succeeds.
- Either way the bake **must not** loop forever — the per-file retry budget bounds total time (R-Bake5).

## 12.7 Security + back-compat proof (NF-Bake5 / NF-Bake4 — hard gates)
- **`GD_API_KEY` never leaves the server/build (F10, veto):** the key is used only by `scripts/fetch_images.py` (build/dev) and, if BakeQ1 keeps it, by `resolve_media` (server). It is NEVER written to `static/img/levels/` (only image bytes are), NEVER in `manifest.json`, NEVER in the `/photos` payload, NEVER in any client bundle. The script logs status codes only (reusing `drive_service`'s discipline).
- **The manifest exposes nothing new:** it contains `file_id` + `name` only. `file_id` is **already** in today's `/photos` payload (`_ref` emits it), and `name` (the filename) becomes visible in the static URL anyway. No folder ids, no key, no new data class crosses the boundary versus today.
- **No path traversal serving static files (NF-Bake5):** files are served by FastAPI `StaticFiles` from `static/`, which already normalizes/sandboxes paths. The bake script additionally refuses to WRITE a filename containing `/`, `\`, or `..` (§12.3 edge), so a hostile Drive filename cannot escape `static/img/levels/{id}/`. `{id}` in the URL maps to a directory name that only ever exists if the build created it.
- **Caption back-compat (NF-Bake4, hard gate):** baked filename == `PhotoRef.name` ⇒ `(level, filename)` key unchanged ⇒ all 104 M11 captions still attach. `captions.json` and `captions.py` are **untouched**. QA asserts every caption still attaches after the URL switch (R-Bake3).
- **No regression to M8/M9/M10/M11:** routes other than the `_ref` `url` value (and the optional BakeQ1 proxy keep/drop) are unchanged; the maps, audio engine, prefetch, theme isolation are untouched (theme-agnostic change). The `/photos` payload shape is preserved (only `url` value changes — assert tolerantly, R-Bake7).

## 12.8 `render.yaml` integration + local dev (NF-Bake6 / BakeQ6) + the M8 coupling
**`render.yaml` `buildCommand`:**
```yaml
buildCommand: pip install -r requirements.txt && python scripts/fetch_images.py
```
- Build env vars `GD_API_KEY` / `GD_ROOT_FOLDER` (`sync:false`) are available at build, so the script authenticates exactly as the app does. Drive sharing must stay "Anyone with the link → Viewer" (D12 / HostQ4) for the build to read it — already a deploy precondition.
- **Build-failure behavior** follows §12.6: under the recommended KEEP-proxy + graceful-degrade, a paced-but-still-throttled file warns and the build proceeds; under DROP-proxy it fails the build. The script's exit code encodes this (non-zero only in the fail-the-build mode).

> **⚠️ M8 shared-file coupling (do NOT fight it):** `render.yaml` is **also** being edited by M8 — region `oregon → singapore` (REQUIREMENTS §12.5, HostQ5) and (separately) the `/api/refresh` token-gate is a backend change, not a `render.yaml` one. M12 only touches the **`buildCommand` line**; M8 only touches the **`region` line**. These are non-overlapping edits to the same file — coordinate the commit so both land (the PM sequences B5 against the M8 edit), but neither blocks the other. Do not revert M8's region change while editing `buildCommand`.

**Local dev (BakeQ6):** run the **same** `scripts/fetch_images.py` with a local `.env` (`GD_API_KEY`/`GD_ROOT_FOLDER`) — identical bake into `static/img/levels/`. Graceful states when unbaked:
- **Manifest present, files present:** normal — serves static (the post-bake state, prod-like).
- **Manifest absent / dir empty:** the app falls back to live Drive **metadata** discovery (§12.4); image `url`s would then point at the static path that doesn't exist yet → the developer either runs the bake, OR (if BakeQ1 keeps the proxy) the app can emit proxy URLs in this un-baked mode. **Recommended dev ergonomics:** `_ref` checks "is this level baked?" (manifest/disk) and emits the static URL when baked, else the proxy URL when the proxy is kept — so a fresh clone with no bake still shows images via the proxy, and a baked clone shows them statically. This keeps local onboarding to "set `.env`, run `uvicorn`" with the bake as an optional speed/parity step.
- **No creds at all:** empty gallery (exactly as today) — no crash.

## 12.9 `.gitignore` rule — RESOLVES NF-Bake1 (R-Bake2, no allow-list regression)
The baked images are **personal photos in a PUBLIC repo** — they must NEVER be committed (privacy + bloat). The current `.gitignore` is **allow-list style** (negations re-include `static/`, `static/audio/`, `static/audio/**/*.mp3`) and has **no broad `static/` ignore**, so today the baked dir would be commit-eligible. Add an **explicit, narrow ignore for the baked dir only**, placed AFTER the existing allow-list block so a later negation cannot accidentally re-include it:

```gitignore
# ── Baked level images (M12) — personal photos, build output ONLY, NEVER committed ──
# Fetched at build time by scripts/fetch_images.py into static/img/levels/.
# This dir is ignored AFTER the static/ allow-list so it never lands in the public repo.
static/img/levels/
```
- **Why this does NOT regress the D9 audio allow-list:** the rule targets `static/img/levels/` specifically; `static/audio/` and `!static/audio/**/*.mp3` are untouched, so every committed `.mp3` stays tracked.
- **Why it does NOT hide the map/brand assets:** `static/img/horror/`, `static/img/light/`, `static/img/logo/` are siblings of `static/img/levels/`, not under it. The rule ignores only the `levels/` subtree, so `landing-map.v2.jpg`, `landing-map.v2.webp`, and the logo stay tracked. (`static/img/light/landing-map.png` design source is likewise unaffected.)
- **Placement matters:** put it as a NEW trailing block (after line 47's `!static/audio/**/*.mp3`) so the allow-list negations above never re-include `levels/`. A directory ignore (`static/img/levels/`) also covers `manifest.json` inside it — acceptable, since the manifest is build output and is regenerated every deploy. (If the manifest is ever wanted in-repo for a no-Drive-build, add `!static/img/levels/manifest.json` — NOT recommended, as it would couple the repo to a specific bake.)

## 12.10 Recommended defaults for open questions (BakeQ1–BakeQ6)
- **BakeQ1 (keep/drop proxy):** **KEEP** `/api/levels/{id}/media/{file_id}` as a guarded, non-default fallback (R1/R6 ACs intact); never the bulk path, so the 403 risk is gone. DROP is a clean one-line follow-up if SECURITY prefers a zero-proxy runtime.
- **BakeQ2 (missing/ bake + freshness model):** **BAKE** the `missing/` set into `static/img/levels/missing/`; the per-visit re-roll (R3) picks from the cached local list and emits a static URL. **PLUS (user-refined freshness):** add a **periodic, change-gated, background incremental sync** (§12.13) — build-bake is the cold-start floor; a `lifespan` `asyncio` task lists Drive metadata every `IMAGE_SYNC_INTERVAL_SECONDS` (default **1800**, `0`/unset DISABLES for hermetic CI/tests) and, **only when the `file_id` set changed**, paced-downloads the delta + atomically updates `manifest.json` + reloads the in-memory scope. So new/changed images appear **without a redeploy** and **without** per-request Drive calls (user traffic stays static/Drive-free). `POST /api/refresh` runs the same path for an on-demand (token-gated) force.
- **BakeQ3 (discovery source):** **build-written `manifest.json` as PRIMARY**, live Drive metadata as FALLBACK, empty gallery as last resort. Zero Drive calls on a normal cold start; works with no runtime creds.
- **BakeQ4 (build-failure policy):** **retry-with-backoff (2→32 s, 5 tries), then WARN + serve-partial** (paired with the kept proxy). Switches to **FAIL-the-build** iff BakeQ1 is later chosen as DROP.
- **BakeQ5 (filename/URL scheme):** **`static/img/levels/{id}/{PhotoRef.name}` verbatim** — filename == `PhotoRef.name` (`{n}.{i}.jpeg`), preserving the M11 caption key byte-for-byte. Hostile/colliding names are rejected/flagged loudly (§12.3), never silently mangled.
- **BakeQ6 (local-dev source):** **same `scripts/fetch_images.py`** with a local `.env`; graceful states when unbaked (proxy URLs while the proxy is kept, else empty/placeholder). Onboarding stays "set `.env`, run `uvicorn`," bake optional for parity.

## 12.11 Technical risks / flags for PM (M12) — R-Bake1…R-Bake8
- **R-Bake1 (build still trips the 403):** **Core risk → §12.2/§12.3 pacing** — concurrency 2, 0.4 s jittered delay, exp-backoff retry on 403/429. Only `alt=media` is throttled; metadata discovery is not. QA/PM verify a clean bake of the 52-image set and measure duration (R-Bake5). If 403 persists at concurrency 2, drop to 1 and lengthen the delay.
- **R-Bake2 (photos leak into git):** **§12.9 explicit ignore** for `static/img/levels/`, added in the same change; SECURITY (B6) confirms no photo is staged/committed and the D9 audio allow-list + map/brand assets are intact.
- **R-Bake3 (caption breakage):** **§12.3 hard gate** — baked filename == `PhotoRef.name`; QA asserts all 104 captions still attach after the URL switch.
- **R-Bake4 (secret exposure):** **§12.7 hard gate** — `GD_API_KEY` build/server-side only; manifest/payload/static output carry only `file_id`+`name` (already client-visible). SECURITY veto.
- **R-Bake5 (Render build limits):** **Verify at execution** — measure paced bake duration for 52 images; tune concurrency/delay if near a build timeout; small set + "won't add many more" makes this low.
- **R-Bake6 (stale images without redeploy):** **RESOLVED by §12.13 (no longer redeploy-only)** — the periodic background change-gated sync pulls new/changed images within ~30 min (or immediately via `POST /api/refresh`) without a redeploy, paced so it never bursts. The build-bake remains the cold-start floor. (Prior "redeploy-only; `/api/refresh` never downloads" stance is superseded; `/api/refresh` now triggers an immediate sync — §12.13.5.)
- **R-Bake7 (test fragility):** **§12.3 note** — tests that hard-assert the proxy `url` value must move to the static scheme; assert the `url` shape/prefix (`/static/img/levels/{id}/`) tolerantly, not the exact proxy path. Cross-check `tests/test_backend.py` / `tests/test_cache.py` / `tests/test_captions.py`.
- **R-Bake8 (background sync adds runtime Drive metadata calls + must be hermetic in tests):** the §12.13 sync introduces runtime Drive activity that the pure build-bake did not — (a) a cheap **metadata** `files.list` every `IMAGE_SYNC_INTERVAL_SECONDS` (~30 min; not throttled, so cheap, but note it; user traffic stays Drive-free), and (b) paced `alt=media` delta downloads only on a change. **Mitigations:** the interval env defaults to 1800 but **MUST be `0` (disabled) in local/CI/pytest** so the suite stays hermetic and never polls Drive (the task is not even created at `0`/unset); the metadata-only change-gate guarantees zero downloads on the common no-change tick; the paced downloader + single-flight lock + catch-all prevent bursts/overlap/crashes; and the runtime now needs `GD_API_KEY`/`GD_ROOT_FOLDER` (already set in Render, no new exposure — §12.7/§12.13.6). **Flag to SECURITY** for the data-flow review (runtime now makes outbound Drive calls + holds the key live; the on-demand sync rides the token-gated `/api/refresh`).

## 12.12 Diff surface for M12 (what changes)
1. **`scripts/fetch_images.py`** (NEW) — the paced build-time bake script + manifest writer (§12.2). Reuses `drive_service` discovery.
2. **`app/drive_service.py`** — add a tolerant `manifest.json` loader feeding the existing `DiscoveryCache` shape, with live-metadata fallback (§12.4). `resolve_media` + byte LRU KEPT (BakeQ1) as a guarded fallback. **Factor the paced downloader** (concurrency/jitter/backoff, §12.3) so both `scripts/fetch_images.py` and the §12.13 background sync reuse one implementation (NF-Bake7).
3. **`app/main.py`** — `_ref` emits the static `url` (file_id + name preserved); optional baked-vs-proxy URL selection for un-baked local dev (§12.8). `lifespan` starts/cancels the **periodic background sync `asyncio` task** (§12.13) when `IMAGE_SYNC_INTERVAL_SECONDS > 0`. `POST /api/refresh` re-reads the manifest/captions AND triggers an **immediate sync** via the same single-flight code path (§12.13.5).
4. **`render.yaml`** — `buildCommand` adds `&& python scripts/fetch_images.py` (coordinate with M8's region edit — §12.8). Runtime env already carries `GD_API_KEY`/`GD_ROOT_FOLDER` (§12.13.6, no new secret); optionally surface `IMAGE_SYNC_INTERVAL_SECONDS` (default 1800; set `0` for any non-Render/CI env to disable polling).
5. **`.gitignore`** — explicit `static/img/levels/` ignore (§12.9); the background sync writes into this same ignored dir, so no new ignore rule is needed.
6. **`static/img/levels/`** (build output + sync target, GIT-IGNORED) — baked images + `manifest.json`, updated in place by the background sync.
7. **Tests/CI** — `IMAGE_SYNC_INTERVAL_SECONDS` unset/`0` in the suite so the sync task is never created (hermetic — R-Bake8); QA may unit-test the change-gate + delta logic with a mocked Drive directly, not via the live loop.
8. **Docs** — this §12 + README bake/local-dev/freshness notes (background sync + the env flag); QA updates URL assertions tolerantly.

**Untouched:** `app/captions.json` / `app/captions.py` (caption key preserved), both landing maps (§8/§9), the audio engine, prefetch, theme isolation, M8's `/api/refresh` token-gate + region edit (independent), and all routes other than the `_ref` `url` value (+ the optional proxy keep/drop).

## 12.13 Periodic background image sync — RESOLVES BakeQ2 (refined: freshness without redeploy)

**Decision (BakeQ2, user-refined):** keep build-time bake as the **cold-start floor**, and ADD a periodic, change-gated, background **incremental sync** so new/changed images appear **without a redeploy** — and **without** per-request Drive calls and **without** the burst that trips the 403. Verbatim user intent: *"we can use a list every half an hour — if count changes then only refresh in background."* This supersedes R-Bake6's "redeploy-only" stance (see updated R-Bake6 + new R-Bake8); the build-bake / static-serving / caption-key / manifest decisions (§12.2–§12.9) are **unchanged** — the sync only writes into the SAME `static/img/levels/` layout and updates the SAME `manifest.json`.

**1. Trigger / loop (lifespan-owned background task).** A single `asyncio` background task is started in the FastAPI `lifespan` startup, alongside the existing discovery + caption load, and cancelled cleanly on `lifespan` shutdown. The loop:
- Sleeps an **initial delay** (e.g. ~60 s) before its first tick so it never competes with cold-start discovery/caption-load/first-request warmup (the build-baked set already covers t=0).
- Then ticks every `IMAGE_SYNC_INTERVAL_SECONDS` (env, default **1800** = 30 min). **`0` or unset DISABLES the task entirely** — the task is never created, so local dev, CI, and the pytest suite never poll Drive (hermetic; see §12.13.4 + R-Bake8). This mirrors the `os.environ.get(...)`-with-default discipline already used for config in `drive_service`.
- The interval/initial-delay are the only new config; no new route, no new payload field.

**2. Change detection (cheap, metadata-only — the "list every half hour").** Each tick runs the **metadata path ONLY** — `discover_levels(force=True)` + the per-level `files.list` it already performs — which is **not** the throttled endpoint (§12.1: only `files.get?alt=media` bursts trip the 403). From that it computes the **current discovered set**: `level → {file_id…}` for every available level, plus the `missing/` set. It compares against the currently-loaded **`manifest.json`** scope:
- **Signal (recommended):** compare the **set of `file_id`s per level** (and for `missing/`). This is robust to swaps/replacements where the count is unchanged but an image was replaced. The user's "if count changes" is honored as a **fast pre-check**: if the per-level counts AND the `missing/` count all match, short-circuit to the set comparison (usually also equal → no-op); a count delta is a definite change. Net: **count delta OR set delta ⇒ changed; otherwise no-op (zero downloads).**
- An **unchanged** tick does nothing but the cheap metadata list — no `alt=media`, no disk writes, no manifest rewrite, no in-memory reload.

**3. Delta download (paced, background, atomic).** Only on a detected change:
- Compute the delta: `added/changed ids = current − manifest`, `removed ids = manifest − current` (per level + `missing/`).
- Download ONLY the added/changed `file_id`s using the **SAME paced downloader** as `scripts/fetch_images.py` (§12.2/§12.3: concurrency ≈ 2, 0.4 s ±20% jittered inter-request delay, exponential backoff 2→32 s on 403/429/5xx, bounded retry budget). So even a sync NEVER bursts — it is the build pacing applied incrementally, on a handful of files at a time. (Design intent: the paced downloader is factored so both the build script and the runtime sync call one implementation — NF-Bake7's "one source of truth" extended to the sync; no second downloader.)
- **Never serve a half-written file:** download each file to a temp name in the target dir, then atomically `rename` into `static/img/levels/{id}/{name}` (or `missing/{name}`) on success. A failed/throttled file leaves the previous file (if any) untouched and is retried next interval.
- **Remove deleted ids:** unlink the static files for `removed ids` after the manifest swap (so a reader never sees a manifest entry whose file was just deleted).
- **Atomic manifest update + in-memory reload:** write the new `manifest.json` to a temp file and `rename` over the old one, then reload the in-memory discovery/caption scope (the SAME loader path used at `lifespan` startup and by `POST /api/refresh`, §12.4) so `/api/levels` and `/api/levels/{id}/photos` immediately reflect the new set. Captions are re-read on the same reload (a new image simply has no caption until `captions.json` is updated — CapQ6 behavior, no error).

**4. Safety / robustness (the task must NEVER crash the app).**
- **Single-flight lock:** an `asyncio.Lock` (or a "sync in progress" flag) prevents overlapping ticks AND overlap with a `/api/refresh`-triggered sync (§12.13.5). If a tick is somehow still running when the next fires, the new tick skips (logs "sync still running, skipping").
- **Catch-all per tick:** the entire tick body is wrapped so ANY exception (Drive 403/429 on the delta downloads, network error, malformed metadata, disk error) is **caught + logged (status/shape only, never the key — §12.7) and swallowed**; the loop then sleeps and retries next interval. A 403 on the delta leaves existing files + the existing manifest intact and tries again later — never a partial/corrupt manifest, never a crashed event loop.
- **Failure floor:** the build-baked set (+ last good synced state) is always the floor; a sync can only ADD freshness, never degrade below the cold-start set. On **Render free spin-down**, the task pauses with the instance and resumes on wake (the next tick after wake does a cheap list; the build-baked set covers the cold start) — no special handling needed.

**5. Relationship to `POST /api/refresh`.** `/api/refresh` triggers an **immediate** sync via the **same code path** (acquire the single-flight lock → metadata list → change-gate → paced delta download → atomic manifest swap → in-memory reload) IN ADDITION TO re-reading the manifest + captions it already does (§12.4). So the user can **force** an update on demand instead of waiting for the next 30-min tick. Because it shares the single-flight lock, a manual refresh and a scheduled tick never collide. **Coupling note:** `/api/refresh` is slated to be **token-gated** (M8 / R-D6); the on-demand sync therefore rides that same protected, authenticated endpoint — an anonymous caller cannot trigger Drive downloads. (If `IMAGE_SYNC_INTERVAL_SECONDS=0` disables the periodic loop, `/api/refresh` can still perform a one-shot sync on demand, since it is an explicit operator action, not a poll — recommended behavior; document it.)

**6. Runtime-credentials implication (data-flow change vs a pure build-bake).** A pure build-bake needs `GD_API_KEY` / `GD_ROOT_FOLDER` only at **build** time. The background sync means the **RUNTIME also needs** `GD_API_KEY` / `GD_ROOT_FOLDER` (already set in Render as `sync:false` env, §12.8 — no new secret, no new exposure surface; the key still NEVER leaves the server and is NEVER written to the manifest/payload/static output, §12.7). Crucially, this does **not** reintroduce per-request Drive traffic: **user-facing requests still serve plain static files (Drive-free)**; the only runtime Drive calls are (a) the cheap periodic **metadata** list and (b) the **paced delta downloads that happen only when the set changed**. The §12 data-flow is therefore: *build-bake (floor) → static serving for all user traffic → background metadata poll every 30 min → paced incremental download + manifest/scope reload only on change.*

### 12.13 summary
Build-bake remains the cold-start floor; a `lifespan`-owned `asyncio` task lists Drive metadata every `IMAGE_SYNC_INTERVAL_SECONDS` (default 1800, **0/unset disables** for hermetic local/CI/tests), change-gates on the **per-level `file_id` set** (count as a fast pre-check), and on a change only, paced-downloads the delta into the static dir + atomically swaps `manifest.json` and reloads the in-memory discovery/caption scope. It is single-flight, crash-proof (catch-all → retry next interval), and `POST /api/refresh` runs the same path for an on-demand, token-gated force. No per-request Drive calls are added; static serving stays Drive-free. **No change to the build-bake, static-serving, manifest-PRIMARY, or `(level, filename)` caption-key decisions (§12.2–§12.9) — the sync writes into the SAME layout/manifest and reuses the SAME paced downloader + loader.**

> **⚠️ §12 entirely superseded by §13 (M13, 2026-06-09).** The Drive build-bake, the `static/img/levels/` + `manifest.json` layout, the manifest-PRIMARY discovery, the kept `/media` proxy, and the periodic **download** sync above are all replaced by Cloudinary. The periodic task survives in spirit as a metadata-only **Admin re-list** (no byte download); everything else in §12 is historical. The Drive `alt=media` throttle that §12 worked around is moot — there is no per-request external byte fetch.

---

# 13. Cloudinary source (as-built) — M13

> Supersedes the Drive parts of §2/§3/§4/§5 and the **whole of §12 (M12 Drive build-bake)** and the **M9/M12 Drive-bake** references. The image source is now Cloudinary; there is no Drive client, no proxy, no build-bake, no `static/img/levels/`.

## 13.1 Module
`app/cloudinary_service.py` replaces `app/drive_service.py` (deleted). It owns discovery, the in-process cache, the keyless CDN URL builder, and the missing-fallback pool. `scripts/fetch_images.py` (M12 bake) is deleted; `scripts/` is removed.

## 13.2 Discovery (one Admin API list, metadata only)
- `_parse_cloudinary_url()` reads `CLOUDINARY_URL` (`cloudinary://<api_key>:<api_secret>@<cloud_name>`); a missing/malformed value returns `None` → graceful empty-gallery degrade (never raises).
- `discover()` makes one **paginated** Cloudinary **Admin API** list of `resources/image` (HTTP basic auth with `api_key:api_secret`, server-side only) and groups by `asset_folder`: `all ages/{N}` → level N, `all ages/missing` → fallback pool; resources outside `all ages/` are ignored. Result cached in `DiscoveryCache` (`get_cache()`).
- A `lifespan` background task re-runs `discover()` every `IMAGE_SYNC_INTERVAL_SECONDS` (default 1800; **0/unset disables** → hermetic local/CI) and atomically swaps the cache; `POST /api/refresh` forces an immediate re-list. This is **metadata only — no byte download** (so the §12 throttle/pacing machinery is gone).

## 13.3 Keyless delivery
Each `ImageRef` carries `file_id` (= Cloudinary `public_id`), `filename_stem` (= `public_id` with Cloudinary's random `_xxxxxx` suffix stripped — the caption key, §13.4), and an absolute `url`:
```
https://res.cloudinary.com/{cloud}/image/upload/f_auto,q_auto/{public_id}.{fmt}
```
`f_auto,q_auto` = free automatic format + quality. The browser loads bytes straight from Cloudinary's CDN; the app is never on the byte path and the `api_secret` never appears in the URL, payload, or logs.

## 13.4 Caption key = filename stem
M11 captions are still keyed by filename, but the key is the **stem** (`app/captions.json` / `app/captions.py`). Cloudinary derives a `public_id` like `15.1_gpoksj`; `_filename_stem()` strips the random suffix back to `15.1`, which equals the original `{n}.{i}` base, so all captions keep matching. `original_filename` comes back null from the Admin API (verified live), so the stem is derived from `public_id`.

## 13.5 Endpoints / payload (as-built)
- `/api/levels/{id}/media/{file_id}` and `resolve_media` are **removed**.
- `/api/levels/{id}/photos` returns each image as `{ "file_id": "<public_id>", "url": "<keyless CDN url>", "caption"?: {...} }`; `available`/`fallback_audio` semantics unchanged (missing-level audio still a local per-theme track, §11). `file_id` is now the `public_id`.

## 13.6 Config + deploy
- `CLOUDINARY_URL` (secret) replaces `GD_API_KEY` + `GD_ROOT_FOLDER`; `IMAGE_SYNC_INTERVAL_SECONDS` retained. `render.yaml` `buildCommand` is just `pip install -r requirements.txt` (no bake); region `singapore`. No Drive folder-sharing precondition. M8 deploy now needs only `CLOUDINARY_URL`.

## 13.7 Tests
Hermetic suite **163 passed**: the Cloudinary Admin API is mocked in `tests/conftest.py`; `tests/test_cloudinary.py` added; `tests/test_cache.py` + `tests/test_m12_bake_manifest.py` deleted; `tests/test_backend.py` / `tests/test_captions.py` converted. No network, no real secret.
