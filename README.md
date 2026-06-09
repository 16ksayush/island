# 🗝️ Archive 19 — Dual-Atmosphere Dynamic Gallery

An interactive web gallery with a **dynamically-scaled** number of levels (0 → up to 18), presented through **two distinct, toggleable realities**. The chosen theme persists across the whole session and can be switched from any page.

| THEME A — 🕯️ Horror | THEME B — 🏝️ Sea & Island |
|---|---|
| Illustrated **haunted map** — numbered destinations / doorways across an eerie landscape (clickable hotspots) | Illustrated **archipelago map** — sunlit islands across an open ocean (clickable hotspots) |
| `#0D0D0D` obsidian + `#FFB000` molten amber, shadowed vignette | `#E0F2FE`/`#0284C7` azures + warm sand, white coral, palm green |
| Continuous atmospheric horror soundtrack | Bright, relaxing ocean/acoustic ambient |

> **Status:** ✅ Implemented. The backend (FastAPI + build-baked static images, Drive proxy as fallback), frontend (SSR Jinja2 + dual themes + audio engine), and the full test suite (**182 passed**) are complete and security-audited. Both landings are illustrated maps with clickable hotspots (M9 Horror, M10 Sea); images now ship **baked at build into `static/img/levels/` and served as static files**, with a 30-min background sync for new images (M12). Deploy config (`render.yaml` / `Procfile`) is ready; live deployment (M8) is the remaining step. See [Project Status](#-project-status). *(Note: real Google Drive assets and the `.mp3` audio files are still placeholders.)*

---

## ✨ Features

- **Dual, toggleable themes** — Horror and Sea & Island, swapped from a control on *every* page.
- **Session-persistent theme** — stored via cookie + `sessionStorage`; SSR reads the cookie for a flash-free first paint (default: Horror).
- **Dynamic level discovery** — both landing maps render a fixed illustrated layout of 19 numbered hotspots; discovery of whatever numbered folders exist in Google Drive (5, 12, 19… all work) drives each hotspot's **availability** styling (sealed/sunken for missing levels), not the layout itself.
- **Per-level pages** at `/level/{id}`, styled as a *room* (Horror) or a *beach* (Sea).
- **Build-baked static images** — level images are downloaded from Google Drive **once at build time** (paced to avoid Drive's download throttle) into `static/img/levels/` and served thereafter as **plain static files** — no per-request Drive proxy on the hot path. The Drive image proxy is kept only as a guarded fallback for not-yet-baked / brand-new images, and the Google Drive API key **never** reaches the browser.
- **Background image sync** — a periodic background task checks Drive metadata every 30 min (`IMAGE_SYNC_INTERVAL_SECONDS`, default 1800; `0`/unset disables it) and, only when images actually changed, paced-downloads the delta and atomically updates the manifest — so new images appear **without a redeploy**, while user traffic stays static/Drive-free. `POST /api/refresh` forces an immediate sync.
- **Missing-level fallback** — if a numbered folder is absent (or empty), the backend serves 1 random image from the Drive `missing/` folder; the level's audio is a random **local per-theme track** (`static/audio/{theme}/`) chosen client-side, so a missing level never fails over absent Drive audio.
- **Per-image dual-theme captions** — every real gallery image carries two one-line captions (Sea = light & funny, Horror = playful-gothic); the active theme selects which one shows, rendered per-slide beneath the slideshow image. Captions live in a committed `app/captions.json` (keyed by `(level, filename)`) and are optional/back-compatible — an image with no caption renders exactly as before. Subject is referred to as "Chudail" (no real name).
- **Audio crossfade engine** — landing-page global ambient fades out while a per-level track fades in (and back), auto-play-safe.
- **Fast by default** — level images are served as **build-baked static files** (no per-request Drive round-trip on the hot path) with long-lived `Cache-Control`/`ETag` headers; discovery reads a build-written `manifest.json` so a cold start makes **zero Drive calls**. The level page shows a slow, scrollable **slideshow** (3s/slide) and the landing page **prefetches** all level images in the background, so navigation is near-instant after first load. (The guarded Drive proxy fallback still uses a bounded in-memory LRU for any not-yet-baked image.)

---

## 🧱 Tech Stack

| Layer | Technology |
|---|---|
| Backend | **FastAPI** + **Uvicorn**, **Jinja2** SSR, **httpx** (Drive client) |
| Frontend | Semantic HTML5, **Tailwind CDN** + custom `style.css` (`.theme-horror` / `.theme-sea`), native `<audio>` |
| Media | Images → **Google Drive**, baked at build into `static/img/levels/` + served static (proxy as fallback); audio → **GitHub repo** (`static/audio/`, served static) |
| Hosting | Render / Railway (free tier), secrets via environment variables |

---

## 🏛️ Architecture (overview)

```
Browser (Horror = illustrated haunted map w/ hotspots · Sea = illustrated archipelago map w/ hotspots)
   │  GET /level/{id}  (SSR page)          │  GET /api/levels/{id}/photos
   ▼                                        ▼
FastAPI (app/main.py) ── reads theme cookie ── renders level.html
   │
   ▼ app/drive_service.py ──GD_API_KEY (os.environ)──► Google Drive API (under GD_ROOT_FOLDER)
        • list parent's children → discover which levels exist (dynamic scaling)
        • folder {id} present → list its images
        • folder {id} ABSENT  → 1 random image from `missing/`; audio = random local per-theme track
   ▼
Browser proxies image bytes via /api/levels/{id}/media/{file_id}; never sees the key.
Audio loads from /static/audio/...  (no Drive, no key).
```

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Landing page; **both themes** = full-bleed illustrated map with 19 %-positioned clickable hotspots (`?calibrate` outlines them) — **Horror** = haunted map, **Sea** = archipelago map; discovery drives sealed/sunken styling for missing levels; theme from cookie |
| GET | `/level/{id}` | Dedicated, theme-styled level page (room / beach) |
| GET | `/api/levels` | Discovered levels + `available` flag (here `available` = the numbered folder exists) |
| GET | `/api/levels/{id}/photos` | Image refs for a level + fallback audio (here `available` = folder exists **and** is non-empty) |
| GET | `/api/levels/{id}/media/{file_id}` | Stream a single image's bytes from Drive (key stays server-side) |
| POST | `/api/refresh` | Rebuild the level-discovery cache |

> **Two-layer `available` semantics (QA-flagged):** in `/api/levels`, `available` means the numbered Drive folder *exists*; in `/api/levels/{id}/photos`, `available` means the folder exists **and** contains media. A level can therefore be listed as available yet still fall back to the `missing/` folder when its photos are requested.

Full design lives in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md), and [docs/PLAN.md](docs/PLAN.md).

### Project structure

```
island/
├── app/
│   ├── main.py            # routes, theme cookie, manifest-first discovery, gated background sync, Jinja2
│   ├── drive_service.py   # Drive client, manifest loader, paced downloader, child discovery, missing/ fallback
│   └── captions.json      # per-image dual-theme captions, keyed by (level, filename)
├── scripts/
│   └── fetch_images.py    # build-time image bake → static/img/levels/ + manifest.json (paced)
├── static/
│   ├── style.css          # .theme-horror / .theme-sea
│   ├── img/
│   │   ├── horror/        # landing-map.v2.jpg (Horror landing art)
│   │   ├── light/         # landing-map.v2.webp (Sea landing art; landing-map.png = design source)
│   │   ├── logo/          # brand asset
│   │   └── levels/        # ⚠️ build-generated, git-IGNORED — baked level photos + manifest.json (never committed)
│   └── audio/
│       ├── global/        # horror_ambient.mp3, sea_ambient.mp3
│       ├── horror/        # level_0.mp3 … level_18.mp3
│       └── sea/           # level_0.mp3 … level_18.mp3
├── templates/
│   ├── index.html         # landing: Haunted Map (Horror) ⇄ Archipelago Map (Sea)
│   └── level.html         # level page: room ⇄ beach by theme
├── docs/                  # REQUIREMENTS · ARCHITECTURE · PLAN
├── requirements.txt       # fastapi, uvicorn, jinja2, httpx
├── .env.example           # GD_API_KEY= , GD_ROOT_FOLDER=
└── render.yaml / Procfile
```

---

## ⚙️ Configuration

The app reads two environment variables (never commit the key):

| Variable | Type | Description |
|---|---|---|
| `GD_API_KEY` | **secret** | Google Drive API key. Read via `os.environ`; kept server-side only. |
| `GD_ROOT_FOLDER` | config | ID/link of the parent Drive folder whose children are the numbered subfolders `0..18` + `missing/`. |
| `IMAGE_SYNC_INTERVAL_SECONDS` | config | How often the background sync checks Drive for new/changed images (default **1800** = 30 min). **`0` or unset disables** the sync entirely — keep it unset locally / in CI so the suite stays hermetic. Set in `render.yaml` for prod. |

> The parent Drive folder must be shared **"Anyone with the link → Viewer"** so a plain API key can read it. Copy `.env.example` to `.env` and fill in your values.

---

## 🚀 Getting Started

```bash
# 1. Clone
git clone https://github.com/16ksayush/island.git
cd island

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure secrets (optional for a first run — see note below)
cp .env.example .env             # then fill in GD_API_KEY and GD_ROOT_FOLDER

# 5. Run the dev server
uvicorn app.main:app --reload
```

Open http://localhost:8000.

> **Level images (build-baked):** in production the images are baked into `static/img/levels/` at build time and served as static files. Locally this directory is **git-ignored and empty on a fresh clone** — the app still runs, falling back to the guarded Drive proxy for images. To bake them locally for static-parity (and to refresh after the Drive download throttle clears), run:
>
> ```bash
> python scripts/fetch_images.py        # paced download → static/img/levels/ + manifest.json
> ```
>
> This is the **same script** `render.yaml` runs in its `buildCommand`. New/changed images then flow in via the 30-min background sync (or `POST /api/refresh`) — no redeploy needed.

> The repo-root `.env` is **auto-loaded** at startup (via `python-dotenv`) — no manual
> `export` needed. Real environment variables always take precedence over `.env`, and a
> missing `.env` is a no-op (so CI and production, which set vars on the host, are unaffected).

> The app **starts and serves even with no `GD_API_KEY` / `GD_ROOT_FOLDER`** — level discovery simply degrades to an empty gallery (`/api/levels` returns `{"levels": []}`) and the page still renders with its theme. Set both env vars to load real Drive content.

### 🧪 Running tests

The suite is hermetic (Drive is fully mocked — no network, no real key):

```bash
pytest tests/            # 182 passed
# or, without activating the venv:
.venv/bin/python -m pytest tests/ -q
```

The same suite runs automatically in **GitHub Actions** on every push / PR to `main`
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)). Because the tests are hermetic,
CI needs no Drive credentials.

