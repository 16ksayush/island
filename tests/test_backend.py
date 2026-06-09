"""Backend test suite (M13 — Cloudinary) — pytest + FastAPI TestClient.

Cloudinary is fully mocked via ``tests/conftest.py`` (the Admin-API list is
patched), so the suite is hermetic and offline.

Covers the still-valid backend invariants, converted from the M12/Drive version
to the Cloudinary contract:
  1. Routes smoke (/, /level/{id}, /api/levels shape + availability)
  2. Dynamic discovery (present vs missing reflect the mocked resource set)
  3. Missing fallback R3 (absent level -> random CDN image from the missing pool)
  4. Empty/absent level R5 (no images -> missing fallback)
  5. Photo payload contract (file_id = public_id, url = keyless CDN link)
  6. Theme cookie D3 (no cookie -> horror; theme=sea -> sea in context)
  7. Refresh R2 (changed Admin listing -> levels change after POST /api/refresh)
  8. Error mapping (unknown id -> 404) + secret isolation (api_secret never leaks)
  9. Graceful degrade (no CLOUDINARY_URL -> empty gallery, app still serves)

RETIRED here (M13 — no longer part of the contract; routes/code REMOVED):
  * media-proxy scoping (R1) + content-type echo (R6): the
    ``/api/levels/{id}/media/{file_id}`` endpoint and ``resolve_media`` are gone
    (images stream from res.cloudinary.com); see test_no_media_proxy_route below.
  * upstream-failure -> 502 mapping for /photos and /media: there is no
    per-request upstream fetch anymore (discovery is the only API call).
  * GD_API_KEY / DriveConfigError config tests: replaced by CLOUDINARY_URL
    parsing + the graceful no-creds path.
"""

from __future__ import annotations

import os

import pytest

from app import cloudinary_service
from app import main as main_module
from tests import conftest as fake


# ===========================================================================
# 1. Routes smoke
# ===========================================================================
def test_index_route_renders_200(client):
    resp = client.get("/")
    assert resp.status_code == 200, resp.text


def test_level_page_route_renders_200(client):
    # Present level and absent level both render the SSR page.
    assert client.get("/level/1").status_code == 200
    assert client.get("/level/3").status_code == 200


def test_api_levels_shape_and_flags(client):
    resp = client.get("/api/levels")
    assert resp.status_code == 200
    body = resp.json()
    assert "levels" in body and isinstance(body["levels"], list)
    by_id = {lvl["id"]: lvl["available"] for lvl in body["levels"]}
    # Each element is {id, available}.
    for lvl in body["levels"]:
        assert set(lvl.keys()) == {"id", "available"}
    # Present folders 1, 2, 8 -> available True.
    assert by_id[1] is True
    assert by_id[2] is True
    assert by_id[8] is True
    # Absent numbered folders within the span are flagged unavailable.
    assert by_id[0] is False
    assert by_id[3] is False


# ===========================================================================
# 2. Dynamic discovery
# ===========================================================================
def test_dynamic_span_zero_to_max(client):
    """Span is 0..max(present); here present max is 8 -> ids 0..8."""
    body = client.get("/api/levels").json()
    ids = [lvl["id"] for lvl in body["levels"]]
    assert ids == list(range(0, 9)), ids


def test_dynamic_available_set_matches_resources(client):
    body = client.get("/api/levels").json()
    available = sorted(lvl["id"] for lvl in body["levels"] if lvl["available"])
    # Folders present in the fake resource set: 1, 2, 8.
    assert available == [1, 2, 8], available


def test_missing_folder_not_treated_as_level(client):
    """The 'missing' asset_folder must not appear as a numbered level."""
    cache = cloudinary_service.get_cache()
    assert cache.missing_images, "missing pool should be populated"
    # All folder_index keys are integers (numeric folders only).
    assert all(isinstance(k, int) for k in cache.folder_index)
    assert sorted(cache.folder_index) == [1, 2, 8]


