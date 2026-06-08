"""Caching / perf test suite (post perf-refactor).

Verifies the new caching internals introduced by the backend perf change while
keeping the suite hermetic (all Drive access mocked via tests/conftest.py):

  1. Scope cache still enforces R1 per-level isolation under caching
     (cross-level file id -> 404; unknown id -> 404).
  2. missing/ assets are cross-level serveable via ANY level URL (expected).
  3. Byte cache: two requests for the same file id -> ONE upstream Drive fetch;
     identical bytes + identical Content-Type on both (R6).
  4. Cache-Control + ETag headers on the media response.
  5. R3 still re-rolls a missing level's pick even though the missing/ LIST is
     cached (only the list is cached, not the choice).
  6. POST /api/refresh clears caches: scope + levels update and stale bytes are
     not served from the old listing.
  7. Discovery does NOT re-list Drive per media request: after warm discovery,
     N in-scope media requests trigger 0 additional list_children calls.

All counters/instrumentation wrap the SAME mocks conftest installs, so nothing
here reaches the network.
"""

from __future__ import annotations

import httpx
import pytest

from app import drive_service
from app import main as main_module
from tests import conftest as fake


# ---------------------------------------------------------------------------
# Local helpers: instrument the conftest mocks with call counters.
# ---------------------------------------------------------------------------
@pytest.fixture
def counting_drive(monkeypatch, drive_tree):
    """Like ``patched_drive`` but counts ``list_children`` invocations.

    Returns a holder with ``.tree`` (mutable fake tree), ``.calls`` (total
    list_children calls) and ``.calls_by_folder`` (per-folder counts).
    """
    holder = {"tree": drive_tree, "calls": 0, "by_folder": {}}

    async def fake_list_children(folder_id, client):
        holder["calls"] += 1
        holder["by_folder"][folder_id] = holder["by_folder"].get(folder_id, 0) + 1
        if folder_id not in drive_tree:
            return []
        return list(drive_tree[folder_id])

    monkeypatch.setattr(drive_service, "list_children", fake_list_children)
    return holder


@pytest.fixture
def counting_media(monkeypatch):
    """Like ``patched_media`` but counts upstream files.get?alt=media fetches.

    Returns a holder with ``.fetches`` (total upstream media GETs) and
    ``.by_file`` (per file_id fetch counts) plus ``.last_request``.
    """
    holder = {"fetches": 0, "by_file": {}, "last_request": None}

    def handler(request: httpx.Request) -> httpx.Response:
        holder["last_request"] = request
        file_id = request.url.path.rsplit("/", 1)[-1]
        holder["fetches"] += 1
        holder["by_file"][file_id] = holder["by_file"].get(file_id, 0) + 1
        if file_id in fake.MEDIA_BYTES:
            content_type, body = fake.MEDIA_BYTES[file_id]
            return httpx.Response(
                200, headers={"content-type": content_type}, content=body
            )
        return httpx.Response(404, content=b"not found")

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return real_async_client(transport=transport, **kwargs)

    monkeypatch.setattr(drive_service.httpx, "AsyncClient", client_factory)
    return holder


@pytest.fixture
def counting_client(counting_drive):
    """TestClient whose discovery/lifespan runs against the counting mock."""
    from fastapi.testclient import TestClient

    with TestClient(main_module.app) as c:
        yield c


# ===========================================================================
# 1. Scope cache still enforces R1 per-level isolation (under caching)
# ===========================================================================
def test_scope_cache_blocks_cross_level_file_id(client, patched_media):
    """A real image id from level 2 must 404 when fetched via level 1's URL."""
    # Sanity: it is valid for its OWN level.
    ok = client.get(f"/api/levels/2/media/{fake.IMG_2A}")
    assert ok.status_code == 200, ok.text
    # ...but not through a different level (cross-level isolation, R1).
    leak = client.get(f"/api/levels/1/media/{fake.IMG_2A}")
    assert leak.status_code == 404, leak.text
    assert leak.json()["detail"] == "Media not found."


def test_scope_cache_unknown_file_id_404(client, patched_media):
    """An id in NO folder is never in scope -> 404."""
    resp = client.get("/api/levels/1/media/never-existed-id")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Media not found."


# ===========================================================================
# 2. missing/ assets are cross-level serveable (expected, per security note)
# ===========================================================================
def test_missing_asset_serveable_via_any_level(client, patched_media):
    """A missing/ file id resolves through ANY level's media URL."""
    # Through an absent level (3) and a present level (1) — both must serve it.
    for level_id in (0, 1, 3, 8):
        resp = client.get(f"/api/levels/{level_id}/media/{fake.MISS_IMG_A}")
        assert resp.status_code == 200, (level_id, resp.text)
        assert resp.content == fake.MEDIA_BYTES[fake.MISS_IMG_A][1]
    # The audio half of the missing pool is equally cross-level serveable.
    aud = client.get(f"/api/levels/5/media/{fake.MISS_AUD_A}")
    assert aud.status_code == 200
    assert aud.content == fake.MEDIA_BYTES[fake.MISS_AUD_A][1]


