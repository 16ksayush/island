# Requirements — Archive 19: Dual-Atmosphere Dynamic Gallery

Status: **Discovery COMPLETE — design approved, asset reality confirmed (§7).** **M12 — Build-time image baking: Discovery COMPLETE pending user sign-off — design LOCKED (§14 + ARCHITECTURE §12); user decided Approach A (bake at BUILD time → serve static, no runtime Drive image proxy, 2026-06-09). Architect resolved BakeQ2/Q3/Q5/Q6 (bake `missing/`; manifest PRIMARY + metadata FALLBACK; verbatim `PhotoRef.name`; same script locally). Three user-facing items remain: BakeQ1 (keep/drop the media proxy — recommend KEEP), redeploy-acceptance (NF-Bake6), and the D12 build precondition (env vars in Render + Drive "Anyone with link → Viewer"). Depends on M11 (captions keyed by (level, filename) must keep matching — hard gate NF-Bake4), interacts with M8 (M12 edits only `render.yaml buildCommand`; M8 only the region line — non-overlapping). Execution (B3–B8) runs on sign-off.** Supersedes the original single-theme blueprint. Build proceeds with placeholders (§8). **M8 — Deploy: host CHOSEN — Render (D13); HostQ1 RESOLVED. Remaining open Qs = cold-start tolerance, domain, /api/refresh auth, Drive-sharing confirm, traffic/region (HostQ2–Q5 + R-D6) — these shape but do not block the Render deploy. Requirements in §12.** **M10 — Sea (Light) landing map: BUILT, SECURITY-APPROVED, QA-VERIFIED (140 passed) — pending commit; see §10 (frontend-only; replaced the Sea island grid with a full-bleed archipelago map + hotspots; Horror untouched). Prior: Horror Atmosphere Redesign §9 (M9, shipped). After M9+M10, both themes are map-based.**

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

---

## 13. M11 — Image captions (dual-theme) (change request — 2026-06-09)

Status: **BUILT + SECURITY-APPROVED + QA-VERIFIED (156 passed) — pending commit (2026-06-09).** All open questions resolved (§13.5): CapQ1 `(level, filename)` key, CapQ2 overlaid `<figcaption class="slide-caption">`, CapQ6 missing-level uncaptioned, CapQ7 `app/captions.json` startup-cached + re-read on `POST /api/refresh` — all architect-locked and built as designed; CapQ3 guardrail APPROVED, CapQ4 = nickname **"Chudail"** (no real name), CapQ5 = draft & ship directly (review gate waived — see below). **Every CapR# and NF-Cap# is satisfied** by the as-built feature (CapR1–CapR7, NF-Cap1/Cap2/Cap4/Cap5/Cap6 met; **NF-Cap3's mandatory pre-ship review gate was waived by the user per CapQ5** — drafted & shipped directly, user may edit afterward). Delivered: **52 real images (levels 1, 2, 8–18) × {sea, horror} = 104 captions** in `app/captions.json`, subject referred to as **"Chudail"** (a real-name "ANSHIKA" cake-text leak was caught and scrubbed from 13.4; 17.0/18.1/18.2 are stylized artwork, captioned to match). Backend `app/captions.py` (tolerant loader, startup-cached, reloads on `POST /api/refresh`) + `app/main.py` `_ref` adds an optional `caption:{sea,horror}` (omitted when absent — payload back-compat). Frontend `templates/level.html` renders a per-slide `<figcaption class="slide-caption">` via `textContent`, theme-scoped in `static/style.css`. QA added `tests/test_captions.py`; full suite **156 passed** (was 140); live smoke after server restart confirmed captions in the `/api/levels/{id}/photos` payload for both themes. This was a new feature: every **real** gallery image gets **two** one-line captions, theme-selected (Sea = light & funny, Horror = dark/playful-spooky), shown with the image in the level-page slideshow.

### 13.1 Intent (verbatim user request)
"Can you look at each image (not the missing ones), and generate a 1-liner explanation for all images to be displayed with images. I am not planning to add many more of those. Context: all of these are images of my **sister from young to 18**, different age groups, and I want to present this as a **gift to her**. All images should have **two descriptions: one light and funny (for the Sea theme), one dark/a-bit-horror (for the dark/Horror theme).**"

