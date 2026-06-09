"""Cloudinary-service contract tests (M13).

Unit + integration coverage for ``app/cloudinary_service.py``, the new image
source that replaced the Google-Drive byte proxy. All Admin-API access is mocked
via ``tests/conftest.py`` (``_list_all_resources`` patched), so these tests are
hermetic and never reach api.cloudinary.com.

Covers:
  1. discover() builds levels/availability/span from mocked Admin resources;
     missing pool populated; result cached (R2) and only rebuilt on force.
  2. Stem extraction: strips the random "_xxxxxx" suffix; preserves underscores
     in the body; leaves a non-suffixed id unchanged.
  3. CDN delivery URL shape (f_auto,q_auto + format) and file_id = public_id.
  4. get_level_photos: present -> own images; absent -> re-rolled missing image,
     fallback_audio None; no missing pool -> empty.
  5. run_sync_once single-flight + no-creds short-circuit; refresh = force.
  6. background_sync_loop is NOT started by the lifespan when env unset (gate).
  7. Graceful degrade: malformed/absent CLOUDINARY_URL or an API error keeps the
     prior (empty) cache and never raises.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app import cloudinary_service as cs
from app import main as main_module
from tests import conftest as fake


# ===========================================================================
# 1. discover() builds the cache from mocked Admin resources
# ===========================================================================
def test_discover_builds_levels_and_missing_pool(patched_cloudinary):
    cache = asyncio.run(cs.discover(force=True))
    assert cache.ready is True
    assert sorted(cache.folder_index) == [1, 2, 8]
    assert cache.levels == list(range(0, 9))  # span 0..max
    assert len(cache.missing_images) == 2
    # Level images grouped correctly.
    assert {i.file_id for i in cache.level_images[1]} == {fake.PID_1A, fake.PID_1B}
    assert {i.file_id for i in cache.level_images[2]} == {fake.PID_2A}
    assert {i.file_id for i in cache.level_images[8]} == {fake.PID_8A}


def test_discover_caches_result_until_force(patched_cloudinary):
    """R2: a second discover() returns the cache; force=True rebuilds it."""
    first = asyncio.run(cs.discover(force=True))
    # Mutate the resource list, then call WITHOUT force -> unchanged.
    patched_cloudinary.append(
        {"public_id": "10.1_eeeeee", "format": "jpg", "asset_folder": "all ages/10"}
    )
    again = asyncio.run(cs.discover(force=False))
    assert again is first  # same cached object
    assert sorted(again.folder_index) == [1, 2, 8]
    # force=True picks up the change.
    forced = asyncio.run(cs.discover(force=True))
    assert sorted(forced.folder_index) == [1, 2, 8, 10]


def test_discover_empty_when_no_all_ages_folders(monkeypatch):
    """Resources with no 'all ages/' folders -> empty levels/availability."""
    async def fake_list(cfg, client):
        return [
            {"public_id": "x_aaaaaa", "format": "jpg", "asset_folder": "misc/a"},
        ]

    monkeypatch.setattr(cs, "_list_all_resources", fake_list)
    cs._cache = cs.DiscoveryCache()
    cache = asyncio.run(cs.discover(force=True))
    assert cache.ready is True
    assert cache.folder_index == {}
    assert cache.levels == []
    assert cache.missing_images == []


# ===========================================================================
# 2. Stem extraction
# ===========================================================================
@pytest.mark.parametrize(
    "public_id, expected",
    [
        ("15.1_gpoksj", "15.1"),
        ("1_uuasv3", "1"),
        ("2.1_zzzzaa", "2.1"),
        ("1_r2_c4_xxxxxx", "1_r2_c4"),  # underscores in the body are preserved
        ("noSuffix", "noSuffix"),       # no random suffix -> unchanged
        ("short_ab", "short_ab"),       # 2-char tail is not a 6-char suffix
    ],
)
def test_filename_stem_extraction(public_id, expected):
    assert cs._filename_stem(public_id) == expected


# ===========================================================================
# 3. CDN delivery URL shape
# ===========================================================================
def test_delivery_url_shape():
    url = cs._delivery_url("mycloud", "7.2_qwerty", "jpg")
    assert url == (
        "https://res.cloudinary.com/mycloud/image/upload/"
        "f_auto,q_auto/7.2_qwerty.jpg"
    )


def test_delivery_url_defaults_format_to_jpg():
    url = cs._delivery_url("mycloud", "x_aaaaaa", "")
    assert url.endswith("/x_aaaaaa.jpg")


def test_imageref_file_id_is_public_id(patched_cloudinary):
    cache = asyncio.run(cs.discover(force=True))
    ref = cache.level_images[1][0]
    assert ref.file_id in {fake.PID_1A, fake.PID_1B}
    # filename_stem is the public_id minus the random suffix.
    assert ref.filename_stem == cs._filename_stem(ref.file_id)


# ===========================================================================
# 4. get_level_photos
# ===========================================================================
def test_get_level_photos_present(patched_cloudinary):
    asyncio.run(cs.discover(force=True))
    res = cs.get_level_photos(1)
    assert res.available is True
    assert res.fallback_audio is None
    assert {i.file_id for i in res.images} == {fake.PID_1A, fake.PID_1B}


def test_get_level_photos_absent_rerolls_missing(patched_cloudinary):
    asyncio.run(cs.discover(force=True))
    res = cs.get_level_photos(3)
    assert res.available is False
    assert res.fallback_audio is None
    assert len(res.images) == 1
    assert res.images[0].file_id in {fake.MISS_A, fake.MISS_B}


def test_get_level_photos_no_pool_returns_empty(monkeypatch):
    """An absent level with NO missing pool -> empty images, never raises."""
    async def fake_list(cfg, client):
        return [
            {"public_id": "1_aaaaaa", "format": "jpg", "asset_folder": "all ages/1"},
        ]

    monkeypatch.setattr(cs, "_list_all_resources", fake_list)
    cs._cache = cs.DiscoveryCache()
    asyncio.run(cs.discover(force=True))
    res = cs.get_level_photos(0)  # absent, no missing pool
    assert res.available is False
    assert res.images == []
    assert res.fallback_audio is None


# ===========================================================================
# 5. run_sync_once / refresh
# ===========================================================================
def test_run_sync_once_no_creds_short_circuits(monkeypatch):
    """No CLOUDINARY_URL -> run_sync_once returns no-creds without listing."""
    monkeypatch.delenv("CLOUDINARY_URL", raising=False)
    cs._cache = cs.DiscoveryCache()
    out = asyncio.run(cs.run_sync_once())
    assert out == {"status": "no-creds"}
    assert cs._cache.ready is False  # never listed


def test_run_sync_once_synced_reports_change(patched_cloudinary):
    cs._cache = cs.DiscoveryCache()
    out = asyncio.run(cs.run_sync_once())
    assert out["status"] == "synced"
    assert out["available_levels"] == 3
    assert out["changed"] is True  # 0 -> 3 available


def test_run_sync_once_single_flight_skips_when_locked(patched_cloudinary):
    """If the single-flight lock is held, a trigger is skipped (no overlap)."""
    async def scenario():
        await cs._sync_lock.acquire()
        try:
            return await cs.run_sync_once()
        finally:
            cs._sync_lock.release()

    out = asyncio.run(scenario())
    assert out == {"status": "skipped-locked"}


def test_refresh_is_force_discover(patched_cloudinary):
    cs._cache = cs.DiscoveryCache()
    cache = asyncio.run(cs.refresh())
    assert cache.ready is True
    assert sorted(cache.folder_index) == [1, 2, 8]


# ===========================================================================
# 6. background_sync_loop gate — NOT started by lifespan when env unset
# ===========================================================================
def test_background_loop_not_started_without_interval(monkeypatch):
    """The lifespan must NOT create the sync task when IMAGE_SYNC_INTERVAL is
    unset/0, even with creds present (hermetic guard)."""
    from fastapi.testclient import TestClient

    created = {"n": 0}
    real_loop = cs.background_sync_loop

    async def spy_loop(*a, **k):  # pragma: no cover - must never be scheduled
        created["n"] += 1
        return await real_loop(*a, **k)

    monkeypatch.setattr(cs, "background_sync_loop", spy_loop)
    monkeypatch.setenv("CLOUDINARY_URL", fake.DUMMY_CLOUDINARY_URL)
    monkeypatch.setenv("IMAGE_SYNC_INTERVAL_SECONDS", "")  # disabled

    async def fake_list(cfg, client):
        return []

    monkeypatch.setattr(cs, "_list_all_resources", fake_list)
    cs._cache = cs.DiscoveryCache()
    with TestClient(main_module.app):
        pass
    assert created["n"] == 0, "background sync loop must not start when disabled"


def test_image_sync_interval_parsing(monkeypatch):
    monkeypatch.setenv("IMAGE_SYNC_INTERVAL_SECONDS", "")
    assert main_module._image_sync_interval() == 0
    monkeypatch.setenv("IMAGE_SYNC_INTERVAL_SECONDS", "0")
    assert main_module._image_sync_interval() == 0
    monkeypatch.setenv("IMAGE_SYNC_INTERVAL_SECONDS", "-5")
    assert main_module._image_sync_interval() == 0
    monkeypatch.setenv("IMAGE_SYNC_INTERVAL_SECONDS", "abc")
    assert main_module._image_sync_interval() == 0
    monkeypatch.setenv("IMAGE_SYNC_INTERVAL_SECONDS", "1800")
    assert main_module._image_sync_interval() == 1800


# ===========================================================================
# 7. Graceful degrade — never raises
# ===========================================================================
def test_discover_no_creds_keeps_empty_cache(monkeypatch):
    monkeypatch.delenv("CLOUDINARY_URL", raising=False)
    cs._cache = cs.DiscoveryCache()
    cache = asyncio.run(cs.discover(force=True))
    assert cache.ready is False
    assert cache.levels == []


def test_discover_api_error_keeps_prior_cache(monkeypatch):
    """An Admin-API HTTP error degrades gracefully — never raises, keeps cache."""
    async def boom(cfg, client):
        request = httpx.Request("GET", "https://api.cloudinary.com/v1_1/x/resources/image")
        response = httpx.Response(401, request=request)
        raise httpx.HTTPStatusError("unauthorized", request=request, response=response)

    monkeypatch.setattr(cs, "_list_all_resources", boom)
    cs._cache = cs.DiscoveryCache()
    # Must not raise.
    cache = asyncio.run(cs.discover(force=True))
    assert cache.ready is False  # prior empty cache kept


def test_discover_network_error_keeps_prior_cache(monkeypatch):
    async def boom(cfg, client):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(cs, "_list_all_resources", boom)
    cs._cache = cs.DiscoveryCache()
    cache = asyncio.run(cs.discover(force=True))
    assert cache.ready is False