# ===========================================================================
# 3. Byte cache: same file id -> ONE upstream fetch; identical body + CT (R6)
# ===========================================================================
def test_byte_cache_single_upstream_fetch_for_repeat(client, counting_media):
    """Two GETs for the same file id cause exactly one upstream Drive fetch."""
    r1 = client.get(f"/api/levels/1/media/{fake.IMG_1A}")
    r2 = client.get(f"/api/levels/1/media/{fake.IMG_1A}")
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Only ONE upstream files.get?alt=media for this id — second served from cache.
    assert counting_media["by_file"].get(fake.IMG_1A) == 1, counting_media["by_file"]
    # Identical bytes + identical content type (R6) across both responses.
    assert r1.content == r2.content == fake.MEDIA_BYTES[fake.IMG_1A][1]
    assert (
        r1.headers["content-type"]
        == r2.headers["content-type"]
        == fake.MEDIA_BYTES[fake.IMG_1A][0]
    )


def test_byte_cache_hit_even_across_different_level_urls_for_missing(
    client, counting_media
):
    """A missing/ id fetched via two different level URLs still hits one fetch.

    The byte cache is keyed by file_id (not by level), so the second request —
    even through a different level's URL — is served from cache.
    """
    a = client.get(f"/api/levels/3/media/{fake.MISS_IMG_B}")
    b = client.get(f"/api/levels/7/media/{fake.MISS_IMG_B}")
    assert a.status_code == b.status_code == 200
    assert counting_media["by_file"].get(fake.MISS_IMG_B) == 1, counting_media["by_file"]
    assert a.content == b.content


# ===========================================================================
# 4. Cache-Control + ETag headers
# ===========================================================================
def test_media_response_has_cache_headers(client, patched_media):
    resp = client.get(f"/api/levels/1/media/{fake.IMG_1A}")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "public, max-age=86400, immutable"
    assert resp.headers["etag"] == f'"{fake.IMG_1A}"'


# ===========================================================================
# 5. R3 still re-rolls for a missing level despite the missing/ LIST cache
# ===========================================================================
def test_missing_list_cached_but_choice_rerolled(counting_client, counting_drive):
    """Only the missing/ LIST is cached; the random pick still varies (R3)."""
    client = counting_client
    seen_imgs, seen_auds = set(), set()
    for _ in range(40):
        body = client.get("/api/levels/4/photos").json()
        seen_imgs.add(body["images"][0]["file_id"])
        seen_auds.add(body["fallback_audio"]["file_id"])
    # Both members of each 2-element pool appear -> the choice is re-rolled.
    assert seen_imgs == {fake.MISS_IMG_A, fake.MISS_IMG_B}, seen_imgs
    assert seen_auds == {fake.MISS_AUD_A, fake.MISS_AUD_B}, seen_auds
    # ...yet the missing/ folder was listed only ONCE across all 40 calls
    # (prefetched at discovery; never re-listed), proving the LIST is cached.
    assert counting_drive["by_folder"].get(fake.MISSING_ID, 0) <= 1, (
        counting_drive["by_folder"]
    )


# ===========================================================================
# 6. POST /api/refresh clears caches (scope + bytes)
# ===========================================================================
def test_refresh_clears_byte_and_scope_cache(counting_client, counting_drive, counting_media):
    """After refresh with a changed listing, stale bytes aren't served and the
    scope list is rebuilt (a removed file id 404s; a new id serves fresh)."""
    client = counting_client
    # Warm the byte cache for an image in folder 1.
    first = client.get(f"/api/levels/1/media/{fake.IMG_1A}")
    assert first.status_code == 200
    assert counting_media["by_file"].get(fake.IMG_1A) == 1

    # Cached hit: no second upstream fetch yet.
    client.get(f"/api/levels/1/media/{fake.IMG_1A}")
    assert counting_media["by_file"].get(fake.IMG_1A) == 1

    # Mutate Drive: folder 1 now contains a DIFFERENT image (IMG_1A removed).
    counting_drive["tree"][fake.FOLDER_1] = [
        {"id": fake.IMG_1B, "name": "1.2.jpeg", "mimeType": "image/jpeg"},
    ]
    refreshed = client.post("/api/refresh")
    assert refreshed.status_code == 200

    # Scope rebuilt: IMG_1A is no longer in folder 1's scope -> 404 (not stale bytes).
    stale = client.get(f"/api/levels/1/media/{fake.IMG_1A}")
    assert stale.status_code == 404, stale.text

    # The surviving image still serves, and (byte cache cleared) is re-fetched.
    keep = client.get(f"/api/levels/1/media/{fake.IMG_1B}")
    assert keep.status_code == 200
    assert counting_media["by_file"].get(fake.IMG_1B) == 1


