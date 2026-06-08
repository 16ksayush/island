# Requirements — Archive 19: Dual-Atmosphere Dynamic Gallery

Status: **Discovery COMPLETE — design approved, asset reality confirmed (§7).** Supersedes the original single-theme blueprint. Build proceeds with placeholders (§8). **Active change request: Horror Atmosphere Redesign — see §9 (visual-only restyle of the Horror theme; Sea untouched).**

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
| F1 | Render a dynamically-sized level grid from whatever levels are configured (5, 12, 19…). | Must |
| F2 | Global theme toggle reachable on **every** page view. | Must |
| F3 | Theme selection persists for the session (cookie + `sessionStorage` — see D1). | Must |
| F4 | Clicking a level navigates to a dedicated **`/level/{id}`** page (`level.html`). | Must |
| F5 | The active theme dictates how the level page is presented (room vs beach). | Must |
| F6 | Landing page plays the theme's **global ambient** track. | Must |
| F7 | Entering a level **crossfades**: wind down global ambient, scale up that level's track. | Must |
| F8 | Images per level fetched from numbered Google Drive subfolders, proxied as bytes (D2). | Must |
| F9 | **Missing-level fallback:** if a numbered folder is absent, pull 1 random **image** AND 1 random **audio** from the Drive `missing/` folder (which holds stock images + stock audio), both proxied through the backend. | Must |
| F10 | Browser never receives the Google Drive API key. | Must |
| F11 | Responsive layout for both theme grids (corridor / archipelago). | Should |

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
- **D6 — Missing handling:** ✅ Absent numbered folder → random **image + audio** both from the Drive `missing/` folder (it holds stock images and stock audio), proxied through the backend.
- **D7 — Level metadata:** ✅ Number only (no titles/descriptions).
- **D8 — Access:** ✅ Public, no auth.
- **D9 — Asset split:** ✅ **Images in Google Drive; normal per-level audio in the GitHub repo** (`static/audio/`). Exception: the **missing-level fallback** image AND audio both come from the Drive `missing/` folder.
- **D12 — Drive access:** ✅ The `all ages` parent folder is shared **"Anyone with the link → Viewer"**, so the plain `GD_API_KEY` can read it. No service account needed.
- **D10 — Drive config:** ✅ A single **parent** Drive folder (one link/ID in `GD_ROOT_FOLDER`) whose children are the numbered subfolders `0..18` + `missing/`. Backend lists the parent's children to discover which levels exist → dynamic scaling.
- **D11 — Per-theme level tracks:** ✅ Horror and Sea each have their **own** per-level tracks (`static/audio/horror/`, `static/audio/sea/`). The missing-level fallback audio is NOT local — it comes from the Drive `missing/` folder per D6/D9.

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
