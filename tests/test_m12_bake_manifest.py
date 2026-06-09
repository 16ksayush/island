"""M12 hermetic tests — build-time bake + manifest discovery + guarded static/proxy
URLs + background sync (docs §12.x).

All Google Drive access is mocked; NO network and NO real disk paths we don't own
are touched. Each test controls its inputs via ``tmp_path`` + ``monkeypatch`` and
asserts the M12 contract:

1. Manifest-PRIMARY discovery (zero Drive calls).
2. Manifest FALLBACK to live discovery (covered elsewhere; reconfirmed green).
3. ``_ref`` static-vs-proxy selection (baked file present -> static; else proxy).
4. ``is_safe_name`` rejects traversal; ``_ref`` never emits a static url for it.
5. Sync enable-gate ``_image_sync_interval`` + lifespan starts no task by default.
6. ``run_sync_once`` no-creds short-circuit (no exception / no network).
7. ``/api/refresh`` re-reads manifest+captions, 200, sync-disabled no-op.
8. Paced downloader retries 403 -> 200 then writes (sleep patched to ~0).
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import captions as captions_module
from app import drive_service
from app import main as main_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _write_manifest(path, levels, missing_images=None):
    """Write a §12.4-shaped manifest.json to ``path`` and return the dict."""
    manifest = {
        "generated_at": "2026-06-09T00:00:00Z",
        "levels": levels,
        "missing": {"images": missing_images or []},
        "span": {
            "min": levels[0]["id"] if levels else 0,
            "max": levels[-1]["id"] if levels else 0,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _point_manifest_at(monkeypatch, manifest_path):
    """Redirect drive_service.load_manifest to read ``manifest_path``.

    ``load_manifest``'s default ``path=MANIFEST_PATH`` is bound at def-time, so
    monkeypatching the module constant alone does not redirect it. We wrap the
    real loader so it reads our tmp manifest while keeping all parse logic under
    test. Also set the constants so any disk lookups in main/_ref are consistent.
    """
    real_load_manifest = drive_service.load_manifest

    def patched_load_manifest(path=manifest_path):
        return real_load_manifest(manifest_path)

    monkeypatch.setattr(drive_service, "load_manifest", patched_load_manifest)
    monkeypatch.setattr(drive_service, "MANIFEST_PATH", manifest_path)


class _NetGuard:
    """Drop-in for ``list_children`` that records calls and refuses to network.

    Used to *prove* the manifest-primary path makes zero Drive list calls — if
    it is ever invoked the test fails loudly.
    """

    def __init__(self):
        self.calls = 0

    async def __call__(self, folder_id, client):  # pragma: no cover - guard
        self.calls += 1
        raise AssertionError(
            f"Drive list_children was called for {folder_id!r}; manifest path "
            "must make ZERO Drive calls."
        )


# ---------------------------------------------------------------------------
# 1. Manifest-PRIMARY discovery — zero Drive calls
# ---------------------------------------------------------------------------
def test_manifest_primary_zero_drive_calls(monkeypatch, tmp_path):
    """A controlled manifest populates the cache; /api/levels + /photos serve it
    with NO Drive list/get invocations."""
    img_dir = tmp_path / "levels"
    manifest_path = img_dir / "manifest.json"
    _write_manifest(
        manifest_path,
        levels=[
            {"id": 0, "available": False, "images": []},
            {
                "id": 1,
                "available": True,
                "images": [
                    {"file_id": "mid_1a", "name": "1.1.jpeg"},
                    {"file_id": "mid_1b", "name": "1.2.jpeg"},
                ],
            },
            {"id": 2, "available": False, "images": []},
            {
                "id": 3,
                "available": True,
                "images": [{"file_id": "mid_3a", "name": "3.1.jpeg"}],
            },
        ],
        missing_images=[{"file_id": "mid_miss", "name": "stock.png"}],
    )

    _point_manifest_at(monkeypatch, manifest_path)
    monkeypatch.setattr(drive_service, "LEVELS_IMG_DIR", img_dir)

    guard = _NetGuard()
    monkeypatch.setattr(drive_service, "list_children", guard)

    # load_discovery should report the manifest as the source (True).
    assert drive_service.load_discovery(force=True) is True

    with TestClient(main_module.app) as c:
        levels = c.get("/api/levels").json()["levels"]
        assert {l["id"] for l in levels} == {0, 1, 2, 3}
        avail = {l["id"]: l["available"] for l in levels}
        assert avail == {0: False, 1: True, 2: False, 3: True}

        photos = c.get("/api/levels/1/photos").json()
        assert photos["available"] is True
        assert {i["file_id"] for i in photos["images"]} == {"mid_1a", "mid_1b"}

    assert guard.calls == 0, "manifest path must make ZERO Drive calls"


# ---------------------------------------------------------------------------
# 2. Manifest FALLBACK — no manifest -> live (mocked) Drive discovery
# ---------------------------------------------------------------------------
def test_manifest_absent_falls_back_to_live_discovery(monkeypatch, tmp_path, patched_drive):
    """With no manifest file, load_discovery returns False (signalling fallback);
    the lifespan then runs live Drive metadata discovery (mocked), so /api/levels
    reflects the fake tree (1,2,8…) — today's behavior, still green."""
    missing_manifest = tmp_path / "levels" / "manifest.json"
    _point_manifest_at(monkeypatch, missing_manifest)

    # 1) The manifest path declines (no file) -> fallback signalled.
    drive_service._cache = drive_service.DiscoveryCache()
    assert drive_service.load_discovery(force=True) is False

    # 2) Boot the app: lifespan sees load_discovery() False and runs the live
    #    (mocked) discovery. /api/levels then reflects the fake Drive tree.
    with TestClient(main_module.app) as c:
        levels = c.get("/api/levels").json()["levels"]
    avail = {l["id"]: l["available"] for l in levels}
    assert avail.get(1) is True
    assert avail.get(2) is True
    # Level 8 present-but-empty -> in folder_index; span covers 0..8.
    assert max(l["id"] for l in levels) >= 8


