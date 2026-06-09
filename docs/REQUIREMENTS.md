# Requirements — Archive 19: Dual-Atmosphere Dynamic Gallery

Status: **Discovery COMPLETE — design approved, asset reality confirmed (§7).** Supersedes the original single-theme blueprint. Build proceeds with placeholders (§8). **M8 — Deploy: host CHOSEN — Render (D13); HostQ1 RESOLVED. Remaining open Qs = cold-start tolerance, domain, /api/refresh auth, Drive-sharing confirm, traffic/region (HostQ2–Q5 + R-D6) — these shape but do not block the Render deploy. Requirements in §12.** **M10 — Sea (Light) landing map: BUILT, SECURITY-APPROVED, QA-VERIFIED (140 passed) — pending commit; see §10 (frontend-only; replaced the Sea island grid with a full-bleed archipelago map + hotspots; Horror untouched). Prior: Horror Atmosphere Redesign §9 (M9, shipped). After M9+M10, both themes are map-based.**

## 1. Vision
An interactive web app with a **variable** number of levels (0 → up to 18) presented through **two distinct, toggleable realities**. The chosen theme persists across the whole session and is switchable from any page.

## 2. The two themes
| | THEME A — Horror | THEME B — Sea & Island |
|---|---|---|
| Persona | Haunted Gothic Corridor; levels are "Doors/Rooms" along an eerie hallway | Sunlit Archipelago Map; levels are "Islands" across an open ocean |
| Palette | `#0D0D0D` charcoal obsidian + `#FFB000` molten amber, shadowed vignette | `#E0F2FE` / `#0284C7` azures + warm sand, white coral, palm green |
| Audio (landing) | Continuous atmospheric horror soundtrack | Bright relaxing ocean/acoustic ambient |
| Level UI feel | Stepping inside a dark, confined room | Stepping onto a sunny open beach |

## 3. Functional requirements
| # | Requirement | Priority |
|---|---|---|
| F1 | Both themes render a fixed illustrated **landing map** of 19 %-positioned clickable hotspots (Horror = haunted map §9, Sea = archipelago map §10). Dynamic discovery (whatever levels are configured: 5, 12, 19…) drives each hotspot's **availability/sealed styling**, not the layout. *(History: the original landing was a dynamically-sized grid; both themes were converted to fixed maps in M9/M10 — see §9/§10.)* | Must |
| F2 | Global theme toggle reachable on **every** page view. | Must |
| F3 | Theme selection persists for the session (cookie + `sessionStorage` — see D1). | Must |
| F4 | Clicking a level navigates to a dedicated **`/level/{id}`** page (`level.html`). | Must |
| F5 | The active theme dictates how the level page is presented (room vs beach). | Must |
| F6 | Landing page plays the theme's **global ambient** track. | Must |
| F7 | Entering a level **crossfades**: wind down global ambient, scale up that level's track. | Must |
| F8 | Images per level fetched from numbered Google Drive subfolders, proxied as bytes (D2). | Must |
| F9 | **Missing-level fallback:** if a numbered folder is absent (or present-but-empty), pull 1 random **image** from the Drive `missing/` folder (proxied through the backend). The fallback **audio** is a random **local per-theme track** from `static/audio/{theme}/` chosen client-side — NOT from Drive — so the `missing/` folder only needs images and a missing level never fails over absent audio. *(History: originally the audio also came from the Drive `missing/` folder; changed 2026-06-09 — see §11.)* | Must |
| F10 | Browser never receives the Google Drive API key. | Must |
| F11 | Responsive layout for both theme landing maps (haunted / archipelago) — scale-to-fit on desktop, pan-to-fit on mobile (§9/§10). | Should |

## 4. Non-functional
- **Frontend:** Semantic HTML5, Tailwind CDN + custom `style.css` (`.theme-horror` / `.theme-sea` utility classes), native `<audio>`.
- **Backend:** FastAPI + Uvicorn + Jinja2 + `httpx`.
- **Security:** `GD_API_KEY` only from `os.environ`; `.env` git-ignored; per-file audit.
- **Hosting:** Render/Railway free tier, secrets via env vars.

