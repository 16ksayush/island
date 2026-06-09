# 🗝️ Archive 19 — Dual-Atmosphere Dynamic Gallery

An interactive web gallery with a **dynamically-scaled** number of levels (0 → up to 18), presented through **two distinct, toggleable realities**. The chosen theme persists across the whole session and can be switched from any page.

| THEME A — 🕯️ Horror | THEME B — 🏝️ Sea & Island |
|---|---|
| Illustrated **haunted map** — numbered destinations / doorways across an eerie landscape (clickable hotspots) | Illustrated **archipelago map** — sunlit islands across an open ocean (clickable hotspots) |
| `#0D0D0D` obsidian + `#FFB000` molten amber, shadowed vignette | `#E0F2FE`/`#0284C7` azures + warm sand, white coral, palm green |
| Continuous atmospheric horror soundtrack | Bright, relaxing ocean/acoustic ambient |

> **Status:** ✅ Implemented. The backend (FastAPI + **Cloudinary CDN** image source), frontend (SSR Jinja2 + dual themes + audio engine), and the full test suite (**163 passed**) are complete and security-audited. Both landings are illustrated maps with clickable hotspots (M9 Horror, M10 Sea); images are now hosted on **Cloudinary** and served straight from its **keyless public CDN** — one server-side Admin API list discovers what exists (refreshed every 30 min), and the browser loads each image directly from `res.cloudinary.com` with no proxy and no per-request external fetch (M13, supersedes the M12 Drive build-bake). Deploy config (`render.yaml` / `Procfile`) is ready; live deployment (M8) is the remaining step. See [Project Status](#-project-status). *(Note: the `.mp3` audio files are still placeholders.)*

---

## ✨ Features

- **Dual, toggleable themes** — Horror and Sea & Island, swapped from a control on *every* page.
- **Session-persistent theme** — stored via cookie + `sessionStorage`; SSR reads the cookie for a flash-free first paint (default: Horror).
- **Dynamic level discovery** — both landing maps render a fixed illustrated layout of 19 numbered hotspots; discovery of whatever numbered folders exist on Cloudinary (under `all ages/{N}`; 5, 12, 19… all work) drives each hotspot's **availability** styling (sealed/sunken for missing levels), not the layout itself.
- **Per-level pages** at `/level/{id}`, styled as a *room* (Horror) or a *beach* (Sea).
- **Cloudinary CDN images** — level images live in a Cloudinary account (folders `all ages/{N}`). The server makes **one Admin API list** (metadata only) to discover what exists, then hands the browser **keyless public CDN URLs** (`https://res.cloudinary.com/{cloud}/image/upload/f_auto,q_auto/{public_id}.{format}`). There is **no per-request external fetch** and no proxy — Cloudinary's CDN serves the bytes — and the Admin `api_secret` **never** reaches the browser, payload, or logs.
- **Background image re-list** — a periodic background task re-runs the Cloudinary Admin list (metadata only — no byte download) every 30 min (`IMAGE_SYNC_INTERVAL_SECONDS`, default 1800; `0`/unset disables it) and atomically swaps the discovery cache, so new images appear **without a redeploy**. `POST /api/refresh` forces an immediate re-list.
- **Missing-level fallback** — if a numbered folder is absent (or empty), the backend serves 1 random image from the Cloudinary `all ages/missing` pool; the level's audio is a random **local per-theme track** (`static/audio/{theme}/`) chosen client-side, so a missing level never fails over absent audio.
- **Per-image dual-theme captions** — every real gallery image carries two one-line captions (Sea = light & funny, Horror = playful-gothic); the active theme selects which one shows, rendered per-slide beneath the slideshow image. Captions live in a committed `app/captions.json` (keyed by the image **filename stem**) and are optional/back-compatible — an image with no caption renders exactly as before. Subject is referred to as "Chudail" (no real name).
- **Audio crossfade engine** — landing-page global ambient fades out while a per-level track fades in (and back), auto-play-safe.
- **Fast by default** — level images are served **directly from Cloudinary's CDN** (no proxy, no per-request external fetch on the hot path), with Cloudinary's own edge caching and optional `f_auto,q_auto` (automatic format + quality) delivery. Discovery reads an in-memory cache populated by the startup Admin list, so a cold start makes **one** Admin call (and zero per request thereafter). The level page shows a slow, scrollable **slideshow** (3s/slide) and the landing page **prefetches** all level images in the background, so navigation is near-instant after first load.

---

## 🧱 Tech Stack

| Layer | Technology |
|---|---|
| Backend | **FastAPI** + **Uvicorn**, **Jinja2** SSR, **httpx** (Cloudinary Admin API client) |
| Frontend | Semantic HTML5, **Tailwind CDN** + custom `style.css` (`.theme-horror` / `.theme-sea`), native `<audio>` |
| Media | Images → **Cloudinary** (server-side Admin list for discovery; browser loads keyless `res.cloudinary.com` CDN URLs directly); audio → **GitHub repo** (`static/audio/`, served static) |
| Hosting | Render / Railway (free tier), secrets via environment variables |

---

## 🏛️ Architecture (overview)

```
Browser (Horror = illustrated haunted map w/ hotspots · Sea = illustrated archipelago map w/ hotspots)
   │  GET /level/{id}  (SSR page)          │  GET /api/levels/{id}/photos
   ▼                                        ▼
FastAPI (app/main.py) ── reads theme cookie ── renders level.html
   │
   ▼ app/cloudinary_service.py ──CLOUDINARY_URL api_secret (os.environ, server-side ONLY)──►
        Cloudinary Admin API  (ONE list at startup; re-listed every 30 min)
        • list resources under `all ages/` → discover which levels exist (dynamic scaling)
        • folder `all ages/{N}` present → its images  → keyless CDN URLs
        • folder `all ages/{N}` ABSENT  → 1 random image from `all ages/missing`;
                                          audio = random local per-theme track
   ▼  /api/levels/{id}/photos returns absolute keyless URLs
Browser loads image bytes DIRECTLY from https://res.cloudinary.com/{cloud}/image/upload/
   f_auto,q_auto/{public_id}.{fmt} — no proxy, no per-request server fetch, no credential.
Audio loads from /static/audio/...  (no external call, no key).
```

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Landing page; **both themes** = full-bleed illustrated map with 19 %-positioned clickable hotspots (`?calibrate` outlines them) — **Horror** = haunted map, **Sea** = archipelago map; discovery drives sealed/sunken styling for missing levels; theme from cookie |
| GET | `/level/{id}` | Dedicated, theme-styled level page (room / beach) |
| GET | `/api/levels` | Discovered levels + `available` flag (here `available` = the numbered folder exists) |
| GET | `/api/levels/{id}/photos` | Image refs for a level (each with an absolute keyless Cloudinary CDN `url`) + fallback audio (here `available` = folder exists **and** is non-empty) |
| POST | `/api/refresh` | Re-run the Cloudinary Admin list and rebuild the level-discovery cache |

> **Two-layer `available` semantics (QA-flagged):** in `/api/levels`, `available` means the numbered folder *exists* on Cloudinary; in `/api/levels/{id}/photos`, `available` means the folder exists **and** contains media. A level can therefore be listed as available yet still fall back to the `all ages/missing` pool when its photos are requested.

Full design lives in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md), and [docs/PLAN.md](docs/PLAN.md).