def test_refresh_clears_byte_cache_even_for_same_in_scope_id(
    client, counting_media
):
    """A file id still in scope after refresh is re-fetched (byte cache cleared)."""
    client.get(f"/api/levels/1/media/{fake.IMG_1A}")
    assert counting_media["by_file"].get(fake.IMG_1A) == 1
    client.post("/api/refresh")  # clears the byte cache
    client.get(f"/api/levels/1/media/{fake.IMG_1A}")
    # Re-fetched upstream because the byte cache was cleared by refresh.
    assert counting_media["by_file"].get(fake.IMG_1A) == 2, counting_media["by_file"]


# ===========================================================================
# 7. Discovery does NOT re-list Drive per media request
# ===========================================================================
def test_no_relist_per_media_request(counting_client, counting_drive, counting_media):
    """After warm discovery, N in-scope media GETs -> 0 extra list_children."""
    client = counting_client
    # Discovery already ran via lifespan; capture the warm baseline.
    baseline_calls = counting_drive["calls"]
    assert baseline_calls > 0  # discovery did list folders

    file_ids = [fake.IMG_1A, fake.IMG_1B, fake.MISS_IMG_A, fake.MISS_AUD_A]
    # Map each id to a valid level URL.
    urls = [
        f"/api/levels/1/media/{fake.IMG_1A}",
        f"/api/levels/1/media/{fake.IMG_1B}",
        f"/api/levels/3/media/{fake.MISS_IMG_A}",
        f"/api/levels/3/media/{fake.MISS_AUD_A}",
    ]
    for _ in range(3):
        for url in urls:
            assert client.get(url).status_code == 200, url

    # The whole point of the perf fix: scope checks read the cached lists, so no
    # additional Drive listing happened for any of those media requests.
    assert counting_drive["calls"] == baseline_calls, (
        counting_drive["calls"],
        baseline_calls,
        counting_drive["by_folder"],
    )
    # 4 distinct ids fetched once each (then cached); 3 rounds add no fetches.
    assert sum(counting_media["by_file"].values()) == len(file_ids), (
        counting_media["by_file"]
    )


def test_discovery_prefetches_level_scope_lists(counting_client, counting_drive):
    """Discovery prefetches per-level scope lists (each numbered folder once)."""
    cache = drive_service.get_cache()
    # Each present numbered folder was listed at discovery and cached.
    assert set(cache.level_images.keys()) == set(cache.folder_index.keys())
    # The missing/ pool lists were prefetched too (R3 pool).
    assert cache.missing_images is not None
    assert cache.missing_audio is not None


# ===========================================================================
# Byte-cache unit tests (LRU bounds) — direct against MediaByteCache
# ===========================================================================
def test_byte_cache_evicts_on_entry_count():
    c = drive_service.MediaByteCache(max_entries=2, max_bytes=10 ** 9)
    c.put("a", "image/jpeg", b"AAA")
    c.put("b", "image/jpeg", b"BBB")
    c.put("c", "image/jpeg", b"CCC")  # evicts LRU "a"
    assert c.get("a") is None
    assert c.get("b") == ("image/jpeg", b"BBB")
    assert c.get("c") == ("image/jpeg", b"CCC")


def test_byte_cache_evicts_on_total_bytes():
    c = drive_service.MediaByteCache(max_entries=100, max_bytes=8)
    c.put("a", "image/jpeg", b"AAAA")  # 4 bytes
    c.put("b", "image/jpeg", b"BBBB")  # 8 total — ok
    c.put("c", "image/jpeg", b"CCCC")  # 12 -> evict "a" down to 8
    assert c.get("a") is None
    assert c.get("b") == ("image/jpeg", b"BBBB")
    assert c.get("c") == ("image/jpeg", b"CCCC")


def test_byte_cache_skips_oversized_item():
    c = drive_service.MediaByteCache(max_entries=10, max_bytes=4)
    c.put("big", "image/jpeg", b"AAAAAAAA")  # 8 bytes > 4 budget -> not cached
    assert c.get("big") is None


def test_byte_cache_clear_empties_store():
    c = drive_service.MediaByteCache(max_entries=10, max_bytes=10 ** 9)
    c.put("a", "image/jpeg", b"AAAA")
    c.clear()
    assert c.get("a") is None
