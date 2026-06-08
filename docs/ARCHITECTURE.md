# Architecture — Archive 19: Dual-Atmosphere Dynamic Gallery

Status: **Design locked** (pending asset data). FastAPI + Jinja2 SSR, dual-theme, dynamic level count.

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
        • numbered folder {id} present → list its images
        • numbered folder {id} ABSENT  → 1 random image from `missing/`  (audio fallback is LOCAL, see §6)
   ▼
Browser proxies image bytes via /api/levels/{id}/media/{file_id}; never sees the key.
Audio is loaded directly from /static/audio/... (no Drive, no key).
```

## 3. Endpoints
| Method | Path | Purpose | Response |
|---|---|---|---|
| GET | `/` | Landing page; dynamic grid sized to configured levels; theme from cookie. | HTML (`index.html`) |
| GET | `/level/{id}` | Dedicated level page; theme-styled (room/beach). | HTML (`level.html`) |
| GET | `/api/levels` | Configured levels + availability flag (real vs missing-fallback). | `[{ "id": 0, "available": true }, ...]` |
| GET | `/api/levels/{id}/photos` | Image refs for a level (proxied URLs back to our media endpoint). | `{ "level": 3, "available": false, "images": [...] }` |
| GET | `/api/levels/{id}/media/{file_id}` | Proxy/stream a single image's bytes from Drive. | image/* |
| GET (static) | `/static/audio/global/{theme}_ambient.mp3` | Landing ambient per theme. | audio/mpeg |
| GET (static) | `/static/audio/level_tracks/level_{id}.mp3` | Per-level track. | audio/mpeg |

## 4. Dynamic level + missing handling (drive_service.py)
- Source of truth: the **children of `GD_ROOT_FOLDER`**. List them once → the numeric-named folders define which levels exist (dynamic scaling). The grid renders exactly those; gaps still render a door/island flagged `available: false`.
- **Confirmed real structure** (parent folder `all ages`, name changeable): present folders `1, 2, 8–18`; **absent** `0, 3, 4, 5, 6, 7` → these resolve via the missing fallback. Images named `{n}.{i}.jpeg` but fetched by Drive file ID, so naming is irrelevant to the code.

> ## ⚠️ CRITICAL — Drive access method
> A plain `GD_API_KEY` (Google API key) can read **only publicly-shared** Drive files via the Drive API v3 (`files.list` with `'<folderId>' in parents`, then `files.get?alt=media`). Therefore the `all ages` parent folder (and its children) **must be shared "Anyone with the link → Viewer."** If the content must stay private, the API-key approach won't work and we'd need an OAuth2 **service-account JSON** instead (different secret, different client). This choice gates the backend implementation.
- Absent numbered folder → list the Drive `missing/` folder (which holds stock images **and** stock audio) and return **1 random image + 1 random audio**, both proxied through the media endpoint.
- `GD_ROOT_FOLDER` is data (config); `GD_API_KEY` is the only secret. The parent folder is shared "Anyone with link → Viewer".

## 5. Audio (GitHub-hosted, per-theme) + crossfade engine
- All audio served as static files from `static/audio/` — no Drive, no API key.
- Landing: loop `global/{theme}_ambient.mp3`.
- Level page (existing level): play `static/audio/{theme}/level_{id}.mp3` (Horror and Sea have distinct tracks).
- Level page (missing level): use the random fallback audio served by the backend from the Drive `missing/` folder (proxied), not a local file.
- Crossfade: navigating into `/level/{id}` fades the global ambient **out** while fading the level track **in** (no clashing lines); reverse on return.
- Defensive auto-play handling: resume/start on first user gesture; fail silently if blocked.

## 6. Project structure
```
island/
├── app/
│   ├── __init__.py
│   ├── main.py            # routes, theme cookie, dynamic level loop, Jinja2
│   └── drive_service.py   # Drive client under GD_ROOT_FOLDER, child discovery, missing/ image fallback (httpx, os.environ key)
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
├── docs/
├── requirements.txt       # fastapi, uvicorn, jinja2, httpx
├── .env.example           # GD_API_KEY= , GD_ROOT_FOLDER=
├── .gitignore
└── render.yaml / Procfile
```
Note: `static/` and `templates/` sit at the repo root (per PRD), not under `app/`. Audio (`static/audio/`) is committed to git; only `.env` (the key) is ignored.