### Project structure

```
island/
├── app/
│   ├── main.py                # routes, theme cookie, Cloudinary-backed discovery, gated background re-list, Jinja2
│   ├── cloudinary_service.py  # Cloudinary Admin API list (metadata), discovery cache, keyless CDN URL builder, missing fallback
│   ├── captions.py            # loads/caches app/captions.json (keyed by filename stem)
│   └── captions.json          # per-image dual-theme captions, keyed by filename stem
├── static/
│   ├── style.css          # .theme-horror / .theme-sea
│   ├── img/
│   │   ├── horror/        # landing-map.v2.jpg (Horror landing art)
│   │   ├── light/         # landing-map.v2.webp (Sea landing art; landing-map.png = design source)
│   │   └── logo/          # brand asset
│   └── audio/
│       ├── global/        # horror_ambient.mp3, sea_ambient.mp3
│       ├── horror/        # level_0.mp3 … level_18.mp3
│       └── sea/           # level_0.mp3 … level_18.mp3
├── templates/
│   ├── index.html         # landing: Haunted Map (Horror) ⇄ Archipelago Map (Sea)
│   └── level.html         # level page: room ⇄ beach by theme
├── docs/                  # REQUIREMENTS · ARCHITECTURE · PLAN
├── requirements.txt       # fastapi, uvicorn, jinja2, httpx, python-dotenv
├── .env.example           # CLOUDINARY_URL= , IMAGE_SYNC_INTERVAL_SECONDS=
└── render.yaml / Procfile
```