# ---------------------------------------------------------------------------
# 3. _ref static-vs-proxy selection
# ---------------------------------------------------------------------------
def test_ref_static_when_baked_proxy_when_not(monkeypatch, tmp_path):
    """Baked file present -> /static url; sibling un-baked -> /api proxy url.
    Captions attach for BOTH (key (level, name) unchanged)."""
    static_dir = tmp_path / "static"
    levels_img_dir = static_dir / "img" / "levels"
    manifest_path = levels_img_dir / "manifest.json"

    _write_manifest(
        manifest_path,
        levels=[
            {
                "id": 1,
                "available": True,
                "images": [
                    {"file_id": "fid_baked", "name": "1.1.jpeg"},
                    {"file_id": "fid_unbaked", "name": "1.2.jpeg"},
                ],
            }
        ],
    )
    # Bake ONLY 1.1.jpeg on disk under levels/1/.
    baked = levels_img_dir / "1" / "1.1.jpeg"
    baked.parent.mkdir(parents=True, exist_ok=True)
    baked.write_bytes(b"\xff\xd8\xff\xe0FAKEJPEG")

    # Point BOTH modules' dir constants at the tmp tree.
    _point_manifest_at(monkeypatch, manifest_path)
    monkeypatch.setattr(drive_service, "LEVELS_IMG_DIR", levels_img_dir)
    monkeypatch.setattr(main_module, "LEVELS_IMG_DIR", levels_img_dir)

    # Captions for BOTH filenames keyed by (level=1, name).
    monkeypatch.setattr(
        captions_module,
        "_captions",
        {
            "1": {
                "1.1.jpeg": {"sea": "baked sea", "horror": "baked horror"},
                "1.2.jpeg": {"sea": "unbaked sea", "horror": "unbaked horror"},
            }
        },
    )

    drive_service._cache = drive_service.DiscoveryCache()
    assert drive_service.load_discovery(force=True) is True

    with TestClient(main_module.app) as c:
        photos = c.get("/api/levels/1/photos").json()

    by_id = {i["file_id"]: i for i in photos["images"]}
    assert by_id["fid_baked"]["url"] == "/static/img/levels/1/1.1.jpeg"
    assert by_id["fid_unbaked"]["url"] == "/api/levels/1/media/fid_unbaked"
    # Caption attaches for BOTH regardless of static/proxy.
    assert by_id["fid_baked"]["caption"]["sea"] == "baked sea"
    assert by_id["fid_unbaked"]["caption"]["horror"] == "unbaked horror"