### ☁️ Deploying

Free-tier deploy config is committed: [`render.yaml`](render.yaml) (Render Blueprint) and [`Procfile`](Procfile) (Railway / Heroku-style). Start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Set `GD_API_KEY` (secret) and `GD_ROOT_FOLDER` (config) in the host dashboard — never in a committed file. Full steps below.

---

## 🌐 Deployment (Render / Railway)

Both platforms build from `requirements.txt` and run the start command above. The Drive parent folder must be shared **"Anyone with the link → Viewer"** so the API key can read it.

### Render (Blueprint via `render.yaml`)

1. Push this repo to GitHub.
2. In the Render dashboard: **New + → Blueprint**, select the repo. Render reads `render.yaml` and provisions a free `web` service with build `pip install -r requirements.txt` and the `uvicorn … --port $PORT` start command.
3. When prompted (both vars are declared `sync: false`), set **Environment** values:
   - `GD_API_KEY` — your Google Drive API key (secret).
   - `GD_ROOT_FOLDER` — the parent folder ID/link holding `0..18` + `missing/`.
4. Deploy. The build runs `python scripts/fetch_images.py` to **bake the level images** into `static/img/levels/` using the build-time `GD_API_KEY`/`GD_ROOT_FOLDER` (so the Drive folder must already be shared "Anyone with link → Viewer"). `IMAGE_SYNC_INTERVAL_SECONDS=1800` (declared in `render.yaml`) turns on the 30-min background sync so new images appear without a redeploy. Health check hits `/api/levels`. Visit the assigned `*.onrender.com` URL.