### 13.2 Verified scope (ground truth — counted via the running app + real Drive)
- **52 real images** across the **13 available levels** (ids **1, 2, 8–18**) — level **18** added 2 images on 2026-06-09 (cache refreshed via `POST /api/refresh`). The missing levels (**0, 3–7**) serve the `missing/` fallback and are **explicitly out of scope** for authored captions (see CapQ6).
- Each image is returned by `/api/levels/{id}/photos` as `{ "file_id": "<driveId>", "url": "/api/levels/{id}/media/<driveId>" }`. Internally the backend `PhotoRef` also carries the image **name** (e.g. `{n}.{i}.jpeg`), so a caption can be keyed by Drive **file_id** or by **(level, name)** (see CapQ1).
- Images display in the **level-page slideshow** (`level.html`, one image at a time, ~3 s/slide). Theme is SSR from the cookie (Horror default).
- Deliverable: **52 image → {sea_caption, horror_caption}** pairs (**104 one-liners** total), authored by **viewing each image** (the app serves the bytes; vision-capable generation happens in the **execution** phase, not now).
- The subject is the user's **sister, photographed from young (child/minor) to 18**, and the gallery is intended as an **affectionate gift** — this drives the hard tone/sensitivity guardrail (NF-Cap1) and the privacy considerations (NF-Cap2).

### 13.3 Functional requirements

| # | Requirement | Priority |
|---|---|---|
| CapR1 | Each **real** image (levels **1, 2, 8–18**) has **TWO** one-line captions: **Sea = light & funny**, **Horror = dark/playful-spooky**. The currently active theme selects which caption is shown (mirrors the SSR cookie → `.theme-*` mechanism, D1/D3). | Must |
| CapR2 | Captions display **with the image** in the level-page slideshow — **per-slide**, updating as the slideshow advances so the caption always matches the visible image. Placement (overlay vs below) is a decision — CapQ2. | Must |
| CapR3 | The caption set is **fixed and small** (~50 images; the user "won't add many more"), so a **committed data file** (e.g. `captions.json` / `.yaml`) is the storage mechanism — **not a database**. Format/location is a decision — CapQ7. | Must |
| CapR4 | Captions are keyed to images by a stable identifier — Drive **file_id** vs **(level, filename)** — so the right pair attaches to the right image. The key choice is a decision — CapQ1 (recommend the more stable key). | Must |
| CapR5 | **Missing-level fallback** images (levels 0, 3–7, served from `missing/`) get **no authored caption** — either no caption or a single generic themed placeholder. Decision — CapQ6. | Should |
| CapR6 | The backend payload change (if any) MUST be **backward-compatible**: captions are **optional** in the `/api/levels/{id}/photos` response (or supplied to the template out-of-band); an image with no caption renders exactly as today (no empty/blank caption box). | Must |
| CapR7 | Captions are **authored AI-generated** (the assistant views each image and writes both lines) and then pass through a **user review/edit sign-off** before they ship (NF-Cap3). The execution backlog must surface the drafts for review (e.g. a 50×2 table). | Must |

### 13.4 Non-functional requirements

- **NF-Cap1 — Tone & sensitivity (CRITICAL — hard content guardrail, flagged prominently).** These are **real photos of the user's sister, several taken as a child/minor**, intended as an **affectionate gift**. Therefore:
  - The **Horror** captions MUST be **whimsical / playful-gothic** — a Halloween-storybook flavor that is **affectionate and wholesome**. They MUST NEVER be genuinely creepy, demeaning, frightening, threatening, or about her **appearance / body**, and MUST NEVER sexualize, objectify, or be unkind. "Dark" here means **cute-spooky**, not scary.
  - The **Sea** captions MUST be **warm, funny, and sweet** — gentle affectionate humor, never mocking.
  - This is a **hard guardrail on the generation step**: SECURITY_ENGINEER / QA review the tone of every generated line, and the user signs off (CapQ3). Any line that reads as creepy, body-focused, sexualizing, or unkind is rejected and rewritten.