## 5. Decisions (locked in Discovery)
- **D1 — Theme persistence:** ✅ **Cookie + sessionStorage.** SSR reads the cookie to render the correct theme on first paint (no flash); client JS mirrors to `sessionStorage`.
- **D2 — Image delivery:** ✅ Backend **proxies image bytes**; Drive folders may stay private.
- **D3 — Default theme:** ✅ **Horror** for first-time visitors with no saved choice.
- **D4 — Level model:** ✅ **Dedicated page per level** at `/level/{id}` (`level.html`).
- **D5 — Level set:** ✅ All 19 (0–18), numbered Drive folders; dynamic scaling so missing numbers are allowed.
- **D6 — Missing handling:** ✅ Absent numbered folder → random **image** from the Drive `missing/` folder, proxied through the backend. *(Superseded 2026-06-09 — §11: the fallback **audio** is now a random LOCAL per-theme track, not from Drive.)*
- **D7 — Level metadata:** ✅ Number only (no titles/descriptions).
- **D8 — Access:** ✅ Public, no auth.
- **D9 — Asset split:** ✅ **Images in Google Drive; all audio in the GitHub repo** (`static/audio/`). The **missing-level fallback** image comes from the Drive `missing/` folder; its audio is a random LOCAL per-theme track *(updated 2026-06-09 — §11; was previously Drive `missing/` audio)*.
- **D12 — Drive access:** ✅ The `all ages` parent folder is shared **"Anyone with the link → Viewer"**, so the plain `GD_API_KEY` can read it. No service account needed.
- **D10 — Drive config:** ✅ A single **parent** Drive folder (one link/ID in `GD_ROOT_FOLDER`) whose children are the numbered subfolders `0..18` + `missing/`. Backend lists the parent's children to discover which levels exist → dynamic scaling.
- **D13 — Hosting (M8):** ✅ **Render free web service** — via the committed `render.yaml` Blueprint (zero new code/config). Resolves **HostQ1**: KEEP the FastAPI Drive-proxy + in-memory-cache architecture on a persistent web-service host. **Fly.io** (Fallback A) and **Hugging Face Spaces** (Fallback B) remain documented alternatives (ARCHITECTURE §10.3); **Vercel** (serverless rework) and **GitHub Pages** (static-only, would expose the secret) are rejected. *User-decided 2026-06-09.* Remaining open Qs (HostQ2–HostQ5 + R-D6) shape the deploy but do not block starting it.
- **D11 — Per-theme level tracks:** ✅ Horror and Sea each have their **own** per-level tracks (`static/audio/horror/`, `static/audio/sea/`). The missing-level fallback audio is a random track drawn from the **active theme's** local set *(updated 2026-06-09 — §11; previously it came from the Drive `missing/` folder)*.

## 6. Configuration variables
- `GD_API_KEY` — **secret**, never committed; read via `os.environ`.
- `GD_ROOT_FOLDER` — the parent Drive folder ID/link (data, not secret); shipped as a fill-in in `.env.example`.

## 7. Confirmed asset reality
- Parent folder `all ages` (renameable) contains numbered subfolders. **Present:** `1, 2, 8–18`. **Absent:** `0, 3–7` → exercise the missing fallback. Images named `{n}.{i}.jpeg`.

## 8. Status: Discovery COMPLETE ✅
All design questions resolved. Build proceeds with **placeholders**:
- `GD_ROOT_FOLDER` ships as a fill-in stub in `.env.example`; user pastes the real `all ages` link locally.
- Audio tree ships with stub `.mp3` placeholders; user drops real files later.
- Drive access = public link (`GD_API_KEY`), `missing/` folder holds stock images + audio.

Phase 2 (`orchestrate-build`) is unblocked.

---

## 9. Horror Atmosphere Redesign (change request — 2026-06-08)

Status: **Discovery in progress.** Scope is a **visual-only restyle of the HORROR theme**; the app is built and working (M1–M7 done). No backend, route, payload, audio, or data-flow changes. **The Sea & Island theme is explicitly out of scope and must remain byte-for-byte unchanged.** All locked decisions D1–D12 and risk resolutions R1–R6 are preserved.

### 9.1 Intent (verbatim user request)
Replace the current plain/near-black Horror landing with a **cinematic haunted-corridor atmosphere**, and likewise give each per-level ("inside a door") page a **horror background instead of black**.

### 9.2 Target aesthetic (reference, "like this, not identical")
A dark haunted corridor at night with:
- Deep **navy/blue** palette (NOT pure black).
- A glowing pale-blue **moonlit doorway/window** at the far center (focal vanishing point).
- A cloaked, hooded **figure** silhouetted in the center, facing the moonlit door.
- **Doors receding** along both side walls in perspective.
- Shadowy **clawed hands** reaching in from the left and right edges.
- Low-lying **fog/mist** drifting along the floor.
- Illustrated / vector, cinematic, eerie.

### 9.3 Functional requirements

> **⚠️ Superseded by the shipped design (2026-06-09).** The Horror landing was redesigned beyond a restyle: the door grid is **replaced** for the Horror theme by a full-bleed illustrated haunted map (`static/img/horror/landing-map.v2.jpg`) whose 19 locations are %-positioned clickable hotspots to `/level/{id}`. This means **HR1** (the landing is now a raster map, not a CSS-only corridor field), **HR3** (the door grid does *not* stay intact for Horror — it is superseded by the map; the Sea grid is unchanged), and **HR4/HQ1** (a raster asset is now used, not pure CSS/SVG) no longer hold as written. The decorative silhouettes/fog (HR5–HR8) and the per-level horror scene (HR2) shipped as specified. The Sea theme is untouched.

