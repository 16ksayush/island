"""FastAPI application for Archive 19 — Dual-Atmosphere Dynamic Gallery.

Implements docs/ARCHITECTURE.md §3 / §4 / §4.1:

- SSR routes ``/`` (index.html) and ``/level/{id}`` (level.html), each reading
  the ``theme`` cookie (default ``horror`` — D3) and passing it to Jinja2.
- JSON API: ``/api/levels`` (id + availability), ``/api/levels/{id}/photos``
  (proxied image refs + fallback audio), and ``/api/refresh`` (rebuild the
  discovery cache — R2).
- Media proxy ``/api/levels/{id}/media/{file_id}`` returns Drive bytes (served
  from an in-memory LRU byte cache when warm) echoing the upstream Content-Type
  (R6) AFTER validating the file id is in scope for the level (R1), with
  browser-cache headers (immutable + ETag) since file ids are immutable.

Security: the Drive API key never reaches the client — only ``file_id`` values
and proxied media URLs do. The app imports and starts even when GD_API_KEY /
GD_ROOT_FOLDER are unset or Drive is unreachable (discovery degrades to empty).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import drive_service
from app.drive_service import DriveError

logger = logging.getLogger("archive19.main")

# --- Paths (static/ + templates/ live at the repo root, per PRD §7) --------
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# --- Local .env auto-load (convenience for local dev only) -----------------
# Loads GD_API_KEY / GD_ROOT_FOLDER from a repo-root .env so `uvicorn app.main:app`
# works without a manual `export`. override=False means real environment vars
# (Render dashboard, CI dummies, an exported shell var) always take precedence,
# and a missing .env (e.g. in CI/prod) is a silent no-op. python-dotenv is
# optional — the app still runs on real env vars if it isn't installed.
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env", override=False)
except ImportError:
    pass

DEFAULT_THEME = "horror"  # D3
VALID_THEMES = {"horror", "sea"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the discovery cache once at startup (R2).

    Never crash on a failed discovery — the app must still serve pages so that
    local runs and tests work without live Drive access.
    """
    try:
        await drive_service.discover_levels(force=True)
    except Exception as exc:  # defensive: discovery must never block startup
        logger.warning("Startup discovery did not complete: %s", type(exc).__name__)
    yield


app = FastAPI(title="Archive 19 — Dynamic Gallery", lifespan=lifespan)

# Mount static assets (audio + style.css). Created lazily so import never fails.
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# --- Helpers ---------------------------------------------------------------
def read_theme(request: Request) -> str:
    """Read the ``theme`` cookie, defaulting to ``horror`` (D3).

    The server only READS the cookie; the client owns writing it (D1).
    """
    theme = request.cookies.get("theme", DEFAULT_THEME)
    return theme if theme in VALID_THEMES else DEFAULT_THEME


def _levels_payload() -> list[dict]:
    """Build the ``levels`` list (id + availability) from the cache."""
    cache = drive_service.get_cache()
    return [
        {"id": level_id, "available": level_id in cache.folder_index}
        for level_id in cache.levels
    ]


# --- SSR routes ------------------------------------------------------------
@app.get("/")
def index(request: Request):
    """Landing page: dynamic grid sized to the discovered levels + theme."""
    theme = read_theme(request)
    return templates.TemplateResponse(
        request,
        "index.html",
        {"theme": theme, "levels": _levels_payload()},
    )


@app.get("/level/{level_id}")
def level_page(request: Request, level_id: int):
    """Dedicated per-level page (room/beach by theme)."""
    theme = read_theme(request)
    cache = drive_service.get_cache()
    available = level_id in cache.folder_index
    return templates.TemplateResponse(
        request,
        "level.html",
        {
            "theme": theme,
            "level_id": level_id,
            "available": available,
        },
    )


# --- JSON API --------------------------------------------------------------
@app.get("/api/levels")
def list_levels():
    """Return the configured levels and their availability flag (§4.1)."""
    return {"levels": _levels_payload()}


@app.get("/api/levels/{level_id}/photos")
async def level_photos(level_id: int):
    """Return proxied image refs for a level (+ fallback audio when missing).

    Unknown level id (outside the discovered span) -> 404. Upstream Drive
    failure -> 502. Image elements are objects (``file_id`` + proxied ``url``),
    never bare Drive URLs (key isolation).
    """
    cache = drive_service.get_cache()
    if level_id not in cache.levels:
        return JSONResponse({"detail": "Unknown level."}, status_code=404)

    try:
        result = await drive_service.get_level_photos(level_id)
    except DriveError:
        return JSONResponse({"detail": "Upstream Drive error."}, status_code=502)

    def _ref(photo) -> dict:
        return {
            "file_id": photo.file_id,
            "url": f"/api/levels/{level_id}/media/{photo.file_id}",
        }

    payload = {
        "level": result.level,
        "available": result.available,
        "images": [_ref(p) for p in result.images],
        "fallback_audio": _ref(result.fallback_audio)
        if result.fallback_audio
        else None,
    }
    return payload


@app.get("/api/levels/{level_id}/media/{file_id}")
async def media_proxy(level_id: int, file_id: str):
    """Return a single Drive file's bytes, scoped to ``level_id`` (R1/R6).

    The file id MUST belong to the level's folder or ``missing/`` (validated in
    ``resolve_media`` against the cached scope set) — otherwise 404, no open
    proxy. Bytes are served from the in-memory media cache when warm, else
    fetched once from Drive and cached. The response Content-Type mirrors the
    upstream Drive value (R6: image/* vs audio/mpeg, never hardcoded).

    Drive file ids are immutable, so the response is marked cacheable for a day
    (``Cache-Control: public, max-age=86400, immutable``) with the ``file_id``
    as a strong ``ETag`` to let browsers revalidate cheaply.
    """
    try:
        result = await drive_service.resolve_media(level_id, file_id)
    except DriveError:
        return JSONResponse({"detail": "Upstream Drive error."}, status_code=502)

    if result is None:
        return JSONResponse({"detail": "Media not found."}, status_code=404)

    content_type, body = result
    headers = {
        "Cache-Control": "public, max-age=86400, immutable",
        "ETag": f'"{file_id}"',
    }
    return Response(content=body, media_type=content_type, headers=headers)


@app.post("/api/refresh")
async def refresh():
    """Manually rebuild the discovery cache without a redeploy (R2).

    A forced rediscovery also rebuilds the scope/list cache and clears the
    in-memory media byte cache (both done inside ``discover_levels(force=True)``)
    so a Drive change takes full effect — no stale bytes or stale scope.
    """
    cache = await drive_service.discover_levels(force=True)
    return {
        "ready": cache.ready,
        "levels": len(cache.levels),
        "available": sorted(cache.folder_index.keys()),
        "missing_folder": cache.missing_folder_id is not None,
    }