# ---------------------------------------------------------------------------
# 4. is_safe_name + _ref never emits static for unsafe name
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad", ["", ".", "..", "a/b", "a\\b", "../x", "x/../y"])
def test_is_safe_name_rejects(bad):
    assert drive_service.is_safe_name(bad) is False


@pytest.mark.parametrize("good", ["9.1.jpeg", "1.1.jpeg", "stock_a.png"])
def test_is_safe_name_accepts(good):
    assert drive_service.is_safe_name(good) is True


def test_ref_unsafe_name_falls_back_to_proxy(monkeypatch, tmp_path):
    """An unsafe image name must NEVER produce a /static url — even if a file
    happened to exist — the proxy is used."""
    static_dir = tmp_path / "static"
    levels_img_dir = static_dir / "img" / "levels"
    manifest_path = levels_img_dir / "manifest.json"

    _write_manifest(
        manifest_path,
        levels=[
            {
                "id": 1,
                "available": True,
                # Hostile traversal name; load_manifest keeps name verbatim.
                "images": [{"file_id": "fid_evil", "name": "../evil.jpeg"}],
            }
        ],
    )
    _point_manifest_at(monkeypatch, manifest_path)
    monkeypatch.setattr(drive_service, "LEVELS_IMG_DIR", levels_img_dir)
    monkeypatch.setattr(main_module, "LEVELS_IMG_DIR", levels_img_dir)

    drive_service._cache = drive_service.DiscoveryCache()
    assert drive_service.load_discovery(force=True) is True

    with TestClient(main_module.app) as c:
        photos = c.get("/api/levels/1/photos").json()

    url = photos["images"][0]["url"]
    assert url == "/api/levels/1/media/fid_evil"
    assert not url.startswith("/static/")


