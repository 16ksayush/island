# Requirements — Archive 19: Dual-Atmosphere Dynamic Gallery

Status: **APPROVED design, pending asset data.** Supersedes the original single-theme blueprint.

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
- **D11 — Per-theme level tracks:** ✅ Horror and Sea each have their **own** per-level tracks (`static/audio/horror/`, `static/audio/sea/`), plus per-theme `_fallback/` sets.

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