def test_noise_resources_ignored(client):
    """Resources not under 'all ages/' (root upload, misc/stuff) are ignored."""
    cache = cloudinary_service.get_cache()
    all_pids = {
        img.file_id
        for refs in cache.level_images.values()
        for img in refs
    } | {img.file_id for img in cache.missing_images}
    assert "root_upload_xxxxxx" not in all_pids
    assert "other_yyyyyy" not in all_pids


# ===========================================================================
# 3. Missing fallback (R3) — CDN image from the missing pool, null audio
# ===========================================================================
def test_missing_level_photos_returns_cdn_image(client):
    resp = client.get("/api/levels/3/photos")  # absent numbered folder
    assert resp.status_code == 200
    body = resp.json()
    assert body["level"] == 3
    assert body["available"] is False
    assert len(body["images"]) == 1
    # Audio for a missing level is NOT served by the backend (local per-theme).
    assert body["fallback_audio"] is None
    img = body["images"][0]
    # Image is drawn from the mocked missing pool.
    assert img["file_id"] in {fake.MISS_A, fake.MISS_B}
    # URL is the keyless CDN link, never a server proxy URL.
    assert img["url"].startswith(
        f"https://res.cloudinary.com/{fake.DUMMY_CLOUD}/image/upload/f_auto,q_auto/"
    )
    assert "/media/" not in img["url"]


def test_missing_fallback_uses_random_selection_and_may_vary(client):
    """R3: the missing-level image is re-rolled each call — always a valid
    member of the missing pool, and the selection MAY vary across calls."""
    pool = {fake.MISS_A, fake.MISS_B}
    seen = set()
    for _ in range(40):
        body = client.get("/api/levels/4/photos").json()
        pid = body["images"][0]["file_id"]
        assert pid in pool, pid
        assert body["fallback_audio"] is None
        seen.add(pid)
    # Over 40 re-rolls across a 2-element pool, both members should appear.
    assert seen == pool, seen


def test_missing_fallback_path_calls_random_choice(client, monkeypatch):
    """Directly assert the code path invokes random.choice (R3)."""
    calls = {"n": 0}
    real_choice = cloudinary_service.random.choice

    def spy(seq):
        calls["n"] += 1
        return real_choice(seq)

    monkeypatch.setattr(cloudinary_service.random, "choice", spy)
    client.get("/api/levels/5/photos")
    assert calls["n"] == 1


# ===========================================================================
# 4. Absent level (R5) within span -> missing fallback
# ===========================================================================
def test_absent_level_falls_through_to_missing(client):
    resp = client.get("/api/levels/6/photos")
    assert resp.status_code == 200
    body = resp.json()
    assert body["level"] == 6
    assert body["available"] is False
    assert len(body["images"]) == 1
    assert body["images"][0]["file_id"] in {fake.MISS_A, fake.MISS_B}
    assert body["fallback_audio"] is None


def test_present_nonempty_level_returns_its_own_images(client):
    resp = client.get("/api/levels/1/photos")
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is True
    assert body["fallback_audio"] is None
    file_ids = {img["file_id"] for img in body["images"]}
    assert file_ids == {fake.PID_1A, fake.PID_1B}
    # Each url is the keyless CDN link for its public_id + format.
    by_id = {img["file_id"]: img for img in body["images"]}
    assert by_id[fake.PID_1A]["url"] == fake._cdn_url(fake.PID_1A, "jpg")
    assert by_id[fake.PID_1B]["url"] == fake._cdn_url(fake.PID_1B, "jpg")


# ===========================================================================
# 5. Photo payload contract — file_id = public_id; CDN url; format honored
# ===========================================================================
def test_photo_url_uses_resource_format(client):
    """Level 2's image is a png; the CDN url must carry the .png extension."""
    body = client.get("/api/levels/2/photos").json()
    img = body["images"][0]
    assert img["file_id"] == fake.PID_2A
    assert img["url"] == fake._cdn_url(fake.PID_2A, "png")
    assert img["url"].endswith(".png")