| # | Requirement | Priority |
|---|---|---|
| HR1 | Horror **landing** (`index.html`) renders a cinematic haunted-corridor BACKGROUND replacing the flat near-black field, in a navy/blue palette with a central moonlit focal point. | Must |
| HR2 | Horror **per-level** page (`level.html`) renders a horror ambiance background behind the room/slideshow stage, replacing the plain dark background. | Must |
| HR3 | The existing **door grid layout and ALL functionality stay intact** — tile links, `/level/{id}` navigation, theme toggle, slideshow, audio crossfade, prefetch. Redesign is restyle + atmosphere only. | Must |
| HR4 | The atmosphere is delivered through the **existing theme injection points** (`.atmosphere` overlay div + `--page-bg-image` / `--vignette` custom properties, scoped to `.theme-horror`), so the SSR cookie→`.theme-*` mechanism is untouched. | Must |
| HR5 | Decorative atmosphere is **non-interactive**: it sits behind content (`.atmosphere` is already `pointer-events:none; z-index:0`; content rides `.layer` at `z-index:1`) and never intercepts clicks/focus or obscures the level number/label/slideshow. | Must |
| HR6 | Foreground contrast preserved: amber accents, level numbers/labels, and slideshow images remain legible against the new background (vignette/scrim as needed). | Must |
| HR7 | Decorative-element scope (moonlit door, cloaked figure, clawed hands, fog) vs. pure ambient gradient/fog is a **decision** — see Open Questions Q2; minimum bar is HR1/HR2 (navy field + moonlit focal + vignette). | Should |
| HR8 | Optional ambient **motion** (drifting fog / faint flicker) — a decision (Open Questions Q4); if included it MUST be disabled under `prefers-reduced-motion`. | Could |

### 9.4 Non-functional requirements
- **NF-HR1 — No performance regression.** Must not regress the existing caching/prefetch/eager-preload work (index.html idle prefetch, level.html eager slide preload, backend long-lived `Cache-Control`). Any background **image asset(s)** must be appropriately sized/compressed, lazy/idle-decoded where possible, and must not block first paint or the landing ambient audio start. Prefer CSS/SVG that adds negligible bytes; cap any raster asset budget (see Q1).
- **NF-HR2 — Accessibility.** Respect `prefers-reduced-motion` (existing global block at style.css:467 must keep working for any new animation). Decorative layers are `aria-hidden`. Maintain WCAG-adequate text/icon contrast against the new navy field (HR6).
- **NF-HR3 — Responsiveness.** Atmosphere must read correctly across breakpoints (mobile → desktop) without horizontal scroll, letterboxing, or focal-point loss; `background-size`/positioning chosen to degrade gracefully on portrait phones.
- **NF-HR4 — Theme isolation.** All new styles scoped under `.theme-horror` selectors (or horror-only template branches). `.theme-sea` tokens, `--page-bg-image`, island tiles, and beach stage MUST be unaffected. No edits to shared neutrals in `:root` that would bleed into Sea.
- **NF-HR5 — Layout/functionality preservation.** No change to the door-grid structure, tile markup contract, routes, JS behavior, payloads, or audio. Diff is restricted to `.theme-horror` CSS, horror-scoped template decoration, and (if Q1 chooses an asset) new files under `static/`.
- **NF-HR6 — Maintainability.** Continue using CSS custom properties + the `.atmosphere` overlay pattern already established; document any new tokens and any committed asset's source/license.

### 9.5 Out of scope (explicit)
- Sea & Island theme (any file path serving it), backend/`drive_service.py`/`main.py`, routes, payload schemas, audio engine, Drive/missing-fallback logic, deployment config. None change.

---

## 10. M10 — Sea (Light) landing map (change request — 2026-06-09)

Status: **BUILT — SECURITY-APPROVED (S6) + QA-VERIFIED (S7, full suite 140 passed / 0 failed); pending commit (PM S8, doc sync done).** Design approved (ARCHITECTURE §9), all open questions resolved via user sign-off (2026-06-09). Scope was a **frontend-only redesign of the SEA & ISLAND (light) theme landing**, mirroring M9's Horror treatment: the dynamic island GRID was replaced with a full-bleed illustrated **archipelago map** (`static/img/light/landing-map.v2.webp`, 214 KB WebP, under the ≤400 KB budget; `landing-map.png` retained as design source only) whose 19 numbered island locations are %-positioned clickable hotspots → `/level/{id}`. **The HORROR theme stayed byte-for-byte unchanged.** No backend, route, payload, audio, data-flow, or deploy changes. All locked decisions D1–D12, risk resolutions R1–R6, and the shipped M9 design are preserved. After M10, **both themes are map-based** (Horror map untouched; Sea grid superseded by its own map).

