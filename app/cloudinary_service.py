"""Cloudinary client + dynamic level discovery for Archive 19 (M13).

Replaces the Google-Drive byte-proxy as the IMAGE source. Cloudinary's keyless
public CDN serves the images directly to the browser, so there is NO per-request
proxy, NO byte download, and NO throttle problem anymore. The server uses the
Cloudinary Admin API ONCE (metadata only) to discover what exists; the browser
then loads each image straight from ``res.cloudinary.com``.

Implements the M13 contract:

- Config via the standard ``CLOUDINARY_URL`` env var
  (``cloudinary://<api_key>:<api_secret>@<cloud_name>``) — a SECRET. It is parsed
  here, read ONLY from ``os.environ``, and the ``api_secret`` is NEVER logged,
  returned, or placed in any client payload. The delivery URLs are keyless (the
  public CDN) — that exposure is intended.
- ``discover()``: one paginated Admin API list of ``resources/image`` → group by
  ``asset_folder`` (``"all ages/{N}"`` -> level N, ``"all ages/missing"`` -> the
  fallback pool) → build a :class:`DiscoveryCache` mirroring the old Drive shape
  (so ``main.py`` needs minimal change), with each image ref carrying its
  ``public_id``, ``filename_stem`` (derived from ``public_id``), and the built
  keyless **CDN delivery URL**.
- A 30-min background re-list (``IMAGE_SYNC_INTERVAL_SECONDS``, gated OFF when
  unset — hermetic for tests/CI) plus an on-demand ``run_sync_once`` used by
  ``POST /api/refresh``. Both share one single-flight lock and never crash.

Tolerant by design: a missing/invalid ``CLOUDINARY_URL`` or any API error leaves
an empty (non-ready) cache and never raises — the app still serves an empty
gallery so local/CI without creds still boots.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import re
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger("archive19.cloudinary")

# --- Cloudinary contract constants -----------------------------------------
# Admin API: server-side, the secret is used ONLY here (HTTP basic auth).
_ADMIN_API_TMPL = "https://api.cloudinary.com/v1_1/{cloud}/resources/image"
_MAX_RESULTS = 500
# Delivery: keyless public CDN. f_auto,q_auto = free auto-format/quality.
_DELIVERY_TMPL = "https://res.cloudinary.com/{cloud}/image/upload/f_auto,q_auto/{public_id}.{fmt}"

# Folder convention: "all ages/{N}" -> level N, "all ages/missing" -> fallback.
_FOLDER_PREFIX = "all ages/"
_MISSING_FOLDER_NAME = "missing"
MISSING_DIR_NAME = _MISSING_FOLDER_NAME  # back-compat name some callers expect

# Cloudinary appends a random 6-char suffix to a derived public_id, e.g.
# "15.1" uploaded as "all ages/15" becomes public_id "15.1_gpoksj". The stable
# filename stem (what captions key on) is the public_id with that suffix removed.
# original_filename comes back null from the Admin API (verified live), so we
# derive the stem from public_id instead.
_SUFFIX_RE = re.compile(r"_[A-Za-z0-9]{6}$")

# Network timeout for the Admin API list (connect/read/write/pool).
_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


class CloudinaryConfigError(RuntimeError):
    """Raised internally when ``CLOUDINARY_URL`` is absent or malformed.

    Never carries the api_secret in its message.
    """


@dataclass(frozen=True)
class CloudinaryConfig:
    """Parsed ``CLOUDINARY_URL`` parts. ``api_secret`` stays server-side only."""

    api_key: str
    api_secret: str
    cloud_name: str


def _parse_cloudinary_url() -> Optional[CloudinaryConfig]:
    """Parse ``CLOUDINARY_URL`` from the environment, or return ``None``.

    SECURITY: read ONLY via ``os.environ``; the secret is never logged. A
    missing or malformed value returns ``None`` (graceful degrade) instead of
    raising, so the app boots with an empty gallery when no creds are present.
    """
    raw = os.environ.get("CLOUDINARY_URL")
    if not raw:
        return None
    raw = raw.strip().strip('"').strip("'")
    m = re.match(r"cloudinary://([^:]+):([^@]+)@(.+)", raw)
    if not m:
        logger.warning("CLOUDINARY_URL is set but malformed; image source disabled.")
        return None
    api_key, api_secret, cloud_name = m.group(1), m.group(2), m.group(3).strip()
    if not (api_key and api_secret and cloud_name):
        logger.warning("CLOUDINARY_URL missing a component; image source disabled.")
        return None
    return CloudinaryConfig(api_key=api_key, api_secret=api_secret, cloud_name=cloud_name)


def _filename_stem(public_id: str) -> str:
    """Derive the stable filename stem from a Cloudinary ``public_id``.

    Strips Cloudinary's random ``_xxxxxx`` suffix (e.g. ``15.1_gpoksj`` ->
    ``15.1``). This stem is what ``app/captions.json`` keys on after the M13
    re-key. A public_id without the suffix pattern is returned unchanged.
    """
    return _SUFFIX_RE.sub("", public_id)


def _delivery_url(cloud_name: str, public_id: str, fmt: str) -> str:
    """Build the keyless public-CDN delivery URL for a resource."""
    return _DELIVERY_TMPL.format(cloud=cloud_name, public_id=public_id, fmt=fmt or "jpg")


# --- Image reference + cache types (mirror the old Drive shape) -------------
@dataclass
class ImageRef:
    """A single image reference served to the client.

    ``file_id`` keeps the old payload key name but now holds the Cloudinary
    ``public_id`` (a stable, public identifier). ``url`` is the absolute keyless
    CDN delivery URL. ``filename_stem`` keys the captions lookup.
    """

    file_id: str          # = Cloudinary public_id
    filename_stem: str    # = public_id minus the random suffix (e.g. "15.1")
    url: str              # = absolute https://res.cloudinary.com/... CDN URL


# Back-compat alias: the old Drive code called this PhotoRef. Some non-Drive
# call sites / tests may reference it; keep the name available.
PhotoRef = ImageRef


@dataclass
class LevelPhotos:
    """Result of :func:`get_level_photos` (mirrors the old Drive dataclass)."""

    level: int
    available: bool
    images: list[ImageRef]
    fallback_audio: None = None  # audio is local per-theme (§11); always None


@dataclass
class DiscoveryCache:
    """In-memory level -> Cloudinary-image map, built once and cached (R2).

    Mirrors the old Drive ``DiscoveryCache`` field names so ``main.py`` and the
    templates need minimal change:

    - ``folder_index``: ``{level: True}`` for every PRESENT numbered folder
      (the value is a placeholder string so ``level in cache.folder_index`` and
      ``cache.folder_index.keys()`` keep working exactly as before).
    - ``levels``: the dynamic span ``0..max`` over the numeric folders present.
    - ``level_images``: ``{level: [ImageRef, ...]}`` for available levels.
    - ``missing_images``: the ``missing/`` fallback pool (R3 re-roll source).
    - ``ready``: True once a discovery has populated the cache at least once.
    """

    folder_index: dict[int, str] = field(default_factory=dict)
    levels: list[int] = field(default_factory=list)
    ready: bool = False
    level_images: dict[int, list[ImageRef]] = field(default_factory=dict)
    missing_images: list[ImageRef] = field(default_factory=list)

    # Retained for payload back-compat with the old shape (always None/empty
    # under Cloudinary: there is no Drive folder id and audio is local).
    missing_folder_id: Optional[str] = None


# Module-level singleton cache. Rebuilt only by ``discover(force=True)``
# (startup), the background sync, or ``POST /api/refresh``.
_cache = DiscoveryCache()


def get_cache() -> DiscoveryCache:
    """Return the current (possibly empty) discovery cache."""
    return _cache


# --- Admin API list (paginated) --------------------------------------------
async def _list_all_resources(
    cfg: CloudinaryConfig, client: httpx.AsyncClient
) -> list[dict]:
    """List ALL upload-type image resources, following ``next_cursor`` (R4).

    SECURITY: the ``api_secret`` is sent only as HTTP basic auth to Cloudinary;
    it is never logged. On any error this raises so the caller can degrade to
    the prior cache; it never leaks the secret in the message.
    """
    api = _ADMIN_API_TMPL.format(cloud=cfg.cloud_name)
    auth = (cfg.api_key, cfg.api_secret)
    resources: list[dict] = []
    next_cursor: Optional[str] = None
    # Defensive page cap so a pathological cursor loop can never spin forever.
    for _ in range(50):
        params: dict[str, str | int] = {
            "max_results": _MAX_RESULTS,
            "type": "upload",
        }
        if next_cursor:
            params["next_cursor"] = next_cursor
        resp = await client.get(api, params=params, auth=auth, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        resources.extend(data.get("resources", []) or [])
        next_cursor = data.get("next_cursor")
        if not next_cursor:
            break
    return resources


def _build_cache(cfg: CloudinaryConfig, resources: list[dict]) -> DiscoveryCache:
    """Group raw Admin API resources into a :class:`DiscoveryCache`.

    Resources whose ``asset_folder`` is not under ``"all ages/"`` (e.g. the
    uncategorized root uploads) are ignored. ``"all ages/{N}"`` populates level
    N; ``"all ages/missing"`` populates the fallback pool.
    """
    level_images: dict[int, list[ImageRef]] = {}
    missing_images: list[ImageRef] = []

    for r in resources:
        public_id = r.get("public_id")
        if not public_id:
            continue
        fmt = str(r.get("format", "") or "")
        folder = str(r.get("asset_folder", "") or "").strip()
        if not folder.startswith(_FOLDER_PREFIX):
            continue
        leaf = folder[len(_FOLDER_PREFIX):].strip().strip("/")
        ref = ImageRef(
            file_id=public_id,
            filename_stem=_filename_stem(public_id),
            url=_delivery_url(cfg.cloud_name, public_id, fmt),
        )
        if leaf.lower() == _MISSING_FOLDER_NAME:
            missing_images.append(ref)
        elif leaf.isdigit():
            level_images.setdefault(int(leaf), []).append(ref)
        # any other leaf (unexpected) is ignored — defensive

    # Stable ordering so the gallery render is deterministic per discovery.
    for refs in level_images.values():
        refs.sort(key=lambda x: x.filename_stem)
    missing_images.sort(key=lambda x: x.filename_stem)

    folder_index = {lid: f"cloudinary:{lid}" for lid in level_images}
    if folder_index:
        levels = list(range(0, max(folder_index) + 1))
    else:
        levels = []

    return DiscoveryCache(
        folder_index=folder_index,
        levels=levels,
        ready=True,
        level_images=level_images,
        missing_images=missing_images,
        missing_folder_id="cloudinary:missing" if missing_images else None,
    )


# --- Discovery (public API) ------------------------------------------------
async def discover(force: bool = False) -> DiscoveryCache:
    """Build & cache the level -> Cloudinary-image map (one Admin API list).

    R2: the result is cached; subsequent calls return the cache unless ``force``
    is set (startup / background sync / ``POST /api/refresh``). A missing/invalid
    ``CLOUDINARY_URL`` or any API error degrades gracefully — the prior (or
    empty) cache is kept and this NEVER raises.
    """
    global _cache
    if _cache.ready and not force:
        return _cache

    cfg = _parse_cloudinary_url()
    if cfg is None:
        logger.info("Cloudinary not configured; serving empty gallery.")
        return _cache

    try:
        async with httpx.AsyncClient() as client:
            resources = await _list_all_resources(cfg, client)
    except httpx.HTTPStatusError as exc:
        logger.warning("Cloudinary Admin list failed: HTTP %s", exc.response.status_code)
        return _cache
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Cloudinary Admin list error: %s", type(exc).__name__)
        return _cache
    except Exception as exc:  # defensive: discovery must never block startup
        logger.warning("Cloudinary discovery error: %s", type(exc).__name__)
        return _cache

    _cache = _build_cache(cfg, resources)
    logger.info(
        "Cloudinary discovery complete: %d available levels, span=%d, "
        "missing pool=%d image(s).",
        len(_cache.folder_index),
        len(_cache.levels),
        len(_cache.missing_images),
    )
    return _cache


def get_level_photos(level_id: int) -> LevelPhotos:
    """Return image refs for ``level_id`` (+ a re-rolled missing image when absent).

    - Present & non-empty level -> ``available=True`` and its images.
    - Absent OR empty (R5) -> ``available=False`` and a FRESH random image
      re-rolled from the ``missing/`` pool on EVERY call (R3). Audio is local
      per-theme (§11), so ``fallback_audio`` is always ``None``.

    Pure in-memory (no network): all image metadata + CDN URLs live in the cache
    and the browser fetches bytes directly from the CDN. Never raises.
    """
    images = _cache.level_images.get(level_id)
    if images:
        return LevelPhotos(
            level=level_id,
            available=True,
            images=list(images),
            fallback_audio=None,
        )

    # Missing-level fallback: re-roll one random image from the missing/ pool.
    if _cache.missing_images:
        img = random.choice(_cache.missing_images)
        return LevelPhotos(
            level=level_id,
            available=False,
            images=[img],
            fallback_audio=None,
        )

    # No fallback pool available (e.g. unconfigured) -> empty, never raise.
    return LevelPhotos(level=level_id, available=False, images=[], fallback_audio=None)


# --- On-demand + periodic background re-list (§12.13, simplified) -----------
# Single-flight guard shared by the periodic loop AND POST /api/refresh.
_sync_lock = asyncio.Lock()


async def run_sync_once() -> dict:
    """Re-list Cloudinary once and update the cache (single-flight).

    Cheap metadata-only operation — there are NO byte downloads anymore. Skips
    if a sync is already running. Returns a small status dict (no secrets) and
    never raises (the caller and the loop also guard).
    """
    if _sync_lock.locked():
        logger.info("Cloudinary sync already running; skipping this trigger.")
        return {"status": "skipped-locked"}

    async with _sync_lock:
        if _parse_cloudinary_url() is None:
            return {"status": "no-creds"}
        before = len(_cache.folder_index)
        await discover(force=True)
        after = len(_cache.folder_index)
        return {
            "status": "synced",
            "available_levels": after,
            "changed": after != before,
        }


# Public alias used by POST /api/refresh.
async def refresh() -> DiscoveryCache:
    """Force a fresh Cloudinary discovery (used by ``POST /api/refresh``)."""
    return await discover(force=True)


async def background_sync_loop(interval: int, initial_delay: float = 60.0) -> None:
    """Lifespan-owned poller: re-list Cloudinary every ``interval`` seconds.

    Sleeps ``initial_delay`` so it never competes with cold-start warmup, then
    ticks. Each tick is wrapped in a catch-all (log + swallow → retry next
    interval) and the loop is cancelled cleanly on shutdown. ONLY scheduled when
    ``interval > 0`` and ``CLOUDINARY_URL`` is set (gate in ``main.lifespan``),
    so tests/CI never reach it.
    """
    try:
        await asyncio.sleep(initial_delay)
        while True:
            try:
                await run_sync_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — must never crash the loop
                logger.warning(
                    "Cloudinary sync tick errored (%s); retrying next interval.",
                    type(exc).__name__,
                )
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("Cloudinary sync loop cancelled; shutting down cleanly.")
        raise