def test_no_media_proxy_route(client):
    """RETIRED endpoint: /api/levels/{id}/media/{file_id} must NOT exist (M13).

    The Drive byte proxy is gone; images come straight from the CDN. A request
    to the old proxy path must not be served (404 / route not registered).
    """
    resp = client.get(f"/api/levels/1/media/{fake.PID_1A}")
    assert resp.status_code == 404
    # And the route is genuinely absent from the app's routing table.
    paths = {getattr(r, "path", "") for r in main_module.app.routes}
    assert "/api/levels/{level_id}/media/{file_id}" not in paths
    assert not any("/media/" in p for p in paths)


# ===========================================================================
# 6. Theme cookie (D3)
# ===========================================================================
def _spy_theme(monkeypatch):
    captured = {}
    real = main_module.templates.TemplateResponse

    def spy(request, name, context, *a, **k):
        captured["theme"] = context.get("theme")
        return real(request, name, context, *a, **k)

    monkeypatch.setattr(main_module.templates, "TemplateResponse", spy)
    return captured


def test_theme_default_horror_no_cookie(client, monkeypatch):
    captured = _spy_theme(monkeypatch)
    assert client.get("/").status_code == 200
    assert captured["theme"] == "horror"


def test_theme_sea_cookie_passed_to_context(client, monkeypatch):
    captured = _spy_theme(monkeypatch)
    client.cookies.set("theme", "sea")
    assert client.get("/").status_code == 200
    assert captured["theme"] == "sea"


def test_theme_invalid_cookie_falls_back_to_horror(client, monkeypatch):
    captured = _spy_theme(monkeypatch)
    client.cookies.set("theme", "purple-nonsense")
    client.get("/level/1")
    assert captured["theme"] == "horror"


def test_theme_helper_unit():
    """read_theme is the SSR cookie reader (D1/D3)."""
    from starlette.requests import Request

    def make(cookie_header):
        headers = [(b"cookie", cookie_header.encode())] if cookie_header else []
        return Request({"type": "http", "headers": headers})

    assert main_module.read_theme(make("")) == "horror"
    assert main_module.read_theme(make("theme=sea")) == "sea"
    assert main_module.read_theme(make("theme=horror")) == "horror"
    assert main_module.read_theme(make("theme=bogus")) == "horror"


# ===========================================================================
# 7. Refresh (R2) — re-list Cloudinary reflects a changed resource set
# ===========================================================================
def test_refresh_rebuilds_cache_on_changed_listing(client, patched_cloudinary):
    before = client.get("/api/levels").json()
    before_ids = sorted(l["id"] for l in before["levels"] if l["available"])
    assert before_ids == [1, 2, 8]

    # Mutate the fake resource list: add level 12, remove level 2.
    patched_cloudinary[:] = [
        {"public_id": fake.PID_1A, "format": "jpg", "asset_folder": "all ages/1"},
        {"public_id": fake.PID_8A, "format": "jpg", "asset_folder": "all ages/8"},
        {"public_id": "12.1_aabbcc", "format": "jpg", "asset_folder": "all ages/12"},
        {"public_id": fake.MISS_A, "format": "jpg", "asset_folder": "all ages/missing"},
    ]

    refresh = client.post("/api/refresh")
    assert refresh.status_code == 200
    rbody = refresh.json()
    assert rbody["ready"] is True
    assert rbody["available"] == [1, 8, 12]
    assert rbody["missing_pool"] == 1

    after = client.get("/api/levels").json()
    after_ids = [l["id"] for l in after["levels"]]
    after_available = sorted(l["id"] for l in after["levels"] if l["available"])
    # New span 0..12; available set changed (2 gone, 12 added).
    assert after_ids == list(range(0, 13))
    assert after_available == [1, 8, 12]