---

## ⚙️ Configuration

The app reads two environment variables (never commit the secret):

| Variable | Type | Description |
|---|---|---|
| `CLOUDINARY_URL` | **secret** | Cloudinary connection string `cloudinary://<api_key>:<api_secret>@<cloud_name>` (the standard Cloudinary SDK var). Read via `os.environ`; the `api_secret` is used **only** server-side for the Admin API (HTTP basic auth) to list image metadata — it is never logged, committed, or sent to the browser. Image **delivery** is keyless (public `res.cloudinary.com` CDN), so the browser never sees a credential. |
| `IMAGE_SYNC_INTERVAL_SECONDS` | config | How often the background task re-runs the Cloudinary Admin list (metadata only — no byte download) to pick up new/changed images (default **1800** = 30 min). **`0` or unset disables** the re-list entirely — keep it unset locally / in CI so the suite stays hermetic. Set in `render.yaml` for prod. |

> Image bytes are served by Cloudinary's public CDN, so no folder-sharing setup is needed — only the `CLOUDINARY_URL` secret. Copy `.env.example` to `.env` and fill in your value.

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
cp .env.example .env             # then fill in CLOUDINARY_URL

# 5. Run the dev server
uvicorn app.main:app --reload
```

Open http://localhost:8000.

> **Level images (Cloudinary CDN):** images live in a Cloudinary account under `all ages/{N}`. At startup the app makes **one** Admin API list (metadata only) to discover what exists, then the browser loads each image straight from Cloudinary's keyless public CDN. There is no build-time bake and no local image directory — a fresh clone with a valid `CLOUDINARY_URL` works immediately. New/changed images flow in via the 30-min background re-list (or `POST /api/refresh`) — no redeploy needed.

> The repo-root `.env` is **auto-loaded** at startup (via `python-dotenv`) — no manual
> `export` needed. Real environment variables always take precedence over `.env`, and a
> missing `.env` is a no-op (so CI and production, which set vars on the host, are unaffected).

> The app **starts and serves even with no `CLOUDINARY_URL`** — level discovery simply degrades to an empty gallery (`/api/levels` returns `{"levels": []}`) and the page still renders with its theme. Set `CLOUDINARY_URL` to load real image content.

### 🧪 Running tests

The suite is hermetic (the Cloudinary Admin API is fully mocked — no network, no real secret):

```bash
pytest tests/            # 163 passed
# or, without activating the venv:
.venv/bin/python -m pytest tests/ -q
```

The suite mocks the Cloudinary Admin API (no network, no real secret). The same suite runs
automatically in **GitHub Actions** on every push / PR to `main`
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)). Because the tests are hermetic,
CI needs no Cloudinary credentials.

### ☁️ Deploying

Free-tier deploy config is committed: [`render.yaml`](render.yaml) (Render Blueprint) and [`Procfile`](Procfile) (Railway / Heroku-style). Start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Set `CLOUDINARY_URL` (secret) in the host dashboard — never in a committed file. Full steps below.

---

## 🌐 Deployment (Render / Railway)

Both platforms build from `requirements.txt` (just `pip install`) and run the start command above. No folder-sharing or build-time bake is needed — image bytes are served by Cloudinary's public CDN; the server only needs `CLOUDINARY_URL` to list metadata.

### Render (Blueprint via `render.yaml`)

1. Push this repo to GitHub.
2. In the Render dashboard: **New + → Blueprint**, select the repo. Render reads `render.yaml` and provisions a free `web` service (region **singapore**) with build `pip install -r requirements.txt` and the `uvicorn … --port $PORT` start command.
3. When prompted (`CLOUDINARY_URL` is declared `sync: false`), set the **Environment** value:
   - `CLOUDINARY_URL` — your Cloudinary connection string `cloudinary://<api_key>:<api_secret>@<cloud_name>` (secret). The `api_secret` is used server-side only for the Admin list; image delivery is keyless.
4. Deploy. The build is just `pip install -r requirements.txt` (no bake step). At startup the app makes one Cloudinary Admin list; `IMAGE_SYNC_INTERVAL_SECONDS=1800` (declared in `render.yaml`) re-lists metadata every 30 min so new images appear without a redeploy. Health check hits `/api/levels`. Visit the assigned `*.onrender.com` URL.

### Railway (`Procfile`)

