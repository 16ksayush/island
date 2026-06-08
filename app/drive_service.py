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
from dataclasses import dataclass, field
from typing import AsyncIterator, Awaitable, Callable, Optional

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


# --- Cached discovery state (§5.1) -----------------------------------------
@dataclass
class DiscoveryCache:
    """In-memory level -> Drive-folder map, built once and cached (R2)."""

    folder_index: dict[int, str] = field(default_factory=dict)
    missing_folder_id: Optional[str] = None
    levels: list[int] = field(default_factory=list)
    # True once discovery has successfully run at least once.
    ready: bool = False


# Module-level singleton cache. Rebuilt only by ``discover_levels(force=True)``
# (startup) or via the manual ``POST /api/refresh`` route.
_cache = DiscoveryCache()


def get_cache() -> DiscoveryCache:
    """Return the current (possibly empty) discovery cache."""
    return _cache


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
    except DriveError:
        logger.warning("Discovery failed: Drive unreachable; serving prior cache.")
        return _cache

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

    _cache = DiscoveryCache(
        folder_index=folder_index,
        missing_folder_id=missing_folder_id,
        levels=levels,
        ready=True,
    )
    logger.info(
        "Discovery complete: %d numbered folders, missing=%s, span=%d levels.",
        len(folder_index),
        "yes" if missing_folder_id else "no",
        len(levels),
    )
    return _cache


# --- Photos (§4.1) ---------------------------------------------------------
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


async def _list_missing_assets(
    client: httpx.AsyncClient,
) -> tuple[list[dict], list[dict]]:
    """Return ``(images, audio)`` items from the Drive ``missing/`` folder."""
    if not _cache.missing_folder_id:
        raise DriveError("No 'missing/' folder is configured for fallback.")
    items = await list_children(_cache.missing_folder_id, client)
    images = _filter_by_mime_prefix(items, IMAGE_MIME_PREFIX)
    audio = _filter_by_mime_prefix(items, AUDIO_MIME_PREFIX)
    return images, audio


async def get_level_photos(level_id: int) -> LevelPhotos:
    """Return image refs for ``level_id`` (+ fallback audio when missing).

    - Present & non-empty folder -> ``available=True``, its images, no audio.
    - Absent OR empty-but-present (R5) -> ``available=False`` and a FRESH random
      image + random audio re-rolled from ``missing/`` on EVERY call (R3).

    Raises :class:`DriveError` on upstream failure.
    """
    folder_id = _cache.folder_index.get(level_id)
    async with httpx.AsyncClient() as client:
        if folder_id is not None:
            items = await list_children(folder_id, client)
            images = _filter_by_mime_prefix(items, IMAGE_MIME_PREFIX)
            if images:
                return LevelPhotos(
                    level=level_id,
                    available=True,
                    images=[
                        PhotoRef(file_id=i["id"], name=str(i.get("name", "")))
                        for i in images
                    ],
                    fallback_audio=None,
                )
            # Present but empty -> fall through to missing fallback (R5).

        # Missing-level fallback: re-roll a fresh image + audio (R3).
        missing_images, missing_audio = await _list_missing_assets(client)
        if not missing_images or not missing_audio:
            raise DriveError("Missing fallback folder lacks an image+audio pair.")
        img = random.choice(missing_images)
        aud = random.choice(missing_audio)
        return LevelPhotos(
            level=level_id,
            available=False,
            images=[PhotoRef(file_id=img["id"], name=str(img.get("name", "")))],
            fallback_audio=PhotoRef(file_id=aud["id"], name=str(aud.get("name", ""))),
        )


# --- Media proxy (§4 / R1 / R6) --------------------------------------------
@dataclass
class MediaStream:
    """A streaming media fetch: byte iterator + upstream Content-Type + cleanup."""

    content_type: str
    body: AsyncIterator[bytes]
    aclose: Callable[[], Awaitable[None]]


async def _file_in_scope(level_id: int, file_id: str) -> bool:
    """Return True iff ``file_id`` is a child of the level folder OR ``missing/``.

    R1: this is the open-proxy guard. We re-list the relevant folder(s) and
    confirm membership before any byte is streamed; unknown ids -> not in scope.
    """
    candidate_folders: list[str] = []
    folder_id = _cache.folder_index.get(level_id)
    if folder_id is not None:
        candidate_folders.append(folder_id)
    if _cache.missing_folder_id:
        candidate_folders.append(_cache.missing_folder_id)
    if not candidate_folders:
        return False

    async with httpx.AsyncClient() as client:
        for fid in candidate_folders:
            items = await list_children(fid, client)
            if any(it.get("id") == file_id for it in items):
                return True
    return False


async def resolve_media(level_id: int, file_id: str) -> Optional[MediaStream]:
    """Resolve a Drive ``file_id`` to a streaming fetch, scoped to ``level_id``.

    Returns ``None`` if the id is not in scope (route -> 404, R1). Otherwise
    returns a :class:`MediaStream` whose ``content_type`` mirrors the upstream
    Drive ``Content-Type`` (R6 — image/* vs audio/mpeg, never hardcoded).

    Raises :class:`DriveError` on upstream failure (route -> 502).
    """
    if not await _file_in_scope(level_id, file_id):
        return None

    api_key = _get_api_key()
    params = {
        "alt": "media",
        "supportsAllDrives": "true",
        "key": api_key,
    }
    client = httpx.AsyncClient(timeout=_TIMEOUT)
    try:
        req = client.build_request(
            "GET", f"{DRIVE_API_BASE}/files/{file_id}", params=params
        )
        resp = await client.send(req, stream=True)
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        await client.aclose()
        logger.warning("Drive files.get failed: HTTP %s", status)
        raise DriveError("Upstream Drive media request failed.") from None
    except httpx.HTTPError as exc:
        await client.aclose()
        logger.warning("Drive files.get error: %s", type(exc).__name__)
        raise DriveError("Upstream Drive media request failed.") from None

    # R6: echo the upstream Content-Type verbatim (fallback to octet-stream).
    content_type = resp.headers.get("content-type", "application/octet-stream")

    async def _cleanup() -> None:
        await resp.aclose()
        await client.aclose()

    return MediaStream(content_type=content_type, body=resp.aiter_bytes(), aclose=_cleanup)