def test_refresh_without_refresh_keeps_cache(client, patched_cloudinary):
    """Without POST /api/refresh, a mutated resource set must NOT change levels."""
    patched_cloudinary.append(
        {"public_id": "15.1_dddddd", "format": "jpg", "asset_folder": "all ages/15"}
    )
    body = client.get("/api/levels").json()
    ids = [l["id"] for l in body["levels"]]
    assert ids == list(range(0, 9))  # unchanged — cache held (R2)


# ===========================================================================
# 8. Error mapping + secret isolation
# ===========================================================================
def test_unknown_level_id_returns_404(client):
    # Level 99 is outside the discovered span (0..8).
    resp = client.get("/api/levels/99/photos")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Unknown level."


def test_api_secret_never_appears_in_any_response_body(client):
    """Security: the Cloudinary api_secret must never leak into a client response."""
    bodies = [
        client.get("/api/levels").text,
        client.get("/api/levels/1/photos").text,
        client.get("/api/levels/3/photos").text,  # missing fallback
        client.get("/").text,
        client.get("/level/1").text,
        client.post("/api/refresh").text,
    ]
    for b in bodies:
        assert fake.DUMMY_SECRET not in b, "api_secret leaked into a response"
        assert "CLOUDINARY_URL" not in b
        assert "api.cloudinary.com" not in b
        # The keyless delivery host is fine; the admin host must never appear.


def test_photos_payload_carries_only_public_id_and_cdn_url(client):
    """The /photos payload exposes only the public_id + keyless CDN url — no
    api_key, api_secret, or admin host."""
    text = client.get("/api/levels/1/photos").text
    assert fake.DUMMY_SECRET not in text
    assert fake.DUMMY_KEY not in text
    assert "api.cloudinary.com" not in text
    # The keyless CDN host IS expected (intended public exposure).
    assert "res.cloudinary.com" in text


# ===========================================================================
# 9. Graceful degrade + hermeticity guards
# ===========================================================================
def test_app_imports_and_serves_without_real_cloudinary(client):
    """The app boots and serves even though no real Cloudinary is reachable."""
    assert main_module.app.title.startswith("Archive 19")
    assert client.get("/api/levels").status_code == 200


def test_no_creds_empty_gallery_pages_still_200(monkeypatch):
    """With CLOUDINARY_URL unset, discovery degrades to an empty gallery; the
    app still boots and every page returns 200 (never raises)."""
    from fastapi.testclient import TestClient

    monkeypatch.delenv("CLOUDINARY_URL", raising=False)
    # Also blank IMAGE_SYNC so the loop never starts (belt & braces).
    monkeypatch.setenv("IMAGE_SYNC_INTERVAL_SECONDS", "")
    cloudinary_service._cache = cloudinary_service.DiscoveryCache()

    with TestClient(main_module.app) as c:
        levels = c.get("/api/levels")
        assert levels.status_code == 200
        assert levels.json() == {"levels": []}
        assert c.get("/").status_code == 200
        assert c.get("/level/0").status_code == 200
        # An out-of-span level on an empty gallery is a 404 (no span at all).
        assert c.get("/api/levels/3/photos").status_code == 404


def test_parse_cloudinary_url_absent_returns_none(monkeypatch):
    monkeypatch.delenv("CLOUDINARY_URL", raising=False)
    assert cloudinary_service._parse_cloudinary_url() is None


def test_parse_cloudinary_url_malformed_returns_none(monkeypatch):
    monkeypatch.setenv("CLOUDINARY_URL", "not-a-cloudinary-url")
    assert cloudinary_service._parse_cloudinary_url() is None


def test_parse_cloudinary_url_valid(monkeypatch):
    monkeypatch.setenv("CLOUDINARY_URL", fake.DUMMY_CLOUDINARY_URL)
    cfg = cloudinary_service._parse_cloudinary_url()
    assert cfg is not None
    assert cfg.api_key == fake.DUMMY_KEY
    assert cfg.api_secret == fake.DUMMY_SECRET
    assert cfg.cloud_name == fake.DUMMY_CLOUD