> **SR1 firmed (architect default, §9.5):** "replaces the dynamic island grid" is now read **literally** — the Sea grid markup is **deleted**, with **no mobile grid fallback** (pan-to-fit is used on mobile instead). This closes R-S6. **Confirmed by user sign-off (2026-06-09): no mobile grid fallback.**

### 10.1 Intent (verbatim user request)
"Similar to dark mode (Horror), we need a detailed design for **light mode** as well. Refer to the image at `static/img/light/landing-map.png`." → Give the Sea & Island (light) theme the **same full-bleed illustrated map + clickable hotspots** treatment M9 gave Horror, using the supplied archipelago art.

### 10.2 Reference art (`static/img/light/landing-map.png`)
An illustrated fantasy **archipelago** titled "TOUR-DE-ANSHIKA": sunlit sky, **19 numbered island locations** connected by bridges, each with a painted NAME — `0 RUIN · 1 GATE · 2 WITCH'S HUT · 3 MAUSOLEUM · 4 ECHOED ABYSS · 5 PRISON · 6 GRAVEYARD · 7 HALLO · 8 SUNKEN TEMPLE · 9 FORBIDDEN · 10 CAVERN · 11 SEPULCHER · 12 WATCH TOWER · 13 PIT · 14 FINAL KEEP · 15 HAUNTED TOWER · 16 CURSED ORCHARD · 17 DRAGON'S DEW · 18 FORGOTTEN MEMORY`. A theme-toggle pill is **painted into the art top-right** (decorative; the real interactive overlay toggle sits on top of it). The island layout differs from the Horror map, so hotspot coords must be calibrated against THIS art. **Byte note:** the file is a **2.7 MB PNG**; the Horror map shipped as a **640 KB JPG** — image optimization is an Open Question (SQ2).

### 10.3 Functional requirements

