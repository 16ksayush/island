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
