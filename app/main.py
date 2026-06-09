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

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import captions, drive_service
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

# Baked level-image dir (M12 §12.3). The static `url` is emitted only when the
# baked file is present here; otherwise `_ref` falls back to the proxy URL.
LEVELS_IMG_DIR = STATIC_DIR / "img" / "levels"


def _image_sync_interval() -> int:
    """Read ``IMAGE_SYNC_INTERVAL_SECONDS`` (§12.13). 0/unset/invalid -> 0.

    A return of 0 means the periodic background sync is DISABLED — the task is
    never created, so local dev, CI, and the pytest suite never poll Drive
    (hermetic — R-Bake8). Render sets a positive value (e.g. 1800) to enable it.
    """
    raw = os.environ.get("IMAGE_SYNC_INTERVAL_SECONDS", "")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 0
    return value if value > 0 else 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the discovery cache once at startup (R2 / §12.4).

    Discovery source order (§12.4): build-written ``manifest.json`` is PRIMARY
    (zero Drive calls at cold start, no runtime creds needed); if absent or
    malformed, fall back to live Drive **metadata** discovery; if that also
    fails, the empty gallery (exactly as today). Never crash on a failed
    discovery — the app must still serve pages so local runs and tests work
    without live Drive access.

    When ``IMAGE_SYNC_INTERVAL_SECONDS > 0`` AND Drive creds are present, a
    single ``asyncio`` background sync task is started (§12.13) and cancelled
    cleanly on shutdown. With 0/unset/invalid OR no creds the task is NEVER
    created (hermetic local/CI/tests — R-Bake8).
    """
    try:
        if not drive_service.load_discovery(force=True):
            # No usable manifest -> live Drive metadata discovery (fallback).
            await drive_service.discover_levels(force=True)
    except Exception as exc:  # defensive: discovery must never block startup
        logger.warning("Startup discovery did not complete: %s", type(exc).__name__)
    # Load image captions once (§11.2). The loader is tolerant — a missing or
    # malformed app/captions.json degrades to an empty map and never raises.
    captions.load_captions()

    # §12.13: start the periodic background sync ONLY when explicitly enabled
    # AND creds exist. This gate is what keeps the test suite + local runs
    # hermetic — with the env unset/0 the task is never scheduled and Drive is
    # never polled.
    sync_task: asyncio.Task | None = None
    interval = _image_sync_interval()
    creds_present = bool(os.environ.get("GD_API_KEY")) and bool(
        os.environ.get("GD_ROOT_FOLDER")
    )
    if interval > 0 and creds_present:
        logger.info("Background image sync ENABLED: every %ds.", interval)
        sync_task = asyncio.create_task(
            drive_service.background_sync_loop(interval)
        )
    else:
        logger.info(
            "Background image sync DISABLED (interval=%d, creds=%s).",
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
    cache = drive_service.get_cache()
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
    cache = drive_service.get_cache()
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

    # A missing-level (available: false) image is baked under .../levels/missing/,
    # an available level's images under .../levels/{id}/ (§12.3).
    disk_subdir = str(level_id) if result.available else drive_service.MISSING_DIR_NAME

    def _ref(photo) -> dict:
        # §12.3/§12.5/§12.8: emit the static URL iff the baked file exists on
        # disk; otherwise fall back to the guarded media proxy (un-baked / local
        # dev / not-yet-synced id). file_id + name + caption are unchanged.
        baked = LEVELS_IMG_DIR / disk_subdir / photo.name
        if drive_service.is_safe_name(photo.name) and baked.is_file():
            url = f"/static/img/levels/{disk_subdir}/{photo.name}"
        else:
            url = f"/api/levels/{level_id}/media/{photo.file_id}"
        ref = {
            "file_id": photo.file_id,
            "url": url,
        }
        # Optional, additive caption keyed by (level, filename) — §11.3. Absent
        # captions OMIT the key entirely (payload identical to today). A partial
        # entry (only one theme present) emits "" for the missing theme so the
        # client can still toggle without a missing-key error.
        cap = captions.get_caption(level_id, photo.name)
        if cap:
            ref["caption"] = {
                "sea": cap.get("sea", ""),
                "horror": cap.get("horror", ""),
            }
        return ref

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
    """Manually refresh discovery + captions, and force an immediate sync (§12.13.5).

    Under the M12 manifest model (§12.4) refresh first **re-reads the manifest**
    (PRIMARY) — falling back to live Drive metadata discovery when no manifest
    is present — and **re-reads captions** so an edit takes effect without a
    redeploy (§11.2). When the background sync is enabled AND creds are present,
    it ALSO triggers an **immediate** sync via the SAME single-flight code path
    (§12.13.5) so an operator can pull new images on demand instead of waiting
    for the next tick. With sync disabled (e.g. tests/CI) it is a no-op refresh,
    exactly as before — no Drive download, no new behavior on the test path.
    """
    if not drive_service.load_discovery(force=True):
        # No manifest -> fall back to live Drive metadata discovery (R2).
        await drive_service.discover_levels(force=True)
    # Re-read captions so a caption edit takes effect without a redeploy (§11.2).
    captions.reload_captions()

    # §12.13.5: an explicit operator action MAY pull new images on demand even
    # when the periodic loop is off — but only when creds are present (so the
    # hermetic test path, which has dummy creds but no real Drive, stays a
    # cheap re-read: run_sync_once short-circuits to a metadata list that the
    # mocked tests already handle). We only fire it when the periodic sync is
    # actually enabled to keep /api/refresh behavior identical under the test
    # suite (sync disabled there).
    sync_status = "disabled"
    if _image_sync_interval() > 0 and os.environ.get("GD_API_KEY"):
        try:
            result = await drive_service.run_sync_once()
            sync_status = str(result.get("status", "unknown"))
        except Exception as exc:  # never let a sync error fail the refresh
            logger.warning("On-demand sync errored: %s", type(exc).__name__)
            sync_status = "error"

    cache = drive_service.get_cache()
    return {
        "ready": cache.ready,
        "levels": len(cache.levels),
        "available": sorted(cache.folder_index.keys()),
        "missing_folder": cache.missing_folder_id is not None,
        "sync": sync_status,
    }
