"""Shared fixtures for the Archive 19 backend test suite (T6b).

All Google Drive access is mocked — the suite is hermetic and offline:

- ``drive_service.list_children`` is the single network funnel used by
  discovery, the ``missing/`` fallback, and the in-scope guard. We patch it to
  serve a fake Drive tree keyed by folder id, so no real ``httpx`` request is
  made for those paths.
- ``resolve_media`` builds its own ``httpx.AsyncClient`` to stream bytes; we
  patch the module's ``httpx.AsyncClient`` to one backed by an
  ``httpx.MockTransport`` so the streaming byte fetch is also offline.

``GD_API_KEY`` / ``GD_ROOT_FOLDER`` are set to dummy values for the session so
config reads succeed without ever contacting Google.
"""

from __future__ import annotations

import importlib

import httpx
import pytest

# Dummy config BEFORE importing the app, so module import + lifespan never try
# to read a real key. These are placeholders; no network ever happens.
import os

os.environ.setdefault("GD_API_KEY", "TEST-DUMMY-KEY-do-not-use")
os.environ.setdefault("GD_ROOT_FOLDER", "ROOT_FOLDER_ID")

from app import drive_service  # noqa: E402
from app import main as main_module  # noqa: E402


# --- Fake Drive tree -------------------------------------------------------
# A realistic confirmed structure (ARCHITECTURE §5.1 / REQUIREMENTS §7):
#   present numbered folders: 1, 2, 8  (subset; enough to prove dynamic span)
#   a "missing/" folder holding stock images + audio
FOLDER_MIME = drive_service.FOLDER_MIME

ROOT_ID = "ROOT_FOLDER_ID"

# Drive ids for the child folders under root.
FOLDER_1 = "drv_folder_1"
FOLDER_2 = "drv_folder_2"
FOLDER_8 = "drv_folder_8"
MISSING_ID = "drv_missing"

# Image ids inside present level folders.
IMG_1A = "img_1a"
IMG_1B = "img_1b"
IMG_2A = "img_2a"
# Folder 8 is present but EMPTY (R5: empty-but-present -> missing fallback).

# Stock assets inside the missing/ folder.
MISS_IMG_A = "miss_img_a"
MISS_IMG_B = "miss_img_b"
MISS_AUD_A = "miss_aud_a"
MISS_AUD_B = "miss_aud_b"


def _default_tree() -> dict[str, list[dict]]:
    """Return a fresh copy of the fake Drive tree (folder_id -> children)."""
    return {
        ROOT_ID: [
            {"id": FOLDER_1, "name": "1", "mimeType": FOLDER_MIME},
            {"id": FOLDER_2, "name": "2", "mimeType": FOLDER_MIME},
            {"id": FOLDER_8, "name": "8", "mimeType": FOLDER_MIME},
            {"id": MISSING_ID, "name": "missing", "mimeType": FOLDER_MIME},
            # A non-numeric, non-folder sibling that must be ignored.
            {"id": "readme", "name": "README", "mimeType": "text/plain"},
        ],
        FOLDER_1: [
            {"id": IMG_1A, "name": "1.1.jpeg", "mimeType": "image/jpeg"},
            {"id": IMG_1B, "name": "1.2.jpeg", "mimeType": "image/jpeg"},
        ],
        FOLDER_2: [
            {"id": IMG_2A, "name": "2.1.jpeg", "mimeType": "image/jpeg"},
        ],
        FOLDER_8: [],  # present but empty
        MISSING_ID: [
            {"id": MISS_IMG_A, "name": "stock_a.png", "mimeType": "image/png"},
            {"id": MISS_IMG_B, "name": "stock_b.jpg", "mimeType": "image/jpeg"},
            {"id": MISS_AUD_A, "name": "stock_a.mp3", "mimeType": "audio/mpeg"},
            {"id": MISS_AUD_B, "name": "stock_b.mp3", "mimeType": "audio/mpeg"},
        ],
    }


@pytest.fixture
def drive_tree():
    """Mutable fake Drive tree the test can edit (e.g. for /api/refresh)."""
    return _default_tree()


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset the module-level discovery cache before & after each test."""
    drive_service._cache = drive_service.DiscoveryCache()
    yield
    drive_service._cache = drive_service.DiscoveryCache()


@pytest.fixture
def patched_drive(monkeypatch, drive_tree):
    """Patch ``list_children`` to serve ``drive_tree`` (no real network).

    Returns the tree dict so tests can mutate it (folder add/remove) and then
    call ``POST /api/refresh`` to observe re-discovery.
    """

    async def fake_list_children(folder_id, client):
        # Mirror the real signature; ignore the (unused-here) client object.
        if folder_id not in drive_tree:
            # An unknown folder behaves like an empty folder (no children).
            return []
        return list(drive_tree[folder_id])

    monkeypatch.setattr(drive_service, "list_children", fake_list_children)
    return drive_tree


# --- Media-byte mock (for resolve_media's own httpx client) ----------------
# Maps Drive file id -> (content_type, body_bytes) for the streaming proxy.
MEDIA_BYTES: dict[str, tuple[str, bytes]] = {
    IMG_1A: ("image/jpeg", b"\xff\xd8\xff\xe0JPEGDATA"),
    IMG_1B: ("image/jpeg", b"\xff\xd8\xff\xe0JPEGDATA2"),
    IMG_2A: ("image/jpeg", b"\xff\xd8\xff\xe0JPEGDATA3"),
    MISS_IMG_A: ("image/png", b"\x89PNG\r\n\x1a\nPNGDATA"),
    MISS_IMG_B: ("image/jpeg", b"\xff\xd8\xff\xe0MISSJPEG"),
    MISS_AUD_A: ("audio/mpeg", b"ID3MP3DATA_A"),
    MISS_AUD_B: ("audio/mpeg", b"ID3MP3DATA_B"),
}


def _media_handler(request: httpx.Request) -> httpx.Response:
    """MockTransport handler emulating Drive files.get?alt=media."""
    # URL form: https://www.googleapis.com/drive/v3/files/{file_id}
    file_id = request.url.path.rsplit("/", 1)[-1]
    if file_id in MEDIA_BYTES:
        content_type, body = MEDIA_BYTES[file_id]
        return httpx.Response(200, headers={"content-type": content_type}, content=body)
    # Upstream "not found" — exercises the 502 path in resolve_media.
    return httpx.Response(404, content=b"not found")


@pytest.fixture
def patched_media(monkeypatch):
    """Back ``resolve_media``'s httpx client with a MockTransport (no network).

    Returns a holder whose ``.last_request`` captures the outgoing Drive
    request so a test can assert the key is sent upstream but never returned to
    the client.
    """
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["last_request"] = request
        return _media_handler(request)

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return real_async_client(transport=transport, **kwargs)

    monkeypatch.setattr(drive_service.httpx, "AsyncClient", client_factory)
    return captured


@pytest.fixture
def client(patched_drive):
    """A TestClient with discovery pre-built from the fake tree.

    Using the context manager triggers the lifespan handler, which calls
    ``discover_levels(force=True)`` against the patched ``list_children``.
    """
    from fastapi.testclient import TestClient

    with TestClient(main_module.app) as c:
        yield c