1. **New Project → Deploy from GitHub repo**; Railway auto-detects Python and the `Procfile` `web:` process.
2. In **Variables**, add `CLOUDINARY_URL` (secret). Railway injects `$PORT` automatically.
3. Deploy and open the generated public domain.

> If `CLOUDINARY_URL` is omitted, the deploy still boots and serves an empty gallery (graceful degradation) — useful for verifying the deploy before wiring up Cloudinary.

---

## 🤖 How this project is built (Claude Code)

This repo is engineered with [Claude Code](https://claude.com/claude-code) using a multi-agent workflow. Five engineering personas are implemented as **subagents** (`.claude/agents/`), coordinated by **skills** (`.claude/skills/`):

| Subagent | Role |
|---|---|
| 👔 `project-manager` | Init, roadmap, task checklists, deployment |
| 📐 `solutions-architect` | Route signatures, payloads, level → image-source schema |
| ⚙️ `backend-engineer` | FastAPI/Uvicorn + httpx Cloudinary Admin client |
| 🎨 `frontend-engineer` | Semantic HTML, Tailwind grid, themes, audio engine |
| 🛡️ `security-engineer` | Credential isolation, `.gitignore` policy, per-file audit |
| 🧪 `qa-tester` | pytest + FastAPI TestClient (Cloudinary mocked) + smoke checks |

**To build:** run the `orchestrate-build` skill (or ask the `project-manager` agent to start). It runs Phase 1 (Discovery & Blueprinting) and Phase 2 (Autonomous Execution) with explicit hand-offs. See [CLAUDE.md](CLAUDE.md) for the full blueprint.

---

## 📊 Project Status

Build is **complete** through M7 plus the M9 Horror / M10 Sea landing-map redesigns, the M11 dual-theme captions, and the M13 **Cloudinary image source** (which supersedes the M12 Drive build-bake) — full suite **163 passed**; deploy config is ready (M8 = live verification, now just needs `CLOUDINARY_URL`). The `.mp3` audio files are still placeholders. Milestones:

- [x] **M0 — Discovery** — dual-theme PRD, requirements, architecture, and plan documented
- [x] **M1 — Scaffold & secure** — file tree, `requirements.txt`, `.env.example`, hardened `.gitignore`, audio tree
- [x] **M2 — Backend dynamic core** — `drive_service.py`, `main.py` routes + theme cookie
- [x] **M3 — Theme system** — `style.css`, global toggle, cookie + sessionStorage, SSR theme read
- [x] **M4 — Landing grid** — dynamic Corridor Grid ⇄ Island Map
- [x] **M5 — Level pages** — `/level/{id}` room/beach presentation + proxied images
- [x] **M6 — Audio engine** — per-theme ambient + per-level crossfade
- [x] **M7 — Harden, test & verify** — error handling, full pytest suite (58 passed, Drive mocked), local uvicorn smoke test
- [ ] **M8 — Deploy** — Render/Railway config committed (`render.yaml` / `Procfile`); live verification pending. **After M13 this just needs `CLOUDINARY_URL` set in the host dashboard** — no Google Drive vars, no build-time bake.
- [x] **M9 — Horror landing redesign** — replaced the Horror door grid with a full-bleed illustrated haunted map; each of the 19 locations is a %-positioned clickable hotspot to `/level/{id}` (sealed styling for unavailable levels), plus drifting ghost/silhouette atmosphere. Supersedes the original "restyle-only / keep door grid" plan (HR3) and the pure-CSS approach (HQ1).
- [x] **M10 — Sea (Light) landing map** — replaced the Sea dynamic island grid with a full-bleed illustrated **archipelago map** (`static/img/light/landing-map.v2.webp`, 214 KB WebP), mirroring the M9 Horror treatment; all 19 island locations are %-positioned clickable hotspots to `/level/{id}` with sealed/sunken styling for unavailable levels and name-aware `aria-label`s ("Level 5 — Prison"). The old island-grid markup is deleted (no mobile grid fallback; pan-to-fit on mobile). Frontend-only — Horror landing, backend, routes, payloads, audio, and deploy config are byte-unchanged. **After M10, both themes are map-based.** Full suite 140 passed. (Supersedes M4's "Island Map/Grid" Sea layout.) *Follow-ups (2026-06-09): missing-level fallback audio is now a random local per-theme track (REQUIREMENTS §11); both landings have ambient border decorations — Horror drifting ghosts + twinkles + shooting stars, Sea balloons + gulls + clouds — all decorative (`aria-hidden`, `pointer-events:none`) and frozen under `prefers-reduced-motion`.*
- [x] **M11 — Image captions (dual-theme)** — every real gallery image (52 images across levels 1, 2, 8–18) gets two one-line captions (Sea funny-sweet + Horror playful-gothic = 104 total), shown per-slide in the level slideshow and selected by the active theme. Captions live in a committed `app/captions.json` keyed by `(level, filename)`, loaded by `app/captions.py` (startup-cached, re-read on `POST /api/refresh`); `main.py`'s `_ref` adds an optional, backward-compatible `caption:{sea,horror}` per image (omitted when absent → renders as before). `level.html` renders a theme-scoped `<figcaption class="slide-caption">` via `textContent` (no injection). Subject referred to as "Chudail" (no real name). Full suite 156 passed. Backend route/payload backward-compatible — M8 deploy unaffected.
- [x] **M12 — Build-time image baking + background sync** — level images are downloaded from Drive **once at build time** by `scripts/fetch_images.py` (paced — bounded concurrency + jittered delay + exp-backoff — to avoid Drive's `alt=media` download throttle) into `static/img/levels/{id}/{filename}` (filename preserved so M11 captions still match) plus a `manifest.json`; the app serves them as **static files** (`/api/levels/{id}/photos` `url` switches from the `/media/{file_id}` proxy path to `/static/img/levels/{id}/{filename}`, `file_id`+`name`+`caption` preserved). Discovery reads the manifest **PRIMARY** → Drive-metadata **FALLBACK** → empty-gallery, so a cold start makes zero Drive calls. The `/media` proxy is **kept as a guarded fallback** for not-yet-baked images. A periodic **background sync** (`IMAGE_SYNC_INTERVAL_SECONDS`, default 1800s; `0`/unset disables) checks Drive metadata every 30 min and paced-downloads only the delta on a change → new images without a redeploy; `POST /api/refresh` forces it. `static/img/levels/` is **git-ignored** (personal photos, build output only). The same script runs in `render.yaml`'s `buildCommand`. Full suite **182 passed** (Drive mocked, sync off in tests). Backend route/payload backward-compatible — M8 deploy unaffected beyond the additive `buildCommand` + env. *(Superseded by M13: the entire Drive source + build-bake is replaced by Cloudinary.)*
- [x] **M13 — Google Drive → Cloudinary image-source migration** — the image source is now **Cloudinary** (`app/cloudinary_service.py`). One server-side Admin API list (metadata only) discovers what exists under `all ages/{N}` and caches it; the browser then loads each image straight from Cloudinary's **keyless public CDN** (`https://res.cloudinary.com/{cloud}/image/upload/f_auto,q_auto/{public_id}.{format}`). There is **no per-request external fetch and no proxy**, so the Drive `alt=media` download throttle problem is gone for good. The Drive `/api/levels/{id}/media/{file_id}` proxy, `resolve_media`, byte LRU, the M12 build-bake (`scripts/fetch_images.py`), and `app/drive_service.py` are **removed**. `CLOUDINARY_URL` (secret; the `api_secret` stays server-side and never reaches the payload/logs/browser) replaces `GD_API_KEY`/`GD_ROOT_FOLDER`; a 30-min background **re-list** (`IMAGE_SYNC_INTERVAL_SECONDS=1800`) picks up new images, `POST /api/refresh` forces it. Captions are re-keyed to filename **stems** (`app/captions.json`/`app/captions.py`). `render.yaml` build is just `pip install -r requirements.txt` (region singapore). Missing-level fallback now draws from `all ages/missing`. Full suite **163 passed** (Cloudinary Admin API mocked, hermetic). Backend payload backward-compatible (`url` is now an absolute keyless CDN URL) — M8 deploy now needs only `CLOUDINARY_URL`. Supersedes M12 and the Drive parts of M8. *(Real Cloudinary assets wired up; `.mp3` audio still placeholder.)*

---

## 🔐 Security

- `CLOUDINARY_URL` is read only from the environment and **never** leaves the server — its `api_secret` is used only for the server-side Cloudinary Admin API (HTTP basic auth) to list image metadata; it is never written to the API payload, the logs, or any client bundle. Image **delivery** is keyless: the browser loads public `res.cloudinary.com` CDN URLs that carry no credential.
- `.env` is git-ignored; only `.env.example` (with empty fill-in stubs) is committed.
- Every file is audited by the `security-engineer` agent before it is frozen.

---

## 📄 License

No license has been specified yet.