- **NF-Cap2 — Privacy.** The captions and the entire gallery will be **publicly accessible**: a public Render URL (M8), Drive shared "anyone with the link → Viewer" (D12), **and a public GitHub repo** that would hold the committed `captions.json` (CapR3). Surface this: the captions should likely **avoid the sister's real name and any identifying personal details** (school, addresses, surnames, etc.). The naming policy is a decision — CapQ4.
- **NF-Cap3 — Authoring & review (sign-off gate).** Captions are AI-generated by the assistant viewing each image, but because this is a **personal gift**, the user **reviews and edits** the full set **before it ships**. No captions are committed/displayed until the user signs off (CapQ5). The review surface (e.g. a Markdown table of all 50 images × 2 captions) is part of the execution backlog.
- **NF-Cap4 — Length / layout / i18n.** Captions are **one-liners** — short enough to overlay on or sit beneath a slideshow image on **mobile and desktop** without clutter, wrapping, or obscuring the photo. A soft length budget should be defined by the architect (e.g. ≤ ~60–80 chars).
- **NF-Cap5 — No regression.** No regression to the existing slideshow, **prefetch**, **audio crossfade**, **theme isolation**, or **performance** (M9/M10, §11). The caption data must not block first paint or slide preload. The backend payload change stays **backward-compatible** (CapR6).
- **NF-Cap6 — Maintainability.** Single source of truth for captions in the committed data file (CapR3); the key strategy (CapQ1) documented; adding/editing a caption later is a one-line data edit with no code change. Document the data file's schema in `ARCHITECTURE.md`.

### 13.5 Open questions (CapQ — resolution state after ARCHITECTURE §11)

**Architect-LOCKED (no user input required to proceed):** CapQ1, CapQ2, CapQ6, CapQ7.
**✅ ALL CapQs RESOLVED (user sign-off 2026-06-09):** CapQ3 guardrail APPROVED (playful, never creepy); CapQ4 = nickname **"Chudail"**, no real name; CapQ5 = draft & ship directly (review gate waived). CapQ1/Q2/Q6/Q7 architect-locked. **M11 cleared for execution.**

| # | Question | Why it matters | Resolution |
|---|---|---|---|
| CapQ1 | **Caption → image key:** map by Drive **file_id** (breaks if an image is re-uploaded → new id) vs by **(level, filename)** (stable across re-upload, but needs the backend to expose/track the image name in the payload)? | Wrong/unstable key → a caption attaches to the wrong photo or silently drops after a re-upload. | **✅ RESOLVED (architect, §11.1) — key by `(level, filename)`.** Stable across re-upload, human-editable, read from `PhotoRef.name` with zero new Drive calls. `file_id` rejected (re-upload fragility, R-Cap1). Contract: a re-uploaded file must keep its `{n}.{i}.jpeg` name or its caption goes inert (never errors). |
| CapQ2 | **Display placement:** caption **overlaid** on the image (bottom gradient bar) vs **below** the slide? Theme-styled (Horror gothic vs Sea sunlit)? | Defines the `level.html` / `style.css` diff and the mobile-clutter risk (NF-Cap4). | **✅ RESOLVED (architect, §11.4) — overlaid bottom-gradient `<figcaption class="slide-caption">` per slide, theme-skinned** (`.theme-horror`/`.theme-sea`), ≤~70 chars + `-webkit-line-clamp`; documented `≤480px` below-stage fallback if the overlay crowds. Visual eyeball at QA (R-Cap4). |
| CapQ3 | **Tone calibration / guardrails (CRITICAL).** | Hard content guardrail (NF-Cap1). | ✅ **RESOLVED — APPROVED (user, 2026-06-09):** Horror = **playful-gothic / cute-spooky & affectionate** (never genuinely scary, never body/appearance-focused, never sexualizing/unkind); Sea = **funny & sweet**. Binding on every generated line. |
| CapQ4 | **Privacy / naming.** | Public repo + Render URL + Drive (NF-Cap2, R-Cap2). | ✅ **RESOLVED (user, 2026-06-09): NO real name.** Refer to her by the affectionate nickname **"Chudail"** (witch/ghost — doubles as anonymization AND fits the spooky theme). No surname, school, address, or other identifying detail. |
| CapQ5 | **Authoring + review flow.** | Sets the review gate (NF-Cap3, CapR7). | ✅ **RESOLVED (user, 2026-06-09): draft & ship DIRECTLY.** Assistant views each image, drafts both captions under the guardrail, and writes `app/captions.json` **without a separate review gate** (user may edit afterward). NF-Cap3's mandatory pre-ship review is **waived by the user** for this milestone. |
| CapQ6 | **Missing-level images:** caption the `missing/` fallback images with a **generic themed line**, or leave them **uncaptioned**? | The fallback image is re-rolled per visit (R3), so it has no stable identity to caption (CapR5). | **✅ RESOLVED (architect, §11.1/§11.2) — uncaptioned.** Re-rolled fallback images (levels 0, 3–7) have no stable identity; an optional single generic per-theme placeholder is a trivial later add, not designed now. |
| CapQ7 | **Storage format / location:** `captions.json` vs `.yaml`; keyed per the CapQ1 decision; committed at **repo root** or under `app/` / `static/`? Loaded at startup (cached) or per request? | Architect to specify the schema, location, and load path so it fits the existing cache/SSR model (R2). | **✅ RESOLVED (architect, §11.2/§11.7) — `app/captions.json`** (shape `"<level>" → "<filename>" → {sea, horror}`), JSON over YAML (no new dep). Loaded **once in `lifespan` + cached** via a new `app/captions.py`; **re-read on `POST /api/refresh`**; missing/malformed file → empty map → feature inert (never raises). |

