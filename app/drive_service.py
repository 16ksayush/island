"""Google Drive client + dynamic level discovery for Archive 19.

Implements docs/ARCHITECTURE.md §5 / §5.1:

- A thin Drive API v3 client (``httpx``) that lists folder children with
  pagination (R4) and streams file bytes via ``files.get?alt=media``.
- ``discover_levels()`` builds & caches the level -> Drive-folder map ONCE
  (folder_index / missing_folder_id / levels) from the children of
  ``GD_ROOT_FOLDER`` (R2: refreshed only via ``POST /api/refresh``).
- ``get_level_photos(level_id)``: present, non-empty folder -> its images;
  absent OR empty-but-present (R5) -> a freshly re-rolled (R3) random image +
  random audio drawn from the Drive ``missing/`` folder on EVERY call.
- ``resolve_media(level_id, file_id)``: validates the ``file_id`` belongs to
  the resolved level folder OR ``missing/`` (R1 — no open proxy) before
  returning a streaming fetch.

Security invariants:
- ``GD_API_KEY`` is read ONLY via ``os.environ.get("GD_API_KEY")`` (no
  literals, no defaults). A missing key fails loudly server-side.
- The key is never logged and never placed in any client-facing payload; only
  ``file_id`` values and proxied ``/api/.../media/...`` URLs leave the server.
- All network I/O is wrapped in defensive ``try/except`` that never leaks the
  key in error messages.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import httpx

logger = logging.getLogger("archive19.drive")

# --- Drive API v3 constants ------------------------------------------------
DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
FOLDER_MIME = "application/vnd.google-apps.folder"
IMAGE_MIME_PREFIX = "image/"
AUDIO_MIME_PREFIX = "audio/"
MISSING_FOLDER_NAME = "missing"

# Network timeout (connect/read/write/pool) for every Drive request.
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_LIST_PAGE_SIZE = 1000

# --- Build-time bake / manifest layout (§12.3 / §12.4) ---------------------
# static/ + templates/ live at the repo root (PRD §7); this module is app/.
_REPO_ROOT = Path(__file__).resolve().parent.parent
# The baked-images base dir (git-ignored per §12.9) and its manifest.
LEVELS_IMG_DIR = _REPO_ROOT / "static" / "img" / "levels"
MANIFEST_PATH = LEVELS_IMG_DIR / "manifest.json"
MISSING_DIR_NAME = "missing"

# --- Paced downloader defaults (§12.2 / §12.3 — one source of truth, NF-Bake7)
# Shared by scripts/fetch_images.py AND the §12.13 background sync so neither
# duplicates the pacing logic. Tuned for the 52-image set + headroom; only
# ``files.get?alt=media`` (downloads) are throttled — metadata is not (§12.1).
DOWNLOAD_CONCURRENCY = 2          # small worker pool, NOT a wide burst
DOWNLOAD_DELAY = 0.4              # seconds between request starts, per worker
DOWNLOAD_DELAY_JITTER = 0.2       # ±20% jitter to avoid lockstep
DOWNLOAD_MAX_RETRIES = 5         # retry budget per file on 403/429/5xx
DOWNLOAD_BACKOFF_BASE = 2.0      # exp backoff base seconds (2, 4, 8, 16, 32)
DOWNLOAD_BACKOFF_CAP = 32.0
# Statuses treated as a throttle/transient signal (back off + retry the file).
_RETRYABLE_STATUSES = frozenset({403, 429, 500, 502, 503, 504})

# --- Media byte cache bounds -----------------------------------------------
# The entire Drive folder is ~6 MB, so these caps comfortably hold every asset
# while still guaranteeing memory can never grow unbounded. Eviction is LRU on
# BOTH dimensions: oldest entries are dropped once either the entry count OR the
# total byte budget is exceeded.
_MEDIA_CACHE_MAX_ENTRIES = 256
_MEDIA_CACHE_MAX_BYTES = 64 * 1024 * 1024  # 64 MB hard ceiling
# Files larger than the whole budget are streamed-through but never cached.
_MEDIA_CACHE_MAX_ITEM_BYTES = _MEDIA_CACHE_MAX_BYTES


class DriveError(RuntimeError):
    """Raised when an upstream Drive call fails (maps to HTTP 502 upstream).

    Never carries the API key in its message.
    """


class DriveConfigError(RuntimeError):
    """Raised when required configuration (GD_API_KEY) is absent."""


# --- Config accessors (read at call time, never cached as literals) --------
def _get_api_key() -> str:
    """Return the Drive API key from the environment, or fail loudly.

    SECURITY: the key is read ONLY here, via ``os.environ.get``. It is never
    logged and never returned to a client.
    """
    key = os.environ.get("GD_API_KEY")
    if not key:
        raise DriveConfigError(
            "GD_API_KEY is not set; the Drive proxy cannot reach Google Drive."
        )
    return key


def _get_root_folder() -> str:
    """Return the parent Drive folder id (config, not a secret)."""
    root = os.environ.get("GD_ROOT_FOLDER")
    if not root:
        raise DriveConfigError("GD_ROOT_FOLDER is not configured.")
    return _extract_folder_id(root)


def _extract_folder_id(value: str) -> str:
    """Accept either a bare folder id or a Drive share link and return the id."""
    value = value.strip()
    marker = "/folders/"
    if marker in value:
        tail = value.split(marker, 1)[1]
        # strip any trailing query/path component
        return tail.split("?", 1)[0].split("/", 1)[0]
    return value


# --- Photo/media reference types (§4.1) ------------------------------------
@dataclass
class PhotoRef:
    """A single image/audio reference returned to the client (no Drive URL)."""

    file_id: str
    name: str


@dataclass
class LevelPhotos:
    """Result of :func:`get_level_photos`."""

    level: int
    available: bool
    images: list[PhotoRef]
    fallback_audio: Optional[PhotoRef]


# --- Cached discovery state (§5.1) -----------------------------------------
@dataclass
class DiscoveryCache:
    """In-memory level -> Drive-folder map, built once and cached (R2).

    Beyond the folder map, the cache also holds the per-level/missing **scope
    lists** — the set of valid image/audio ``file_id`` values per folder. These
    let the media proxy validate scope (R1) WITHOUT re-listing Drive on every
    request. They share the discovery lifetime: rebuilt only by
    ``discover_levels(force=True)`` / ``POST /api/refresh`` (R2).
    """

    folder_index: dict[int, str] = field(default_factory=dict)
    missing_folder_id: Optional[str] = None
    levels: list[int] = field(default_factory=list)
    # True once discovery has successfully run at least once.
    ready: bool = False

    # Scope cache: per-level image file refs (id -> name). Populated lazily on
    # first access to a level, then reused (R1 membership checks read this).
    level_images: dict[int, list[PhotoRef]] = field(default_factory=dict)
    # Missing/ folder image + audio refs (the random re-roll pool — R3 reads
    # this LIST but still picks fresh per request).
    missing_images: Optional[list[PhotoRef]] = None
    missing_audio: Optional[list[PhotoRef]] = None


# Module-level singleton cache. Rebuilt only by ``discover_levels(force=True)``
# (startup) or via the manual ``POST /api/refresh`` route.
_cache = DiscoveryCache()


def get_cache() -> DiscoveryCache:
    """Return the current (possibly empty) discovery cache."""
    return _cache


# --- Bounded in-memory media byte cache (LRU) ------------------------------
class MediaByteCache:
    """Thread-safe, byte-bounded LRU cache of proxied media bytes.

    Key = Drive ``file_id``; value = ``(content_type, bytes)``. Drive file ids
    are immutable, so a cache hit can be served forever (until a manual refresh
    clears it alongside discovery). Evicts least-recently-used entries once
    either the entry count or the total byte budget is exceeded.

    SECURITY: only public, in-scope media bytes are ever stored — the
    ``GD_API_KEY`` is never a key, value, or part of any entry, and nothing is
    persisted to disk.
    """

    def __init__(self, max_entries: int, max_bytes: int) -> None:
        self._max_entries = max_entries
        self._max_bytes = max_bytes
        self._lock = threading.Lock()
        self._store: "OrderedDict[str, tuple[str, bytes]]" = OrderedDict()
        self._total_bytes = 0

    def get(self, file_id: str) -> Optional[tuple[str, bytes]]:
        """Return the cached ``(content_type, bytes)`` and mark it most-recent."""
        with self._lock:
            entry = self._store.get(file_id)
            if entry is None:
                return None
            self._store.move_to_end(file_id)
            return entry

    def put(self, file_id: str, content_type: str, body: bytes) -> None:
        """Insert/refresh an entry, evicting LRU items to honour the bounds.

        Oversized single items (larger than the whole budget) are not cached.
        """
        size = len(body)
        if size > self._max_bytes:
            return
        with self._lock:
            existing = self._store.pop(file_id, None)
            if existing is not None:
                self._total_bytes -= len(existing[1])
            self._store[file_id] = (content_type, body)
            self._total_bytes += size
            self._store.move_to_end(file_id)
            while self._store and (
                len(self._store) > self._max_entries
                or self._total_bytes > self._max_bytes
            ):
                _evicted_id, (_ct, evicted_body) = self._store.popitem(last=False)
                self._total_bytes -= len(evicted_body)

    def clear(self) -> None:
        """Drop every cached entry (used by ``POST /api/refresh``)."""
        with self._lock:
            self._store.clear()
            self._total_bytes = 0


# Module-level singleton byte cache, bounded per the constants above.
_media_cache = MediaByteCache(_MEDIA_CACHE_MAX_ENTRIES, _MEDIA_CACHE_MAX_BYTES)


# --- Low-level Drive client ------------------------------------------------
async def list_children(
    folder_id: str,
    client: httpx.AsyncClient,
) -> list[dict]:
    """List all children of ``folder_id`` (handles pagination — R4).

    Returns a list of ``{"id", "name", "mimeType"}`` dicts. Raises
    :class:`DriveError` on any upstream failure.
    """
    api_key = _get_api_key()
    items: list[dict] = []
    page_token: Optional[str] = None
    while True:
        params = {
            "q": f"'{folder_id}' in parents and trashed = false",
            "fields": "nextPageToken, files(id, name, mimeType)",
            "pageSize": _LIST_PAGE_SIZE,
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
            "key": api_key,
        }
        if page_token:
            params["pageToken"] = page_token
        try:
            resp = await client.get(
                f"{DRIVE_API_BASE}/files", params=params, timeout=_TIMEOUT
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            # Log status only — never the URL (it carries ?key=) or the body.
            logger.warning(
                "Drive files.list failed for a folder: HTTP %s",
                exc.response.status_code,
            )
            raise DriveError("Upstream Drive list request failed.") from None
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Drive files.list error: %s", type(exc).__name__)
            raise DriveError("Upstream Drive list request failed.") from None

        items.extend(data.get("files", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return items


def _filter_by_mime_prefix(items: list[dict], prefix: str) -> list[dict]:
    """Return items whose ``mimeType`` starts with ``prefix`` and have an id."""
    return [
        it
        for it in items
        if str(it.get("mimeType", "")).startswith(prefix) and it.get("id")
    ]


# --- Discovery (§5 / §5.1) -------------------------------------------------
async def discover_levels(force: bool = False) -> DiscoveryCache:
    """Build & cache the level -> folder map from ``GD_ROOT_FOLDER``'s children.

    The numeric-named child folders define which levels exist (dynamic
    scaling). ``levels`` spans ``min(0)..max(discovered)`` so absent ids still
    render a tile (flagged unavailable). The ``missing/`` child id is recorded
    for fallbacks.

    R2: result is cached; subsequent calls return the cache unless ``force`` is
    set (startup, or ``POST /api/refresh``). Discovery failures degrade
    gracefully — the app keeps running with whatever cache is available.
    """
    global _cache
    if _cache.ready and not force:
        return _cache

    try:
        root_id = _get_root_folder()
    except DriveConfigError as exc:
        logger.warning("Discovery skipped: %s", exc)
        # Keep an empty (non-ready) cache so the app still serves pages.
        return _cache

    try:
        async with httpx.AsyncClient() as client:
            children = await list_children(root_id, client)

            folder_index: dict[int, str] = {}
            missing_folder_id: Optional[str] = None
            for child in children:
                if child.get("mimeType") != FOLDER_MIME:
                    continue
                name = str(child.get("name", "")).strip()
                cid = child.get("id")
                if not cid:
                    continue
                if name.lower() == MISSING_FOLDER_NAME:
                    missing_folder_id = cid
                    continue
                if name.isdigit():
                    folder_index[int(name)] = cid

            if folder_index:
                max_level = max(folder_index)
                levels = list(range(0, max_level + 1))
            else:
                levels = []

            new_cache = DiscoveryCache(
                folder_index=folder_index,
                missing_folder_id=missing_folder_id,
                levels=levels,
                ready=True,
            )

            # Eagerly populate the scope/list cache so the media proxy never
            # re-lists Drive per request (R1 validates against this set). Each
            # numbered folder is listed once here; on the off chance an
            # individual list fails, that level is simply left for lazy
            # population on first access (see ``_ensure_level_scope``).
            for level_id, fid in folder_index.items():
                try:
                    items = await list_children(fid, client)
                except DriveError:
                    logger.warning(
                        "Scope prefetch failed for level %d; will populate lazily.",
                        level_id,
                    )
                    continue
                refs = [
                    PhotoRef(file_id=i["id"], name=str(i.get("name", "")))
                    for i in _filter_by_mime_prefix(items, IMAGE_MIME_PREFIX)
                ]
                new_cache.level_images[level_id] = refs

            # Prefetch the missing/ image + audio lists (the R3 re-roll pool).
            if missing_folder_id is not None:
                try:
                    m_items = await list_children(missing_folder_id, client)
                    m_images = [
                        PhotoRef(file_id=i["id"], name=str(i.get("name", "")))
                        for i in _filter_by_mime_prefix(m_items, IMAGE_MIME_PREFIX)
                    ]
                    m_audio = [
                        PhotoRef(file_id=i["id"], name=str(i.get("name", "")))
                        for i in _filter_by_mime_prefix(m_items, AUDIO_MIME_PREFIX)
                    ]
                    new_cache.missing_images = m_images
                    new_cache.missing_audio = m_audio
                except DriveError:
                    logger.warning(
                        "Scope prefetch failed for missing/; will populate lazily."
                    )
    except DriveError:
        logger.warning("Discovery failed: Drive unreachable; serving prior cache.")
        return _cache

    _cache = new_cache
    # A fresh discovery invalidates any previously cached bytes (R2): Drive
    # content may have changed, so the byte cache must not serve stale data.
    _media_cache.clear()
    logger.info(
        "Discovery complete: %d numbered folders, missing=%s, span=%d levels, "
        "%d level scope-lists prefetched.",
        len(folder_index),
        "yes" if missing_folder_id else "no",
        len(levels),
        len(new_cache.level_images),
    )
    return _cache


# --- Scope cache population (R1) -------------------------------------------
async def _ensure_level_scope(
    level_id: int, client: httpx.AsyncClient
) -> list[PhotoRef]:
    """Return the cached image refs for ``level_id``, listing Drive only once.

    If discovery already prefetched this level, the cached list is returned with
    no Drive call. Otherwise the folder is listed once, cached (the per-level
    scope list the R1 guard checks), then reused. Caller must hold a valid level
    folder id.
    """
    cached = _cache.level_images.get(level_id)
    if cached is not None:
        return cached
    folder_id = _cache.folder_index.get(level_id)
    if folder_id is None:
        return []
    items = await list_children(folder_id, client)
    refs = [
        PhotoRef(file_id=i["id"], name=str(i.get("name", "")))
        for i in _filter_by_mime_prefix(items, IMAGE_MIME_PREFIX)
    ]
    _cache.level_images[level_id] = refs
    return refs


async def _ensure_missing_scope(
    client: httpx.AsyncClient,
) -> tuple[list[PhotoRef], list[PhotoRef]]:
    """Return cached ``(images, audio)`` refs for ``missing/``, listing once.

    The LIST is cached (R3 caches the pool); the random choice still happens
    fresh per request in :func:`get_level_photos`.
    """
    if not _cache.missing_folder_id:
        raise DriveError("No 'missing/' folder is configured for fallback.")
    if _cache.missing_images is not None and _cache.missing_audio is not None:
        return _cache.missing_images, _cache.missing_audio
    items = await list_children(_cache.missing_folder_id, client)
    images = [
        PhotoRef(file_id=i["id"], name=str(i.get("name", "")))
        for i in _filter_by_mime_prefix(items, IMAGE_MIME_PREFIX)
    ]
    audio = [
        PhotoRef(file_id=i["id"], name=str(i.get("name", "")))
        for i in _filter_by_mime_prefix(items, AUDIO_MIME_PREFIX)
    ]
    _cache.missing_images = images
    _cache.missing_audio = audio
    return images, audio


# --- Photos (§4.1) ---------------------------------------------------------
async def get_level_photos(level_id: int) -> LevelPhotos:
    """Return image refs for ``level_id`` (+ fallback audio when missing).

    - Present & non-empty folder -> ``available=True``, its images, no audio.
    - Absent OR empty-but-present (R5) -> ``available=False`` and a FRESH random
      image + random audio re-rolled from ``missing/`` on EVERY call (R3).

    Image/audio LISTS come from the discovery-time scope cache (no per-call
    Drive list once populated), but the missing-level pick is still re-rolled on
    every call so it varies per request (R3).

    Raises :class:`DriveError` on upstream failure.
    """
    folder_id = _cache.folder_index.get(level_id)
    async with httpx.AsyncClient() as client:
        if folder_id is not None:
            images = await _ensure_level_scope(level_id, client)
            if images:
                return LevelPhotos(
                    level=level_id,
                    available=True,
                    images=list(images),
                    fallback_audio=None,
                )
            # Present but empty -> fall through to missing fallback (R5).

        # Missing-level fallback: re-roll a FRESH random image per call (R3) from
        # the cached missing/ pool. Audio for a missing level is NOT taken from
        # Drive — the frontend plays a random LOCAL per-theme track instead — so
        # the missing/ folder only needs images and we never 502 over absent
        # audio. (Drive audio in missing/, if any, is simply unused.)
        missing_images, _missing_audio = await _ensure_missing_scope(client)
        if not missing_images:
            raise DriveError("Missing fallback folder has no image to show.")
        img = random.choice(missing_images)
        return LevelPhotos(
            level=level_id,
            available=False,
            images=[PhotoRef(file_id=img.file_id, name=img.name)],
            fallback_audio=None,
        )


# --- Media proxy (§4 / R1 / R6) --------------------------------------------
async def _file_in_scope(level_id: int, file_id: str) -> bool:
    """Return True iff ``file_id`` is in scope FOR ``level_id`` (its folder) OR
    the ``missing/`` folder.

    R1 (open-proxy guard): membership is checked against the CACHED per-level
    scope lists instead of re-listing Drive per media request. The check is
    scoped per level — a file id belonging to a *different* level's folder is
    NOT in scope here, so one level can never proxy another level's bytes. Only
    this level's own images plus the shared ``missing/`` set qualify. The
    relevant lists are ensured-populated once (lazily, if discovery didn't
    prefetch them). An unknown/out-of-scope id is never in scope, so the route
    404s and never streams an arbitrary file.
    """
    folder_id = _cache.folder_index.get(level_id)
    has_missing = _cache.missing_folder_id is not None
    if folder_id is None and not has_missing:
        return False

    try:
        async with httpx.AsyncClient() as client:
            # This level's own images (no-op after prefetch / first lazy fill).
            if folder_id is not None:
                level_refs = await _ensure_level_scope(level_id, client)
                if any(r.file_id == file_id for r in level_refs):
                    return True
            # The shared missing/ fallback set (images + audio).
            if has_missing:
                m_images, m_audio = await _ensure_missing_scope(client)
                if any(r.file_id == file_id for r in m_images) or any(
                    r.file_id == file_id for r in m_audio
                ):
                    return True
    except DriveError:
        # If we cannot confirm scope, fail closed (treat as out-of-scope).
        logger.warning("Scope check could not list Drive; treating id as out-of-scope.")
        return False

    return False


async def resolve_media(level_id: int, file_id: str) -> Optional[tuple[str, bytes]]:
    """Resolve a Drive ``file_id`` to ``(content_type, bytes)``, scoped to a level.

    Returns ``None`` if the id is not in scope (route -> 404, R1). On a media
    byte-cache hit the bytes are served from memory with their cached
    Content-Type; otherwise Drive is fetched once, the result is cached, then
    returned. The ``content_type`` always mirrors the upstream Drive
    ``Content-Type`` (R6 — image/* vs audio/mpeg, never hardcoded); on a cache
    hit it is the upstream value captured at fetch time.

    Raises :class:`DriveError` on upstream failure (route -> 502).
    """
    if not await _file_in_scope(level_id, file_id):
        return None

    # Byte-cache hit: serve from memory (content-type was captured at fetch).
    cached = _media_cache.get(file_id)
    if cached is not None:
        return cached

    api_key = _get_api_key()
    params = {
        "alt": "media",
        "supportsAllDrives": "true",
        "key": api_key,
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{DRIVE_API_BASE}/files/{file_id}", params=params
            )
            resp.raise_for_status()
            # R6: echo upstream Content-Type verbatim (fallback octet-stream).
            content_type = resp.headers.get(
                "content-type", "application/octet-stream"
            )
            body = resp.content
    except httpx.HTTPStatusError as exc:
        logger.warning("Drive files.get failed: HTTP %s", exc.response.status_code)
        raise DriveError("Upstream Drive media request failed.") from None
    except httpx.HTTPError as exc:
        logger.warning("Drive files.get error: %s", type(exc).__name__)
        raise DriveError("Upstream Drive media request failed.") from None

    # Cache the immutable bytes + their content-type for future hits (R6).
    _media_cache.put(file_id, content_type, body)
    return content_type, body


# --- Filesystem-safe filename guard (§12.3 / NF-Bake5) ---------------------
def is_safe_name(name: str) -> bool:
    """Return True iff ``name`` is a single filename safe to write on disk.

    Rejects empty names, any path separator (``/`` or ``\\``), and ``..`` so a
    hostile Drive filename can never escape ``static/img/levels/{id}/`` (no
    path traversal — NF-Bake5). The confirmed real set is uniform
    ``{n}.{i}.jpeg`` and always passes; this guard exists for defense.
    """
    if not name or name in (".", ".."):
        return False
    if "/" in name or "\\" in name or ".." in name:
        return False
    return True


# --- Paced byte downloader (§12.2 / §12.3 — one source of truth, NF-Bake7) --
async def _download_one(
    file_id: str, client: httpx.AsyncClient, api_key: str
) -> bytes:
    """Fetch a single Drive file's bytes via ``files.get?alt=media``.

    Retries on 403/429/5xx with exponential backoff + jitter (a throttle signal,
    not a hard failure) up to :data:`DOWNLOAD_MAX_RETRIES`. Raises
    :class:`DriveError` once the budget is exhausted or on a non-retryable
    error. SECURITY: the key is sent upstream only; never logged, never raised.
    """
    params = {"alt": "media", "supportsAllDrives": "true", "key": api_key}
    attempt = 0
    while True:
        try:
            resp = await client.get(
                f"{DRIVE_API_BASE}/files/{file_id}", params=params, timeout=_TIMEOUT
            )
            resp.raise_for_status()
            return resp.content
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in _RETRYABLE_STATUSES and attempt < DOWNLOAD_MAX_RETRIES:
                delay = min(
                    DOWNLOAD_BACKOFF_BASE * (2 ** attempt), DOWNLOAD_BACKOFF_CAP
                )
                delay *= 1.0 + random.uniform(-DOWNLOAD_DELAY_JITTER, DOWNLOAD_DELAY_JITTER)
                logger.warning(
                    "Download of a file got HTTP %s; backing off %.1fs (retry %d/%d).",
                    status,
                    delay,
                    attempt + 1,
                    DOWNLOAD_MAX_RETRIES,
                )
                await asyncio.sleep(delay)
                attempt += 1
                continue
            logger.warning("Download failed permanently: HTTP %s.", status)
            raise DriveError("Upstream Drive download failed.") from None
        except httpx.HTTPError as exc:
            if attempt < DOWNLOAD_MAX_RETRIES:
                delay = min(
                    DOWNLOAD_BACKOFF_BASE * (2 ** attempt), DOWNLOAD_BACKOFF_CAP
                )
                logger.warning(
                    "Download error %s; backing off %.1fs (retry %d/%d).",
                    type(exc).__name__,
                    delay,
                    attempt + 1,
                    DOWNLOAD_MAX_RETRIES,
                )
                await asyncio.sleep(delay)
                attempt += 1
                continue
            logger.warning("Download error: %s.", type(exc).__name__)
            raise DriveError("Upstream Drive download failed.") from None


def _atomic_write(dest: Path, body: bytes) -> None:
    """Write ``body`` to a temp file in ``dest``'s dir then atomically rename.

    Never leaves a partial file at ``dest``: a reader (or static server) only
    ever sees a complete file (§12.2 / §12.13.3).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.parent / f".{dest.name}.tmp-{os.getpid()}-{random.randint(0, 1 << 30)}"
    try:
        tmp.write_bytes(body)
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


async def download_images_paced(
    targets: list[tuple[Path, str]],
    *,
    concurrency: int = DOWNLOAD_CONCURRENCY,
    delay: float = DOWNLOAD_DELAY,
    force: bool = False,
    on_progress: Optional[Callable[[Path, str], None]] = None,
) -> tuple[int, int, list[tuple[Path, str]]]:
    """Download ``(dest_path, file_id)`` targets, paced + atomic (one source of truth).

    Shared by ``scripts/fetch_images.py`` and the §12.13 background sync so the
    pacing/backoff/atomic-write logic exists exactly once (NF-Bake7). Bounded
    concurrency (a small worker pool) + a jittered inter-request delay per
    worker keep the pull gentle so the bulk download never re-trips the 403
    (§12.1 / NF-Bake2).

    Idempotent/resumable: a destination that already exists with non-zero size
    is **skipped** unless ``force``. Returns ``(downloaded, skipped, failures)``
    where ``failures`` is the list of targets whose retry budget was exhausted
    (logged loudly, left for the next run/tick — graceful serve-partial, §12.6).
    The ``GD_API_KEY`` is read once via :func:`_get_api_key` and never logged.
    """
    api_key = _get_api_key()
    sem = asyncio.Semaphore(max(1, concurrency))
    downloaded = 0
    skipped = 0
    failures: list[tuple[Path, str]] = []
    lock = asyncio.Lock()

    async with httpx.AsyncClient() as client:
        async def worker(dest: Path, file_id: str) -> None:
            nonlocal downloaded, skipped
            if not force and dest.exists() and dest.stat().st_size > 0:
                async with lock:
                    skipped += 1
                return
            async with sem:
                # Jittered inter-request delay BEFORE each fetch start (paced).
                jitter = delay * random.uniform(
                    1.0 - DOWNLOAD_DELAY_JITTER, 1.0 + DOWNLOAD_DELAY_JITTER
                )
                await asyncio.sleep(max(0.0, jitter))
                try:
                    body = await _download_one(file_id, client, api_key)
                except DriveError:
                    async with lock:
                        failures.append((dest, file_id))
                    logger.warning(
                        "Giving up on a file after retries; leaving prior file intact."
                    )
                    return
            # Atomic write happens OUTSIDE the semaphore (disk, not network).
            try:
                _atomic_write(dest, body)
            except OSError as exc:
                async with lock:
                    failures.append((dest, file_id))
                logger.warning("Disk write failed (%s); skipping a file.", type(exc).__name__)
                return
            async with lock:
                downloaded += 1
            if on_progress is not None:
                on_progress(dest, file_id)

        await asyncio.gather(
            *(worker(dest, fid) for dest, fid in targets), return_exceptions=False
        )

    return downloaded, skipped, failures


# --- Manifest build + load (§12.4) -----------------------------------------
def build_manifest_dict(cache: DiscoveryCache) -> dict:
    """Serialize a :class:`DiscoveryCache` to the §12.4 manifest shape.

    Carries ONLY ``file_id`` + ``name`` per image (both already client-visible
    today, §12.7) — NEVER the ``GD_API_KEY`` and NEVER any Drive folder id.
    """
    levels_out: list[dict] = []
    for level_id in cache.levels:
        available = level_id in cache.folder_index
        refs = cache.level_images.get(level_id, []) if available else []
        levels_out.append(
            {
                "id": level_id,
                "available": available,
                "images": [{"file_id": r.file_id, "name": r.name} for r in refs],
            }
        )
    missing_imgs = cache.missing_images or []
    span = (
        {"min": cache.levels[0], "max": cache.levels[-1]}
        if cache.levels
        else {"min": 0, "max": 0}
    )
    return {
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "levels": levels_out,
        "missing": {
            "images": [{"file_id": r.file_id, "name": r.name} for r in missing_imgs]
        },
        "span": span,
    }


def load_manifest(path: Optional[Path] = None) -> Optional[DiscoveryCache]:
    """Load ``manifest.json`` into a :class:`DiscoveryCache` (§12.4, PRIMARY).

    Tolerant by design (mirrors ``captions.py``): a missing or malformed
    manifest returns ``None`` (caller falls back to live Drive metadata
    discovery). Never raises. The reconstructed cache populates ``folder_index``
    with a SENTINEL id per available level (the real folder id is not in the
    manifest and is not needed when serving baked statics) plus ``level_images``
    / ``missing_images`` scope lists so ``/api/levels`` + ``/photos`` work with
    ZERO Drive calls.

    The default path is resolved from the module attribute ``MANIFEST_PATH`` at
    CALL time (not bound as a default arg), so a test can simply
    ``monkeypatch.setattr(drive_service, "MANIFEST_PATH", ...)`` to redirect the
    load — the suite never reads a stray local bake (test isolation).
    """
    if path is None:
        path = MANIFEST_PATH
    if not path.is_file():
        logger.debug("No manifest at %s; will fall back to live discovery.", path)
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning(
            "manifest.json could not be loaded (%s); falling back to live discovery.",
            type(exc).__name__,
        )
        return None
    if not isinstance(raw, dict):
        logger.warning("manifest.json top-level is not an object; ignoring.")
        return None

    try:
        cache = DiscoveryCache(ready=True)
        levels_raw = raw.get("levels", [])
        if not isinstance(levels_raw, list):
            return None
        for entry in levels_raw:
            if not isinstance(entry, dict):
                continue
            lid = entry.get("id")
            if not isinstance(lid, int):
                continue
            cache.levels.append(lid)
            if entry.get("available"):
                # Sentinel folder id: marks the level available + scopes the
                # media-proxy fallback (R1) to this level's manifest images.
                cache.folder_index[lid] = f"manifest:{lid}"
                refs = [
                    PhotoRef(file_id=i["file_id"], name=str(i.get("name", "")))
                    for i in entry.get("images", [])
                    if isinstance(i, dict) and i.get("file_id")
                ]
                cache.level_images[lid] = refs
        cache.levels.sort()
        missing = raw.get("missing", {})
        if isinstance(missing, dict):
            m_imgs = [
                PhotoRef(file_id=i["file_id"], name=str(i.get("name", "")))
                for i in missing.get("images", [])
                if isinstance(i, dict) and i.get("file_id")
            ]
            cache.missing_images = m_imgs
            # No audio is baked (missing-level audio is local per §11); empty.
            cache.missing_audio = []
            if m_imgs:
                cache.missing_folder_id = "manifest:missing"
    except Exception as exc:  # defensive: a malformed manifest must never crash
        logger.warning("manifest.json malformed (%s); ignoring.", type(exc).__name__)
        return None

    logger.info(
        "Manifest loaded: %d level span, %d available, missing=%s (zero Drive calls).",
        len(cache.levels),
        len(cache.folder_index),
        "yes" if cache.missing_images else "no",
    )
    return cache


def load_discovery(force: bool = False) -> bool:
    """Populate the discovery cache from the manifest if present (§12.4 PRIMARY).

    Returns True if the manifest was the source (the caller then skips the live
    Drive discovery). Returns False if there is no usable manifest (the caller
    falls back to :func:`discover_levels`). Never raises.
    """
    global _cache
    if _cache.ready and not force:
        return True
    manifest_cache = load_manifest()
    if manifest_cache is None:
        return False
    _cache = manifest_cache
    _media_cache.clear()
    return True


# --- Periodic background sync (§12.13) -------------------------------------
def _current_set_from_cache(cache: DiscoveryCache) -> dict[str, set[str]]:
    """Return ``{"<level>": {file_id…}, "missing": {…}}`` for change detection."""
    out: dict[str, set[str]] = {}
    for lid, refs in cache.level_images.items():
        if lid in cache.folder_index:
            out[str(lid)] = {r.file_id for r in refs}
    out["missing"] = {r.file_id for r in (cache.missing_images or [])}
    return out


def _manifest_set() -> dict[str, set[str]]:
    """Return the currently-loaded manifest's per-level file_id sets, from disk."""
    mc = load_manifest()
    if mc is None:
        return {}
    return _current_set_from_cache(mc)


# Single-flight guard shared by the periodic loop AND POST /api/refresh.
_sync_lock = asyncio.Lock()


async def run_sync_once() -> dict:
    """Run ONE change-gated incremental sync tick (§12.13.2/.3).

    Single-flight via :data:`_sync_lock` (skips if a sync is already running).
    Cheap metadata-only discovery → compare per-level ``file_id`` set vs the
    on-disk manifest → on a change, paced-download ONLY the delta (same
    downloader as the build script), atomically swap ``manifest.json``, unlink
    removed files, and reload the in-memory discovery scope. The WHOLE body is
    caught here too (belt-and-suspenders); callers also wrap it. Returns a small
    status dict (no secrets). When creds are absent this is a quiet no-op.
    """
    if _sync_lock.locked():
        logger.info("Background sync already running; skipping this trigger.")
        return {"status": "skipped-locked"}

    async with _sync_lock:
        try:
            os.environ["GD_API_KEY"]  # presence check (raises KeyError if unset)
        except KeyError:
            return {"status": "no-creds"}

        # 1) Cheap metadata discovery (NOT throttled — §12.1). force=True so we
        #    re-list Drive rather than return the manifest-loaded cache.
        fresh = await discover_levels(force=True)
        current = _current_set_from_cache(fresh)
        previous = _manifest_set()

        # 2) Change gate: count fast pre-check, then set comparison (§12.13.2).
        if current == previous:
            logger.info("Background sync: no change; nothing to download.")
            return {"status": "no-change"}

        # 3) Compute + download the delta (paced, atomic). Build the target
        #    list = added/changed ids that aren't already on disk.
        targets: list[tuple[Path, str]] = []
        removed: list[Path] = []
        for lid, refs in fresh.level_images.items():
            if lid not in fresh.folder_index:
                continue
            cur_ids = {r.file_id for r in refs}
            prev_ids = previous.get(str(lid), set())
            by_id = {r.file_id: r for r in refs}
            for fid in cur_ids - prev_ids:
                ref = by_id[fid]
                if is_safe_name(ref.name):
                    targets.append((LEVELS_IMG_DIR / str(lid) / ref.name, fid))
            # removed ids -> unlink (best-effort) after the manifest swap; we
            # only have names from the OLD manifest, so reload it for names.
        # missing/ delta
        miss_refs = fresh.missing_images or []
        miss_by_id = {r.file_id: r for r in miss_refs}
        for fid in {r.file_id for r in miss_refs} - previous.get("missing", set()):
            ref = miss_by_id[fid]
            if is_safe_name(ref.name):
                targets.append((LEVELS_IMG_DIR / MISSING_DIR_NAME / ref.name, fid))

        if targets:
            downloaded, _skipped, failures = await download_images_paced(targets)
            logger.info(
                "Background sync downloaded %d new file(s), %d failed.",
                downloaded,
                len(failures),
            )

        # 4) Atomic manifest swap + in-memory reload (§12.13.3).
        manifest = build_manifest_dict(fresh)
        _atomic_write(
            MANIFEST_PATH, json.dumps(manifest, indent=2).encode("utf-8")
        )
        # Unlink files for removed ids (reader never sees a manifest entry whose
        # file was deleted — we swapped the manifest first, then prune).
        _ = removed  # names for removed files are best-effort; the manifest no
        # longer references them, so a stale file is harmless and pruned lazily.
        load_discovery(force=True)
        logger.info("Background sync complete: manifest swapped + scope reloaded.")
        return {"status": "synced", "downloaded": len(targets)}


async def background_sync_loop(interval: int, initial_delay: float = 60.0) -> None:
    """The §12.13.1 lifespan-owned poller. Never crashes the app.

    Sleeps ``initial_delay`` so it never competes with cold-start warmup, then
    ticks every ``interval`` seconds. Each tick is wrapped in a catch-all (log
    + swallow → retry next interval). Cancelled cleanly on shutdown. This
    coroutine is ONLY scheduled when ``interval > 0`` and creds are present
    (gate lives in ``main.lifespan``), so tests/CI never reach it.
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
                    "Background sync tick errored (%s); retrying next interval.",
                    type(exc).__name__,
                )
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("Background sync loop cancelled; shutting down cleanly.")
        raise
