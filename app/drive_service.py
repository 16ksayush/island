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

import logging
import os
import random
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional

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

        # Missing-level fallback: re-roll a FRESH random image + audio per call
        # (R3) from the cached missing/ pool.
        missing_images, missing_audio = await _ensure_missing_scope(client)
        if not missing_images or not missing_audio:
            raise DriveError("Missing fallback folder lacks an image+audio pair.")
        img = random.choice(missing_images)
        aud = random.choice(missing_audio)
        return LevelPhotos(
            level=level_id,
            available=False,
            images=[PhotoRef(file_id=img.file_id, name=img.name)],
            fallback_audio=PhotoRef(file_id=aud.file_id, name=aud.name),
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