### 13.5.1 Risks (R-Cap — from ARCHITECTURE §11.8)
| # | Risk | Status |
|---|---|---|
| R-Cap1 | **Re-upload key fragility** — `file_id` key would drop a caption on re-upload. | Mitigated by the `(level, filename)` key (§11.1); residual: a renamed file goes inert (degrades, never errors). |
| R-Cap2 | **Privacy** — `app/captions.json` is committed to a PUBLIC repo + served via a public URL, describing a real minor. | Mitigated by no real name / no identifying details + affectionate generic phrasing; gated on CapQ4. SECURITY data-flow review (C7). |
| R-Cap3 | **Content-safety gate (CRITICAL)** — subject is a real minor + the deliverable is a gift; Horror tone must stay cute-spooky. | Generation BLOCKED until CapQ3 sign-off; every line passes SECURITY/QA tone review; creepy/body-focused/sexualizing/unkind lines rejected. |
| R-Cap4 | **Mobile overlay overflow** — a long caption could crowd the slide / push dots/nav on small screens. | Mitigated by ≤~70-char budget + `-webkit-line-clamp` + documented ≤480px below-stage fallback; verify on real mobile at QA. |
| R-Cap5 | **Payload-shape test fragility** — a test hard-asserting the image-object key set would break on the new `caption` key. | Checked — none do (membership/value assertions only in `tests/test_backend.py`/`tests/test_cache.py`); keep new caption tests tolerant of absence. |
| R-Cap6 | **Stale captions after edit without refresh** — cached at startup, so an edit needs a restart or `POST /api/refresh`. | Low severity; documented (§11.2). Rides the same `/api/refresh` endpoint that R-D6 is token-gating. |