| # | Requirement | Priority |
|---|---|---|
| SR1 | Sea **landing** (`index.html`, the `{% else %}` / Sea branch) renders a full-bleed illustrated **archipelago map** that **replaces** the dynamic island grid for the Sea theme. The Horror map branch is untouched. After this change both themes are map-based. | Must |
| SR2 | The art is delivered as a single full-bleed `<img>` (analog of `.horror-map-img`) inside a Sea map container, filling the viewport like the Horror map. | Must |
| SR3 | **All 19 locations (0–18)** are rendered as %-positioned clickable hotspot anchors → `/level/{id}`, regardless of discovery (the grid of hotspots is hardcoded, mirroring Horror). | Must |
| SR4 | Hotspot **coordinates are calibrated against THIS art** (the archipelago island layout, NOT the Horror map's `coords`) using the existing `?calibrate` aid. | Must |
| SR5 | Unavailable levels (id ∉ discovered `available_ids`) receive **"sealed/sunken"** styling, mirroring Horror's `.is-sealed` (Sea-appropriate visual, e.g. submerged/dimmed island). Hotspot still navigates to `/level/{id}` (which serves the missing fallback). | Must |
| SR6 | The **global theme toggle** is present and overlaid on the map (present on every page, per F2), positioned to **not clash with the painted toggle pill** in the art's top-right. | Must |
| SR7 | Hotspots are **keyboard-focusable** with descriptive `aria-label`s; the painted location NAMES SHOULD be exposed where decided (see SQ3, e.g. `aria-label="Level 5 — Prison"`). Decorative layers (map art, any ambient decoration, painted-pill region) are `aria-hidden` + `pointer-events:none`. | Must |
| SR8 | A landing heading remains available to assistive tech (`sr-only` `<h1>`, mirroring the Horror landing). | Must |
| SR9 | Optional Sea ambient decoration (drifting boats/gulls/clouds, analog of the Horror drifting ghosts) — a **decision** (SQ4); if included it MUST be inert/`aria-hidden` and disabled under `prefers-reduced-motion`. | Could |

### 10.4 Non-functional requirements
- **NF-SR1 — Image byte budget / performance.** The supplied **2.7 MB PNG must be optimized** before ship. Target ≤ **300–600 KB** via WebP or progressive JPEG (PNG only retained if it can hit budget, which is unlikely for a photographic illustration). Use `fetchpriority="high"` + `decoding="async"` on the map `<img>` (mirroring Horror). Must not regress the existing caching/idle-prefetch path (prefetch logic unchanged). Image must not block the landing ambient audio start.
- **NF-SR2 — Accessibility.** Hotspots keyboard-focusable in DOM order with visible focus state and `aria-label`s (SR7). Decorative layers `aria-hidden` + `pointer-events:none`. `prefers-reduced-motion` honored for any ambient motion (reuse the existing global block at `style.css`). Maintain WCAG AA contrast for hotspot rings/ids/focus indicators against the bright sunlit art.
- **NF-SR3 — Responsiveness.** The art is **wide/landscape**; the map must read correctly mobile → desktop without focal-point loss. Small-screen behavior (scroll/pan vs scale-to-fit vs grid fallback under a breakpoint) is an **Open Question (SQ5)**.
- **NF-SR4 — Theme isolation (hard gate).** The **Horror landing must be byte-unchanged** (`static/img/horror/landing-map.v2.jpg`, `.horror-*` CSS, the Horror template branch, its `coords`). If shared map machinery is introduced (SQ1), it MUST NOT regress Horror visuals/behavior. No edits to shared `:root` neutrals that would bleed across themes.
- **NF-SR5 — Layout/functionality preservation.** No change to routes, `/level/{id}` navigation, the slideshow, audio crossfade engine, prefetch, payloads, or backend. Diff restricted to the Sea branch of `index.html`, Sea-scoped (or shared, per SQ1) CSS in `static/style.css`, and the optimized image asset under `static/img/light/`.
- **NF-SR6 — Maintainability.** Reuse the established Horror map patterns (map container + `<img>` + `%`-positioned hotspot anchors + `?calibrate` aid) so both themes share a consistent mental model. Document the class strategy chosen (SQ1) and the image asset's source/license + optimization origin.

### 10.5 Open questions (SQ — RESOLVED in ARCHITECTURE §9; LOCKED status below)
| # | Question | Resolution (ARCHITECTURE §9.8) |
|---|---|---|
| SQ1 | **Class strategy:** refactor the Horror map machinery into a **shared, theme-neutral component** (e.g. `.theme-map` / `.map-hotspot` reused by both themes) vs **duplicate Sea-scoped classes** (`.sea-map` / `.sea-map-img` …)? Tension: DRY vs the "Sea untouched / theme-isolated" / "Horror byte-unchanged" principle (NF-SR4). `.map-hotspot` is **already shared** in the Horror markup. | **LOCKED (architect, §9.2):** reuse the already-shared `.map-hotspot`/`.map-hotspot-ring`/`.map-hotspot-id`/`.is-sealed` **leaf** classes for both themes; add Sea-scoped **container** classes (`.sea-landing`/`.sea-map`/`.sea-map-img`/`.sea-map-hotspots`/`.sea-map-toggle`) under `.theme-sea`. **NO shared Jinja macro, NO Horror rename** (protects NF-SR4). No user input needed unless they want full DRY (reopens R-S1). |
| SQ2 | **Image format/budget:** optimize the 2.7 MB PNG to **WebP** or **progressive JPEG**? Target size (≤300–600 KB)? Keep PNG only if it meets budget? | **LOCKED (architect, §9.4):** ship single **WebP** `static/img/light/landing-map.v2.webp`, q≈80, ~1600px wide, **≤400 KB** (hard ceiling 600 KB). The 2.7 MB PNG must **not** ship as-is. Progressive JPEG is the only-if-needed alternative. No user input needed. |
| SQ3 | **Hotspot labels:** expose the painted location NAMES (Prison, Graveyard…) in hotspot UI and/or `aria-label` (e.g. "Level 5 — Prison"), or numbers-only like Horror? If names: a single source-of-truth name map is needed (template dict). | **LOCKED-with-default (architect, §9.3):** names in **`aria-label` only** ("Level 5 — Prison") via an inline `sea_names` dict; visible UI stays **numbers-only**. **RESOLVED (user sign-off 2026-06-09):** expose the location names in `aria-label` ("Level 5 — Prison"); visible UI stays numbers-only. |
| SQ4 | **Ambient decoration:** add a Sea analog of the drifting ghosts (drifting boats / gulls / clouds), or keep it clean? | **LOCKED (architect, §9.6):** **OFF by default**; a `.sea-ambient` hook is documented for a later trivial add (zero contract change). No user input needed. |
| SQ5 | **Small-screen / responsive:** how should the wide landscape map behave on mobile — horizontal scroll/pan, scale-to-fit (letterbox), or **fall back to the existing island grid** under a breakpoint (which would mean NOT deleting the grid markup)? | **LOCKED (architect, §9.5):** scale-to-fit + letterbox on desktop, **pan-to-fit** on mobile (mirrors Horror); **NO grid fallback** → SR1 "replaces" stays literal, R-S6 closed. **RESOLVED (user sign-off 2026-06-09): no mobile grid fallback** — map scales/pans to fit on all sizes; Sea grid markup deleted. |
| SQ6 | **Naming/theme mismatch:** the "light/Sea" art locations carry **eerie** names (Graveyard, Mausoleum, Dragon's Dew, Haunted Tower). Confirm this art is intended for the **Sea (light)** theme as-is, and that the Sea theme keeps its sunlit azure palette/copy ("Enter the Corridor"/🌙) despite the macabre island names. | **RESOLVED (user sign-off 2026-06-09):** (a) use the art for the **Sea & Island (light)** theme **as-is**; (b) Sea keeps its **sunlit azure palette** + "Enter the Corridor"/🌙 copy; (c) location names **exposed in `aria-label`** (visible UI numbers-only). This is the Sea & Island theme — the painted location names are treated as island names, not a horror restyle. |

### 10.6 Risks (R-S — expanded + status from ARCHITECTURE §9.9)
| # | Risk | Status / mitigation |
|---|---|---|
| R-S1 | **Horror regression** from shared-class refactor (SQ1) — touching `.map-hotspot`/map machinery could alter the Horror landing. | **MITIGATED (severity → low):** §9.2 decision touches no `.horror-*` rule, no Horror markup, no `coords` dict, introduces no shared macro. Residual: the one-line calibrate-JS selector change — QA confirms Horror `?calibrate` still highlights `.horror-map` (S-QA). |
| R-S2 | **Byte budget blown** — shipping the raw 2.7 MB PNG regresses load/perf (NF-SR1). | **OPEN until verified:** mandatory §9.4 optimization (≤400 KB WebP); the raw 2.7 MB PNG is never shipped. Security (S6) + QA (S7) verify the committed asset size. |
| R-S3 | **Toggle clash** — the real overlay toggle overlapping the painted toggle pill looks broken/duplicated (SR6). | **Mitigated (visual eyeball needed):** place the real `.sea-map-toggle` top-right (`position:absolute; top:1rem; right:1rem; z-index:6`) directly over the painted pill so it reads as "the pill is the button"; copy/icon 🌙 "Enter the Corridor". Verify at S5/S7. |
| R-S4 | **Coord drift** — reusing Horror `coords` would mis-place hotspots on the different archipelago layout (SR4). | **CLOSED:** distinct `sea_coords` dict (§9.3) measured against THIS art + calibrate aid now reaches `.sea-map`. S3/S7 fine-tune. |
| R-S5 | **Mobile usability** — wide landscape map unusable/illegible on portrait phones (NF-SR3). | **Addressed:** pan-to-fit model (§9.5) proven on Horror; wider Sea ratio = longer vertical pan. QA mobile pass (S7) confirms all 19 islands reachable, hotspots clear ~44px. |
| R-S6 | **Grid removal vs fallback conflict** — if SQ5 chooses a grid fallback, SR1's "replaces the grid" must be softened to "replaces above breakpoint." | **CLOSED under the locked default (§9.5: no grid fallback)** — SR1 stays literal, grid markup deleted. **Closed for good (user sign-off 2026-06-09): no grid fallback.** |
| R-S7 | **(NEW) Painted toggle pill baked into the optimized image** — the pill is part of the art, so it ships in the WebP; a later branding change to the toggle can't edit the painted pill without re-exporting the art. | **Low severity (maintainability, NF-SR6):** document the art source so a re-export is possible. |
| R-S8 | **(NEW) Landscape pan range buries low-id islands on mobile** — the ~16:9 art panned at 130–175vw pushes bottom-row islands (12/15/17) far down-scroll; some may be hard to reach. | **Low severity:** start corner shows 0–4; QA (S7) confirms **all 19 hotspots reachable on mobile** and considers a subtle "pan to explore" affordance. |

### 10.7 Out of scope (explicit)
- Horror theme (`static/img/horror/landing-map.v2.jpg`, `.horror-*` styles, the Horror template branch + its `coords`), backend / `drive_service.py` / `main.py`, routes, payload schemas, audio engine, Drive / missing-fallback logic, deployment config. None change.

---

## 11. Missing-level fallback audio → local per-theme track (bug fix — 2026-06-09)

**Trigger:** with a real Drive configured, every missing level (0, 3–7) returned **502 "Upstream Drive error."** Root cause: the Drive `missing/` folder holds only **images** (no audio), but the fallback required an image **AND** an audio file (original F9 / D6 / D9 / D11) and raised when audio was absent.

**Decision (user):** for a missing level, play **a random LOCAL track for the active theme** (`static/audio/{theme}/level_*.mp3`) instead of Drive audio. The `missing/` folder is now images-only.

**As-built behavior:**
- `drive_service.get_level_photos` (missing path) returns 1 random image from `missing/` and `fallback_audio = None`; it raises only if there is **no image** (never over absent audio).
- `main.py /level/{id}` passes `audio_track_ids` (the ids with a local `static/audio/{theme}/level_*.mp3`, theme validated by `read_theme`, so no path traversal) to `level.html`.
- `level.html` audio logic: available level → its own `level_{id}.mp3`; **missing level → a random id from `audio_track_ids`** for the active theme; otherwise ambient only.
- `/api/levels/{id}/photos` payload for a missing level: `available:false`, one proxied image, `fallback_audio:null`.

**Scope:** `app/drive_service.py`, `app/main.py`, `templates/level.html`, + the affected `tests/test_backend.py` / `tests/test_cache.py`. No route/signature change; `fallback_audio` stays in the payload (now always `null` for missing levels). Full suite **140 passed**.

---

## 12. Hosting / Deployment (M8 — change request 2026-06-09)

Status: **Host CHOSEN — Render (D13, user-decided 2026-06-09); HostQ1 RESOLVED.** Remaining open Qs = cold-start tolerance (HostQ2), domain (HostQ3), Drive-sharing confirm (HostQ4), traffic/region (HostQ5), and `/api/refresh` auth (R-D6) — these shape the Render deploy but do **not** block starting it. Trigger (verbatim user request): *"how are we going to host the website? Need a free hosting tool, maybe github / vercel? ask question if you have any."* This section frames the **hosting requirements + decision inputs** for **M8 (Deploy)** — the last open milestone. **Planning only; no code.** The architecture (FastAPI + Uvicorn ASGI, SSR, Drive byte-proxy, startup discovery + in-memory cache) is fixed ground truth and is NOT being re-opened by this request unless a host choice forces it (see HostC2/HostQ1). Deploy config is already committed: `render.yaml` (Render free **web service** Blueprint) + `Procfile` (Railway/Heroku-style).

### 12.1 Architectural ground truth the host MUST satisfy (verified)
The app is **NOT a static site**. It is a **persistent Python ASGI server** with state in the running process:
- **SSR Jinja2** — the server renders every page per request and reads a `theme` cookie (no static prebuild).
- **Google Drive byte-proxy** — the backend streams image bytes from Drive using a **server-side secret `GD_API_KEY`** (read via `os.environ`); the key MUST stay server-side and never reach the browser (hard security rule, F10). `GD_ROOT_FOLDER` is the parent-folder config.
- **Startup discovery + in-memory cache** (FastAPI `lifespan`) — on boot it lists the Drive parent's children to discover levels and caches the level→folder map + per-level/`missing/` scope + a bounded LRU of image bytes. A manual **`POST /api/refresh`** rebuilds the cache. **This state lives in the running process** (R2).
- **Audio** served as static files from `static/audio/`.
- **Health check** at `/api/levels`; graceful degradation if env vars are unset (serves an empty gallery).

> Implication: the natural fit is a **persistent web service**, not static hosting and not (without rework) stateless serverless functions. See HostC1/HostC2.

### 12.2 Hosting requirements (HostR#)
| # | Requirement | Type | Priority |
|---|---|---|---|
| HostR1 | Host MUST run a **persistent Python ASGI server** (Uvicorn, `app.main:app`) — or an equivalent long-lived process — capable of executing the `lifespan` startup discovery and holding the in-memory cache across requests (R2). | Functional | Must |
| HostR2 | Host MUST inject **`GD_API_KEY` (secret)** and **`GD_ROOT_FOLDER` (config)** as platform environment variables, never committed to git (`sync:false` in `render.yaml`; platform vars for Railway/Procfile). | Functional | Must |
| HostR3 | The `GD_API_KEY` MUST remain **server-side only** and never be exposed to the browser or baked into any client bundle (F10, hard security gate — SECURITY_ENGINEER veto). | Non-functional (security) | Must |
| HostR4 | Host MUST serve over a **public HTTPS URL** (platform-provided subdomain acceptable; custom domain is an open question — HostQ3). | Non-functional | Must |
| HostR5 | Host MUST **auto-deploy from the `main` branch** of the GitHub repo on push (`autoDeploy: true` already set in `render.yaml`). | Functional | Must |
| HostR6 | Host MUST support a **health check** at `/api/levels` (already wired in `render.yaml` `healthCheckPath`). | Non-functional | Must |
| HostR7 | Total recurring cost MUST be **$0 / free tier**. | Non-functional (cost) | Must |
| HostR8 | The build MUST install from `requirements.txt` (pinned fastapi/uvicorn/starlette/jinja2/httpx/python-dotenv) on **Python 3.13** (`PYTHON_VERSION=3.13.0`). | Functional | Must |
| HostR9 | **Cold-start / spin-down behavior** on the chosen free tier MUST be defined and accepted (free tiers commonly idle-spin-down → first-request delay). Acceptability is an open question — HostQ2. | Non-functional | Should |
| HostR10 | Existing **CI MUST stay green** (full pytest suite, 140 passed) as a pre-deploy gate; no deploy off a red `main`. | Process | Must |
| HostR11 | The **`missing/` fallback audio** is local (`static/audio/{theme}/`, §11) and **all audio ships in the repo** (D9), so the host MUST serve `static/` reliably; no external audio dependency at runtime. | Functional | Must |

### 12.3 Static / serverless incompatibility (HostC# — decision inputs, recorded)
| # | Constraint / finding | Verdict |
|---|---|---|
| HostC1 | **GitHub Pages is static-only.** It cannot run a Python server, cannot hold a server-side secret, and cannot proxy Drive bytes. It violates HostR1/HostR2/HostR3. | **NOT viable** for the current architecture without abandoning the secure proxy / re-architecting to a fully client-side app (which would then expose or remove `GD_API_KEY` — fails F10). |
| HostC2 | **Vercel is serverless functions + static/edge.** FastAPI CAN run as a Vercel Python serverless function, BUT serverless is **stateless/ephemeral**: the startup-discovery + in-memory cache + `POST /api/refresh` model (R2) does not hold across cold invocations (each instance may re-discover; a refresh would not persist), plus cold starts and function execution/bandwidth limits on **streaming Drive bytes**. | **Possible only with rework + tradeoffs** (move discovery per-request or to external cache, accept ephemeral refresh, watch streaming limits). Not a drop-in for the committed `uvicorn` web-service model. |
| HostC3 | **Persistent web-service hosts are the natural fit.** Candidates (for the architect's matrix): **Render** free web service (already Blueprinted; idles/spins down after ~15 min → cold-start delay on next hit), **Fly.io** (small free machine allowance, persistent), **Hugging Face Spaces** (free Docker/FastAPI, supports secrets). | **Preferred direction** — preserves HostR1–HostR3 with the committed config. |
| HostC4 | **Railway no longer has a truly free always-on tier** (usage-based trial credit only), despite a `Procfile` already being committed for it. | **Flag:** the committed `Procfile` stays valid as a process declaration (Railway/Heroku-style), but Railway should not be assumed "free" — keep it as a fallback/portability artifact, not the primary HostR7 answer. |

### 12.4 Open Questions (HostQ# — ALL RESOLVED 2026-06-09 except HostQ4, a deploy-time user precondition)
| # | Question | Why it matters | Default / lean |
|---|---|---|---|
| HostQ1 | ✅ **RESOLVED (Render) — D13, 2026-06-09.** Keep the FastAPI Drive-proxy + in-memory-cache architecture on a persistent web-service host; deploy as a **Render free web service** via the committed `render.yaml`. Vercel/GitHub Pages rejected (static/serverless rework, HostC1/HostC2). | Determined the host class. | **Resolved: keep architecture → Render.** Fly.io / HF Spaces documented as fallbacks. |
| HostQ2 | ✅ **RESOLVED (2026-06-09): accept spin-down.** Render free web service idles after ~15 min → ~30–60s cold start on next hit; accepted as-is (no keep-warm pinger). | Sets HostR9 acceptance. | **Resolved: accept free-tier spin-down.** |
| HostQ3 | ✅ **RESOLVED (2026-06-09): custom domain via a free DNS service (FreeDNS / afraid.org).** A FreeDNS subdomain CNAMEs to the Render `*.onrender.com` host; the custom domain is added in the Render dashboard (Render issues TLS). | Custom domain adds DNS + TLS steps (D-task in M8). | **Resolved: custom domain via FreeDNS** (not the bare `*.onrender.com`). |
| HostQ4 | **Drive sharing confirmation:** confirm the Drive parent folder stays **"Anyone with the link → Viewer"** (D12) so the deployed `GD_API_KEY` can read it from the cloud host's IPs. | If access is later restricted, the deployed proxy 502s on every fetch (cf. §11). Must be true for HostR1 to function in production. | **Lean: confirm D12 unchanged (already locked).** *(User-action precondition at deploy time.)* |
| HostQ5 | ✅ **RESOLVED (2026-06-09): Asia → `singapore`.** Low traffic; deploy region set to Singapore in `render.yaml` (changed from `oregon`). | Region + free-tier bandwidth sanity-check. | **Resolved: low traffic, Singapore region.** |
| R-D6 | ✅ **RESOLVED (2026-06-09): token-gate `POST /api/refresh`.** Before public launch, `/api/refresh` MUST require a shared-secret token (e.g. an `X-Refresh-Token` header matching a `REFRESH_TOKEN` env var; reject otherwise). Small **backend change** (now in scope — §12.5), routed backend-engineer → SECURITY_ENGINEER → QA_TESTER. | An open endpoint triggering Drive listing could be abused (compute/egress). | **Resolved: token-gate `/api/refresh`.** |

### 12.5 In/out of scope (updated after sign-off 2026-06-09)
The M8 diff is now: (a) **doc** updates; (b) **`render.yaml`** region `oregon → singapore` (HostQ5); (c) **one backend change** — token-gate `POST /api/refresh` with a `REFRESH_TOKEN` env var (R-D6), plus its tests; (d) **deployment + FreeDNS custom-domain runbook** in `README.md`. No frontend/route/payload/audio behavior changes; no host config beyond Render (Render chosen — D13, so no Dockerfile/fly.toml).