### Railway (`Procfile`)

1. **New Project → Deploy from GitHub repo**; Railway auto-detects Python and the `Procfile` `web:` process.
2. In **Variables**, add `GD_API_KEY` (secret) and `GD_ROOT_FOLDER` (config). Railway injects `$PORT` automatically.
3. Deploy and open the generated public domain.

> If env vars are omitted, the deploy still boots and serves an empty gallery (graceful degradation) — useful for verifying the deploy before wiring up Drive.

---

## 🤖 How this project is built (Claude Code)

This repo is engineered with [Claude Code](https://claude.com/claude-code) using a multi-agent workflow. Five engineering personas are implemented as **subagents** (`.claude/agents/`), coordinated by **skills** (`.claude/skills/`):

| Subagent | Role |
|---|---|
| 👔 `project-manager` | Init, roadmap, task checklists, deployment |
| 📐 `solutions-architect` | Route signatures, payloads, level → Drive-folder schema |
| ⚙️ `backend-engineer` | FastAPI/Uvicorn + httpx Drive proxy |
| 🎨 `frontend-engineer` | Semantic HTML, Tailwind grid, themes, audio engine |
| 🛡️ `security-engineer` | Credential isolation, `.gitignore` policy, per-file audit |
| 🧪 `qa-tester` | pytest + FastAPI TestClient (Drive mocked) + smoke checks |

**To build:** run the `orchestrate-build` skill (or ask the `project-manager` agent to start). It runs Phase 1 (Discovery & Blueprinting) and Phase 2 (Autonomous Execution) with explicit hand-offs. See [CLAUDE.md](CLAUDE.md) for the full blueprint.

---

## 📊 Project Status

Build is **complete** through M7 plus the M9 Horror / M10 Sea landing-map redesigns, the M11 dual-theme captions, and the M12 build-time image baking + background sync (full suite **182 passed**); deploy config is ready (M8 = live verification). Code uses placeholder Drive assets / `.mp3` files. Milestones:

- [x] **M0 — Discovery** — dual-theme PRD, requirements, architecture, and plan documented
- [x] **M1 — Scaffold & secure** — file tree, `requirements.txt`, `.env.example`, hardened `.gitignore`, audio tree
- [x] **M2 — Backend dynamic core** — `drive_service.py`, `main.py` routes + theme cookie
- [x] **M3 — Theme system** — `style.css`, global toggle, cookie + sessionStorage, SSR theme read
- [x] **M4 — Landing grid** — dynamic Corridor Grid ⇄ Island Map
- [x] **M5 — Level pages** — `/level/{id}` room/beach presentation + proxied images
- [x] **M6 — Audio engine** — per-theme ambient + per-level crossfade
- [x] **M7 — Harden, test & verify** — error handling, full pytest suite (58 passed, Drive mocked), local uvicorn smoke test
- [ ] **M8 — Deploy** — Render/Railway config committed (`render.yaml` / `Procfile`); live verification pending
- [x] **M9 — Horror landing redesign** — replaced the Horror door grid with a full-bleed illustrated haunted map; each of the 19 locations is a %-positioned clickable hotspot to `/level/{id}` (sealed styling for unavailable levels), plus drifting ghost/silhouette atmosphere. Supersedes the original "restyle-only / keep door grid" plan (HR3) and the pure-CSS approach (HQ1).
- [x] **M10 — Sea (Light) landing map** — replaced the Sea dynamic island grid with a full-bleed illustrated **archipelago map** (`static/img/light/landing-map.v2.webp`, 214 KB WebP), mirroring the M9 Horror treatment; all 19 island locations are %-positioned clickable hotspots to `/level/{id}` with sealed/sunken styling for unavailable levels and name-aware `aria-label`s ("Level 5 — Prison"). The old island-grid markup is deleted (no mobile grid fallback; pan-to-fit on mobile). Frontend-only — Horror landing, backend, routes, payloads, audio, and deploy config are byte-unchanged. **After M10, both themes are map-based.** Full suite 140 passed. (Supersedes M4's "Island Map/Grid" Sea layout.) *Follow-ups (2026-06-09): missing-level fallback audio is now a random local per-theme track (REQUIREMENTS §11); both landings have ambient border decorations — Horror drifting ghosts + twinkles + shooting stars, Sea balloons + gulls + clouds — all decorative (`aria-hidden`, `pointer-events:none`) and frozen under `prefers-reduced-motion`.*
- [x] **M11 — Image captions (dual-theme)** — every real gallery image (52 images across levels 1, 2, 8–18) gets two one-line captions (Sea funny-sweet + Horror playful-gothic = 104 total), shown per-slide in the level slideshow and selected by the active theme. Captions live in a committed `app/captions.json` keyed by `(level, filename)`, loaded by `app/captions.py` (startup-cached, re-read on `POST /api/refresh`); `main.py`'s `_ref` adds an optional, backward-compatible `caption:{sea,horror}` per image (omitted when absent → renders as before). `level.html` renders a theme-scoped `<figcaption class="slide-caption">` via `textContent` (no injection). Subject referred to as "Chudail" (no real name). Full suite 156 passed. Backend route/payload backward-compatible — M8 deploy unaffected.
- [x] **M12 — Build-time image baking + background sync** — level images are downloaded from Drive **once at build time** by `scripts/fetch_images.py` (paced — bounded concurrency + jittered delay + exp-backoff — to avoid Drive's `alt=media` download throttle) into `static/img/levels/{id}/{filename}` (filename preserved so M11 captions still match) plus a `manifest.json`; the app serves them as **static files** (`/api/levels/{id}/photos` `url` switches from the `/media/{file_id}` proxy path to `/static/img/levels/{id}/{filename}`, `file_id`+`name`+`caption` preserved). Discovery reads the manifest **PRIMARY** → Drive-metadata **FALLBACK** → empty-gallery, so a cold start makes zero Drive calls. The `/media` proxy is **kept as a guarded fallback** for not-yet-baked images. A periodic **background sync** (`IMAGE_SYNC_INTERVAL_SECONDS`, default 1800s; `0`/unset disables) checks Drive metadata every 30 min and paced-downloads only the delta on a change → new images without a redeploy; `POST /api/refresh` forces it. `static/img/levels/` is **git-ignored** (personal photos, build output only). The same script runs in `render.yaml`'s `buildCommand`. Full suite **182 passed** (Drive mocked, sync off in tests). Backend route/payload backward-compatible — M8 deploy unaffected beyond the additive `buildCommand` + env.

---

## 🔐 Security

- `GD_API_KEY` is read only from the environment and **never** leaves the server — it is used by the build-time bake script and the guarded proxy fallback only; it is never written to the static output, `manifest.json`, the API payload, the logs, or any client bundle.
- `.env` is git-ignored; only `.env.example` (with empty fill-in stubs) is committed.
- Every file is audited by the `security-engineer` agent before it is frozen.

---

## 📄 License

No license has been specified yet.