### 13.6 In/out of scope (explicit)
- **In scope:** a committed caption data file (CapR3/CapQ7); an **optional, backward-compatible** payload/template extension to surface captions in the slideshow (CapR2/CapR6); a theme-styled caption display in `level.html` + `style.css` (CapQ2); the **guardrailed generation** of 50×2 captions by viewing each real image (CapR7/NF-Cap1, **execution phase only, after sign-off**); a **user review/edit gate** (NF-Cap3).
- **Out of scope:** captions for **missing-level** fallback images beyond an optional generic placeholder (CapR5/CapQ6); any **database** (CapR3); any new Drive/auth/deploy behavior; changes to discovery, the audio engine, prefetch, or theme isolation (NF-Cap5); a CMS/admin UI for editing captions (it's a committed data file).

---

## 14. M12 — Build-time image baking (move level images off the per-request Drive proxy) (change request — 2026-06-09)

Status: **BUILT + SECURITY-APPROVED + QA-VERIFIED (full suite 182 passed / 0 failed; was 156) — pending commit (2026-06-09).** Execution B3–B8 ran end to end via `orchestrate-build`: BACKEND_ENGINEER (B3 `scripts/fetch_images.py`, B4 manifest-PRIMARY discovery + guarded `_ref`) → PM+BACKEND (B5 `render.yaml buildCommand` + `.gitignore`) → SECURITY_ENGINEER (B6 APPROVED) → QA_TESTER (B7 `tests/test_m12_bake_manifest.py`, 26 cases) → PM (B8 doc-sync + smoke, this status). **All BakeR1–BakeR7 satisfied:** BakeR1 paced build-time bake (concurrency 2, jittered delay, exp-backoff retry on 403/429/5xx); BakeR2/BakeR3 static URL on the hot path (`_ref` emits `/static/img/levels/{id}/{name}`, `file_id`+`name` preserved); BakeR4 discovery correct from `manifest.json` PRIMARY → Drive-metadata FALLBACK → empty-gallery; BakeR5 `missing/` baked + per-visit re-roll; BakeR6 same `scripts/fetch_images.py` + `.env` locally with graceful unbaked fallback; BakeR7 `/media` proxy KEPT as a guarded, non-default fallback. **All NF-Bake1–NF-Bake7 satisfied:** NF-Bake1 `static/img/levels/` git-ignored (D9 audio allow-list + map/brand assets intact); NF-Bake2 paced/backoff bake; NF-Bake3 static-file serving (no per-request Drive on the hot path); NF-Bake4 caption `(level, filename)` key byte-identical (104 captions still attach); NF-Bake5 `GD_API_KEY` never in manifest/payload/static output/logs (SECURITY veto cleared); NF-Bake6 superseded by §12.13 background sync (no longer redeploy-only); NF-Bake7 single paced downloader shared by script + sync, documented. **§12.13 background sync SHIPPED:** `lifespan` task on `IMAGE_SYNC_INTERVAL_SECONDS` (default **1800**s; **0/unset disables** — task never created, keeps CI/pytest hermetic), cheap metadata change-check → paced delta download → atomic `manifest.json` swap + scope reload, single-flight; `/api/refresh` forces an immediate sync (R-Bake8 mitigations in force). New env var **`IMAGE_SYNC_INTERVAL_SECONDS`** added to `render.yaml` (set 1800 in prod). **Build precondition (confirm at deploy):** `GD_API_KEY`/`GD_ROOT_FOLDER` set in Render AND Drive stays "Anyone with link → Viewer". Depends on **M11** (captions keyed by `(level, filename)` — `app/captions.json` — kept matching, hard gate NF-Bake4 held) and interacts with **M8** (the Render deploy + `render.yaml`: M12 edits only the `buildCommand` line + the additive `IMAGE_SYNC_INTERVAL_SECONDS` env; M8's only pending `render.yaml` edit is region `oregon → singapore` per §12.5 — non-overlapping). All locked decisions D1–D13, R1–R6, and the shipped M9/M10/M11 features are preserved.

### 14.1 Trigger + decision (verbatim user intent — 2026-06-09)
The per-request Google Drive image **proxy keeps hitting throttling**: Drive's download endpoint (`files.get?alt=media`) returned **403 "rate-limit"** pages after a burst of downloads (the same burst recorded as the M11 transient throttle, §M11 operational note 2). Drive **metadata** (list children / `files.get` without `alt=media`) is **NOT** throttled the same way. The user asked: *"can we not pull in all the images from Drive to Render (local disk/memory) and then use those."*

**Decision (user, 2026-06-09) — Approach A: bake all images at BUILD time and serve them as static files; no runtime Drive image proxy.** Runtime startup-prefetch (fetch-on-boot into memory/disk) and commit-to-repo (check the images into git) were **rejected** (see the AskUserQuestion outcome). Build-time baking is robust on Render specifically because **Render env vars (`GD_API_KEY`, `GD_ROOT_FOLDER`) are available during the build command**, and the **build output is part of the served instance** (re-fetched only on redeploy, not on cold-start spin-up) — so the ephemeral runtime filesystem is a non-issue for baked images.

### 14.2 Verified current architecture (ground truth the change must respect)
- **Images** live in Google Drive under `GD_ROOT_FOLDER` (parent → numbered child folders; **present:** `1, 2, 8–18`; **absent:** `0, 3–7`; plus a `missing/` folder). **52 real images** across levels `1, 2, 8–18`; filenames `{n}.{i}.jpeg` (e.g. `2.1.jpeg`).
- `app/drive_service.py`: startup discovery (lists children → `folder_index`, `missing_folder_id`, `levels`), per-level scope (`PhotoRef{file_id, name}`), `resolve_media()` (downloads bytes), bounded in-memory LRU byte cache.
- `app/main.py`: `GET /api/levels/{id}/media/{file_id}` is the proxy (validates `file_id` ∈ resolved folder, R1; echoes upstream `Content-Type`, R6). `GET /api/levels/{id}/photos` returns each image as `{file_id, url:"/api/levels/{id}/media/{file_id}", caption?}` — `url` built in `_ref` (`main.py`), `caption` keyed by `photo.name` (filename), additive/optional (M11/§11.3).
- **M11 captions** are keyed by **(level, filename)** in `app/captions.json` — **any new scheme MUST preserve the filename** so captions keep matching (hard constraint, see NF-Bake4 / BakeQ5).
- **Hosting:** Render free web service (D13). **Env vars are available at build time.** Render free runtime FS is ephemeral, but the **build output ships with the instance** and is only refreshed on redeploy.
- **`.gitignore`** is allow-list style (negations protect `static/` + `static/audio/**/*.mp3`, D9). There is **no broad `static/` ignore today**, so baked photos would currently be eligible for commit — M12 MUST add an explicit ignore for the baked image dir (NF-Bake1 / BakeR1).

### 14.3 Functional requirements (BakeR#)
| # | Requirement | Priority |
|---|---|---|
| BakeR1 | A **build-time fetch step** (invokable from `render.yaml` `buildCommand`, AND runnable locally) downloads every available level's images from Drive into a **static directory** (e.g. `static/img/levels/{id}/{filename}`), preserving the original `{n}.{i}.jpeg` **filename**. The step is **gently throttled** (low concurrency + small inter-request delays) so the 52-image bulk pull does NOT trip Drive's download rate-limit (the same burst that produced the 403, §14.1). | Must |
| BakeR2 | At runtime the app serves these images as **plain static files** under `/static/img/levels/{id}/{filename}` — with **no `files.get?alt=media` proxy call** for level images on the request path. | Must |
| BakeR3 | `/api/levels/{id}/photos` image `url` points at the **static path** (`/static/img/levels/{id}/{filename}`) while **preserving `file_id` and `name`**, so M11 captions keyed by `(level, filename)` still match (CapR4 contract intact). The payload stays **backward-compatible** (additive/shape-preserving; the `caption` key behaves exactly as M11). | Must |
| BakeR4 | **Discovery** (which levels/images exist) MUST remain correct. Either (a) keep the cheap Drive **metadata** discovery at startup (metadata is not throttled), or (b) derive the level/image manifest from the **baked directory** / a **manifest file** the build writes — a decision (BakeQ3). The `available`/sealed landing semantics (F1, two-layer `available`) must be unchanged for the user. | Must |
| BakeR5 | The **`missing/` fallback** behavior (random image re-roll per visit, R3; fallback audio local per §11) is preserved. Whether the `missing/` images are also **baked** (and the re-roll picks from the local set) or **kept on the proxy** is a decision (BakeQ2). | Must |
| BakeR6 | **Local dev:** a developer MUST be able to obtain the images locally — by running the **same fetch script** (with their `GD_API_KEY`/`GD_ROOT_FOLDER`), and/or by a **graceful fallback** (e.g. proxy or empty gallery) when `static/img/levels/` is empty/unbaked. The exact dev source is a decision (BakeQ6). | Should |
| BakeR7 | The **media-proxy route** (`/api/levels/{id}/media/{file_id}`) is either **kept as a fallback** (for not-yet-baked / newly added images — resilient, but retains the throttle path) or **removed** (pure-static, simplest) — a decision (BakeQ1). If kept, all its existing security ACs (R1 file_id validation, R6 Content-Type echo) remain in force. | Must |

### 14.4 Non-functional requirements (NF-Bake#)
- **NF-Bake1 — Photos NOT in git.** The baked images are **personal photos in a PUBLIC repo** (privacy + bloat — parallels M11/NF-Cap2). `static/img/levels/` MUST be **git-ignored**; the photos exist **only in the build output**, never committed. M12 must add an explicit ignore rule (the current allow-list `.gitignore` does not yet cover this dir — §14.2). The `.gitignore` change MUST NOT regress the D9 audio allow-list (`static/audio/**/*.mp3` stays tracked) or `static/style.css` / `static/img/{horror,light,logo}` map+brand assets.
- **NF-Bake2 — Build resilience / pacing (CRITICAL).** A 52-image bulk pull is exactly the burst that tripped the 403. The fetch step MUST pace itself (bounded concurrency + small delays) and define a **failure mode** on throttle/error mid-build: **retry-with-backoff**, then either **fail the build** (no stale/partial deploy) or **degrade** (warn + ship whatever baked, runtime serves baked + falls back for the rest) — decision BakeQ4.
- **NF-Bake3 — Performance (positive).** Removing the per-request Drive round-trip should **improve** image latency and eliminate the runtime LRU-byte-cache pressure for level images. Static files get long-lived `Cache-Control` (matching today's proxy headers). Must not regress the index idle-prefetch / level eager-preload paths (the `url` changes value but the prefetch logic is URL-agnostic).
- **NF-Bake4 — Caption back-compat (hard gate).** The `(level, filename)` caption key MUST keep matching — the baked filename MUST equal the `PhotoRef.name` M11 keys on (`{n}.{i}.jpeg`). No regression to M11 (104 captions still attach), M9/M10 (maps), or M8 (deploy). The `/api/levels/{id}/photos` payload shape for callers/tests stays compatible (only the `url` **value** changes from a proxy path to a static path — assert tolerantly).
- **NF-Bake5 — Security.** `GD_API_KEY` stays **server/build-side only** — it is used by the build/fetch script (and, if BakeQ1 keeps it, the proxy), and MUST NEVER appear in the static output, the manifest, the payload, or any client bundle (F10, hard gate — SECURITY_ENGINEER veto). The baked filenames/paths must not leak Drive `file_id`s in a way that re-enables an open proxy if BakeQ1 removes the route. No path traversal via `{id}`/`{filename}` when serving static files.
- **NF-Bake6 — Redeploy semantics.** Adding/changing images requires a **redeploy** (re-runs the build, re-bakes). The user "won't add many more" images (mirrors M11/CapR3), so this is **acceptable** — but it MUST be documented (README/runbook): new images appear only after a redeploy, and `POST /api/refresh` alone will NOT pull new images at runtime (it only re-lists/re-reads, no download under pure-static).
- **NF-Bake7 — Maintainability.** A single source of truth for the fetch/bake logic (one script, used by both `render.yaml` and local dev); document the static layout, the URL scheme, the build-failure policy, and the local-dev workflow in `README.md` + `ARCHITECTURE.md`. Keep the change minimal and theme-agnostic.

### 14.5 Open questions (BakeQ# — RESOLVED by the SOLUTIONS_ARCHITECT except BakeQ1, which is a user sign-off item)
**Status:** BakeQ2 / BakeQ3 / BakeQ5 / BakeQ6 are **RESOLVED** by architect defaults (ARCHITECTURE §12). **BakeQ1** (keep/drop the media proxy) is carried to the **user sign-off gate** (B2) with a recommended default (KEEP). **BakeQ4** (build-failure policy) is resolved *conditionally on BakeQ1* — see the row.
| # | Question | Why it matters | Resolution |
|---|---|---|---|
| BakeQ1 | **Keep or drop the `/api/levels/{id}/media/{file_id}` proxy?** Keep as a fallback for not-yet-baked / newly added images (resilient, but retains the throttle path + the Drive byte client + LRU cache code) vs. remove entirely (pure-static, smallest surface, but a not-yet-baked image 404s until redeploy). | Defines whether `drive_service.resolve_media()` + the byte LRU + the media route stay or go, and the runtime security surface (R1/R6). | **⏳ USER SIGN-OFF (B2). Recommend KEEP as a guarded, non-default fallback** (ARCHITECTURE §12.5) — un-baked/new ids still resolve, never on the bulk path; DROP is a clean one-line follow-up if a zero-proxy surface is preferred. |
| BakeQ2 | **`missing/` fallback: bake those images too (pick locally on the per-visit re-roll, R3) or keep proxying `missing/`?** | The missing fallback is re-rolled every `/photos` call (R3); baking it keeps the no-runtime-Drive property; proxying it keeps Drive-fresh randomness but retains a throttle path. | **✅ RESOLVED — BAKE the `missing/` set** into `static/img/levels/missing/` (ARCHITECTURE §12.2/§12.3); the per-visit re-roll (R3) picks from the local baked set. |
| BakeQ3 | **Manifest / discovery source:** keep the cheap Drive-**metadata** discovery at startup (not throttled), or have the build write a **manifest** (e.g. `static/img/levels/manifest.json`) so the app needs **zero Drive calls at boot**? | Zero-Drive-at-boot removes the last startup Drive dependency (faster, throttle-proof cold start) but adds a build artifact + a new read path; metadata discovery is simpler but keeps a (cheap) Drive call on every cold start. | **✅ RESOLVED — build-written `manifest.json` PRIMARY** (zero Drive calls at cold start; no creds needed at runtime), **live Drive metadata FALLBACK**, empty gallery last resort (ARCHITECTURE §12.4). |
| BakeQ4 | **Build-failure policy:** on a download throttle/error mid-bake, **fail the deploy** (atomic, no partial gallery) or **warn + serve whatever baked** (graceful, paired with a runtime fallback)? | Sets NF-Bake2 behavior + whether BakeQ1's proxy fallback is required to cover a partial bake. | **✅ RESOLVED (conditional on BakeQ1) — retry/backoff then WARN + serve-partial** when the proxy is KEPT (recommended); **FAIL-the-build** only if the proxy is DROPPED (ARCHITECTURE §12.6). Settles with BakeQ1 at sign-off. |
| BakeQ5 | **Filename / URL scheme** that preserves the `(level, filename)` caption key (NF-Bake4). Confirm `static/img/levels/{id}/{name}` with `name == PhotoRef.name` (`{n}.{i}.jpeg`), and how duplicate/odd Drive filenames (if any) are handled. | A scheme that mangles or de-dupes the filename silently breaks M11 caption matching. | **✅ RESOLVED — `static/img/levels/{id}/{PhotoRef.name}` verbatim** (ARCHITECTURE §12.3); the `(level, filename)` key is byte-identical, so all 104 M11 captions keep matching. Hostile/`..`/path-separator names are rejected; a same-folder name collision is flagged loudly (never silently mangled). |
| BakeQ6 | **Local-dev image source:** run the same fetch script locally (developer needs `GD_API_KEY`/`GD_ROOT_FOLDER`), or fall back to the proxy / empty gallery when `static/img/levels/` is empty? | Defines the dev onboarding step + whether BakeQ1's proxy is the dev fallback. | **✅ RESOLVED — same `scripts/fetch_images.py` + `.env` locally** (ARCHITECTURE §12.8); graceful unbaked states (proxy URL when the proxy is kept, else empty gallery — no crash). |

### 14.6 Risks (R-Bake#)
| # | Risk | Status / mitigation |
|---|---|---|
| R-Bake1 | **Build still trips the 403** — the bulk bake is the same burst that throttled the proxy. | **Core risk → NF-Bake2:** bounded concurrency + inter-request delays + retry/backoff; metadata-only discovery isn't throttled, only `alt=media` downloads are. Architect specifies pacing; QA/PM verify a clean bake. |
| R-Bake2 | **Personal photos leak into git** — `static/img/levels/` committed to a PUBLIC repo (privacy + bloat). | **NF-Bake1:** explicit `.gitignore` ignore for the baked dir, added in the SAME change; SECURITY audit confirms no photo is staged/committed and the D9 audio allow-list is intact. |
| R-Bake3 | **Caption breakage** — a changed filename/URL scheme drops the M11 `(level, filename)` match. | **NF-Bake4 / BakeQ5:** bake the verbatim `PhotoRef.name`; QA asserts all 104 captions still attach after the URL switch. |
| R-Bake4 | **Secret exposure** — `GD_API_KEY` ends up in the static output, manifest, payload, or client (if the proxy is dropped, file_ids/paths must not re-enable an open proxy). | **NF-Bake5 (hard gate):** key build/server-side only; SECURITY veto; no Drive ids in client-reachable artifacts beyond today's contract. |
| R-Bake5 | **Render build-time limits** — bake time/bandwidth/disk on the free tier; a slow paced bake could hit build timeouts. | **Verify at execution:** measure bake duration for 52 images under the chosen pacing; if near a Render build limit, tune concurrency or accept it (small set, "won't add many more"). |
| R-Bake6 | **Stale images without redeploy** — `POST /api/refresh` won't pull new images under pure-static (NF-Bake6); operator expects refresh to fetch. | **Documented (NF-Bake6/NF-Bake7):** runbook states new/changed images require a redeploy (re-bake); refresh only re-lists/re-reads. Acceptable per user ("won't add many more"). |
| R-Bake7 | **Test fragility** — tests that hard-assert the proxy `url` value (`/api/.../media/...`) break when `url` becomes a static path. | **NF-Bake4:** QA updates URL assertions to the static scheme tolerantly (value changes, shape doesn't); cross-check `tests/test_backend.py`/`tests/test_cache.py`/`tests/test_captions.py`. |

### 14.7 In/out of scope (explicit)
- **In scope:** a **build-time fetch/bake script** (single source of truth, used by `render.yaml` + local dev); a **static layout** under `static/img/levels/{id}/{filename}`; the `/api/levels/{id}/photos` **`url` change** (proxy path → static path, filename preserved); the **`render.yaml` `buildCommand`** extension to run the bake (with build-time env vars); a **`.gitignore`** rule ignoring the baked dir (NF-Bake1); the keep/drop decision for the **media proxy** (BakeQ1) + the discovery/manifest source (BakeQ3); README/ARCHITECTURE doc updates; QA URL-assertion + caption-match updates; SECURITY audit of the new build path + `.gitignore`.
- **Out of scope:** any **theme/UI** change (M9/M10 maps untouched), the **audio** engine (local audio per §11 unchanged), **routes other than** the `url` value (and BakeQ1's optional proxy removal), the **caption authoring** (M11 content unchanged — only its key must keep matching), **M8's** separate `render.yaml` region edit + `/api/refresh` token-gate (independent, coordinate the shared `render.yaml` file), and any **database** or runtime-fetch-into-memory approach (rejected in §14.1).
