"""FastAPI application for Archive 19 — Dual-Atmosphere Dynamic Gallery.

Implements docs/ARCHITECTURE.md §3 / §4 / §4.1, updated for M13 (Cloudinary):

- SSR routes ``/`` (index.html) and ``/level/{id}`` (level.html), each reading
  the ``theme`` cookie (default ``horror`` — D3) and passing it to Jinja2.
- JSON API: ``/api/levels`` (id + availability) and ``/api/levels/{id}/photos``
  (image refs + null fallback audio), plus ``/api/refresh`` (re-list Cloudinary
  + reload captions — R2).

M13 image source: images live in Cloudinary and are served straight from its
**keyless public CDN** (``https://res.cloudinary.com/...``). The server uses the
Cloudinary Admin API ONCE (metadata) to discover what exists; each photo's
``url`` is an absolute CDN link, so there is NO per-request proxy and NO byte
download. The Cloudinary ``api_secret`` never reaches the client — only the
public ``public_id`` and keyless CDN URLs do. Per-level audio remains LOCAL
static files (``static/audio/{theme}/``, §11). The app imports + starts even
when ``CLOUDINARY_URL`` is unset (discovery degrades to an empty gallery).
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import captions, cloudinary_service

logger = logging.getLogger("archive19.main")

# --- Paths (static/ + templates/ live at the repo root, per PRD §7) --------
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# --- Local .env auto-load (convenience for local dev only) -----------------
# Loads CLOUDINARY_URL (and IMAGE_SYNC_INTERVAL_SECONDS) from a repo-root .env so
# `uvicorn app.main:app` works without a manual `export`. override=False means
# real environment vars (Render dashboard, CI dummies, an exported shell var)
# always take precedence, and a missing .env (CI/prod) is a silent no-op.
# python-dotenv is optional — the app still runs on real env vars if absent.
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env", override=False)
except ImportError:
    pass

DEFAULT_THEME = "horror"  # D3
VALID_THEMES = {"horror", "sea"}


def _image_sync_interval() -> int:
    """Read ``IMAGE_SYNC_INTERVAL_SECONDS``. 0/unset/invalid -> 0 (disabled).

    A return of 0 means the periodic background re-list is DISABLED — the task is
    never created, so local dev, CI, and the pytest suite never poll Cloudinary
    (hermetic). Render sets a positive value (e.g. 1800) to enable it.
    """
    raw = os.environ.get("IMAGE_SYNC_INTERVAL_SECONDS", "")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 0
    return value if value > 0 else 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Discover Cloudinary once at startup + start the gated background re-list.

    Discovery is one Admin API list (metadata only); a missing/invalid
    ``CLOUDINARY_URL`` or any API error degrades to an empty gallery and never
    crashes startup. Captions are loaded once here too.

    When ``IMAGE_SYNC_INTERVAL_SECONDS > 0`` AND ``CLOUDINARY_URL`` is set, a
    single ``asyncio`` background re-list task is started and cancelled cleanly
    on shutdown. With 0/unset/invalid OR no creds the task is NEVER created
    (hermetic local/CI/tests).
    """
    try:
        await cloudinary_service.discover(force=True)
    except Exception as exc:  # defensive: discovery must never block startup
        logger.warning("Startup discovery did not complete: %s", type(exc).__name__)
    # Load image captions once (§11.2). Tolerant — a missing/malformed
    # app/captions.json degrades to an empty map and never raises.
    captions.load_captions()

    sync_task: asyncio.Task | None = None
    interval = _image_sync_interval()
    creds_present = bool(os.environ.get("CLOUDINARY_URL"))
    if interval > 0 and creds_present:
        logger.info("Background image re-list ENABLED: every %ds.", interval)
        sync_task = asyncio.create_task(
            cloudinary_service.background_sync_loop(interval)
        )
    else:
        logger.info(
            "Background image re-list DISABLED (interval=%d, creds=%s).",
            interval,
            creds_present,
        )

    try:
        yield
    finally:
        if sync_task is not None:
            sync_task.cancel()
            try:
                await sync_task
            except asyncio.CancelledError:
                pass


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
    cache = cloudinary_service.get_cache()
    return [
        {"id": level_id, "available": level_id in cache.folder_index}
        for level_id in cache.levels
    ]


def _local_audio_ids(theme: str) -> list[int]:
    """Level ids with a local per-theme track in ``static/audio/{theme}/``.

    Pool for a MISSING level's fallback music: missing levels have no per-level
    track of their own, so the frontend plays a random track from this
    theme-appropriate set. ``theme`` is already validated by :func:`read_theme`,
    so the path cannot escape the audio dir.
    """
    audio_dir = STATIC_DIR / "audio" / theme
    ids: list[int] = []
    if audio_dir.is_dir():
        for p in audio_dir.glob("level_*.mp3"):
            try:
                ids.append(int(p.stem.split("_", 1)[1]))
            except (IndexError, ValueError):
                continue
    return sorted(ids)


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
    cache = cloudinary_service.get_cache()
    available = level_id in cache.folder_index
    return templates.TemplateResponse(
        request,
        "level.html",
        {
            "theme": theme,
            "level_id": level_id,
            "available": available,
            "audio_track_ids": _local_audio_ids(theme),
        },
    )


# --- JSON API --------------------------------------------------------------
@app.get("/api/levels")
def list_levels():
    """Return the configured levels and their availability flag (§4.1)."""
    return {"levels": _levels_payload()}


@app.get("/api/levels/{level_id}/photos")
def level_photos(level_id: int):
    """Return Cloudinary image refs for a level (+ null fallback audio).

    Unknown level id (outside the discovered span) -> 404. Each image element is
    an object with ``file_id`` (the Cloudinary ``public_id``) and a direct
    keyless CDN ``url`` (absolute ``https://res.cloudinary.com/...``). A missing
    level re-rolls a random image from the ``missing/`` pool per request (R3);
    ``fallback_audio`` is always ``null`` (audio is local per-theme — §11).
    """
    cache = cloudinary_service.get_cache()
    if level_id not in cache.levels:
        return JSONResponse({"detail": "Unknown level."}, status_code=404)

    result = cloudinary_service.get_level_photos(level_id)

    def _ref(photo) -> dict:
        # The url is the absolute keyless Cloudinary CDN link built at discovery
        # time (f_auto,q_auto for auto-format/quality). file_id = public_id.
        ref = {
            "file_id": photo.file_id,
            "url": photo.url,
        }
        # Optional, additive caption keyed by (level, filename_stem) — §11.3.
        # Cloudinary's public_id carries a random suffix, so we key captions on
        # the stable stem (e.g. "2.1") the service derived. Absent captions OMIT
        # the key entirely; a partial entry emits "" for the missing theme.
        cap = captions.get_caption(level_id, photo.filename_stem)
        if cap:
            ref["caption"] = {
                "sea": cap.get("sea", ""),
                "horror": cap.get("horror", ""),
            }
        return ref

    return {
        "level": result.level,
        "available": result.available,
        "images": [_ref(p) for p in result.images],
        "fallback_audio": None,
    }


@app.post("/api/refresh")
async def refresh():
    """Re-list Cloudinary + reload captions so edits take effect without redeploy.

    Re-runs the Cloudinary Admin discovery (metadata only — no byte download)
    and re-reads ``app/captions.json``. Both are cheap and safe to call on
    demand. Returns a small status dict (no secrets).
    """
    cache = await cloudinary_service.refresh()
    captions.reload_captions()
    return {
        "ready": cache.ready,
        "levels": len(cache.levels),
        "available": sorted(cache.folder_index.keys()),
        "missing_pool": len(cache.missing_images),
    }