# ---------------------------------------------------------------------------
# 5. Sync enable-gate
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, 0),       # unset
        ("", 0),         # empty
        ("0", 0),
        ("-5", 0),
        ("abc", 0),
        ("1800", 1800),
        ("  ", 0),
    ],
)
def test_image_sync_interval(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("IMAGE_SYNC_INTERVAL_SECONDS", raising=False)
    else:
        monkeypatch.setenv("IMAGE_SYNC_INTERVAL_SECONDS", raw)
    assert main_module._image_sync_interval() == expected


def test_lifespan_starts_no_sync_task_by_default(monkeypatch, patched_drive):
    """Default test state (interval unset) -> lifespan creates NO sync task and
    never enters background_sync_loop. We fail loudly if either is reached."""
    monkeypatch.delenv("IMAGE_SYNC_INTERVAL_SECONDS", raising=False)

    created = {"count": 0}
    real_create_task = asyncio.create_task

    def spy_create_task(coro, *args, **kwargs):
        # Only count the sync loop coroutine, not unrelated tasks.
        name = getattr(coro, "__name__", "") or getattr(
            getattr(coro, "cr_code", None), "co_name", ""
        )
        if "background_sync_loop" in name:
            created["count"] += 1
        return real_create_task(coro, *args, **kwargs)

    monkeypatch.setattr(main_module.asyncio, "create_task", spy_create_task)

    async def boom(*a, **k):  # pragma: no cover - must never be scheduled
        raise AssertionError("background_sync_loop must NOT run when disabled")

    monkeypatch.setattr(drive_service, "background_sync_loop", boom)

    with TestClient(main_module.app):
        pass
    assert created["count"] == 0


# ---------------------------------------------------------------------------
# 6. run_sync_once no-creds short-circuit
# ---------------------------------------------------------------------------
def test_run_sync_once_no_creds_short_circuits(monkeypatch):
    """With GD_API_KEY unset, run_sync_once returns a no-creds no-op — no
    exception, no Drive call."""
    monkeypatch.delenv("GD_API_KEY", raising=False)

    async def boom_discover(*a, **k):  # pragma: no cover
        raise AssertionError("no-creds path must not discover/network")

    monkeypatch.setattr(drive_service, "discover_levels", boom_discover)

    result = asyncio.run(drive_service.run_sync_once())
    assert result == {"status": "no-creds"}


# ---------------------------------------------------------------------------
# 7. /api/refresh re-reads manifest + captions, 200, sync disabled = no-op
# ---------------------------------------------------------------------------
def test_refresh_rereads_manifest_sync_disabled(monkeypatch, tmp_path):
    monkeypatch.delenv("IMAGE_SYNC_INTERVAL_SECONDS", raising=False)
    img_dir = tmp_path / "levels"
    manifest_path = img_dir / "manifest.json"
    _write_manifest(
        manifest_path,
        levels=[
            {"id": 0, "available": False, "images": []},
            {
                "id": 1,
                "available": True,
                "images": [{"file_id": "mid_1a", "name": "1.1.jpeg"}],
            },
        ],
    )
    _point_manifest_at(monkeypatch, manifest_path)
    monkeypatch.setattr(drive_service, "LEVELS_IMG_DIR", img_dir)

    guard = _NetGuard()
    monkeypatch.setattr(drive_service, "list_children", guard)

    drive_service._cache = drive_service.DiscoveryCache()
    with TestClient(main_module.app) as c:
        body = c.post("/api/refresh").json()
        assert body["ready"] is True
        assert body["sync"] == "disabled"
        assert 1 in body["available"]

        # Mutate the manifest on disk, refresh again -> re-read picks it up.
        _write_manifest(
            manifest_path,
            levels=[
                {"id": 0, "available": False, "images": []},
                {"id": 1, "available": True, "images": [{"file_id": "mid_1a", "name": "1.1.jpeg"}]},
                {"id": 2, "available": True, "images": [{"file_id": "mid_2a", "name": "2.1.jpeg"}]},
            ],
        )
        body2 = c.post("/api/refresh").json()
        assert 2 in body2["available"]

    assert guard.calls == 0, "refresh on manifest path must not list Drive"


# ---------------------------------------------------------------------------
# 8. Paced downloader retries 403 then 200, writes atomically
# ---------------------------------------------------------------------------
def test_download_images_paced_retries_then_writes(monkeypatch, tmp_path):
    """A mocked transport returns 403 once then 200; _download_one retries and
    download_images_paced writes the file. Sleep is patched to ~0 so the test is
    fast (no real 2-32s backoff)."""
    monkeypatch.setenv("GD_API_KEY", "TEST-DUMMY-KEY")

    state = {"hits": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["hits"] += 1
        if state["hits"] == 1:
            return httpx.Response(403, content=b"throttled")
        return httpx.Response(
            200, headers={"content-type": "image/jpeg"}, content=b"REALBYTES"
        )

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return real_async_client(transport=transport, **kwargs)

    monkeypatch.setattr(drive_service.httpx, "AsyncClient", client_factory)

    # Patch sleep to ~0 so backoff + pacing don't actually wait.
    async def fast_sleep(_seconds):
        return None

    monkeypatch.setattr(drive_service.asyncio, "sleep", fast_sleep)

    dest = tmp_path / "1" / "1.1.jpeg"
    downloaded, skipped, failures = asyncio.run(
        drive_service.download_images_paced([(dest, "fid_x")])
    )

    assert downloaded == 1
    assert skipped == 0
    assert failures == []
    assert dest.is_file()
    assert dest.read_bytes() == b"REALBYTES"
    assert state["hits"] == 2  # one 403 retry + one 200


def test_download_images_paced_skips_existing(monkeypatch, tmp_path):
    """An already-present non-empty dest is skipped (idempotent/resumable)."""
    monkeypatch.setenv("GD_API_KEY", "TEST-DUMMY-KEY")
    dest = tmp_path / "1" / "1.1.jpeg"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"ALREADY")

    async def boom(*a, **k):  # pragma: no cover
        raise AssertionError("must not fetch an already-baked file")

    monkeypatch.setattr(drive_service, "_download_one", boom)

    downloaded, skipped, failures = asyncio.run(
        drive_service.download_images_paced([(dest, "fid_x")])
    )
    assert (downloaded, skipped, failures) == (0, 1, [])
    assert dest.read_bytes() == b"ALREADY"
