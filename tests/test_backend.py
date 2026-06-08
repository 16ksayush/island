"""Backend test suite (T6b) — pytest + FastAPI TestClient, Drive fully mocked.

Covers the 9 required areas (see docs/PLAN.md T6b, docs/ARCHITECTURE.md §4/§5):
  1. Routes smoke (/, /level/{id}, /api/levels shape + availability)
  2. Dynamic discovery (present vs missing reflect the fake tree)
  3. Missing fallback R3 (absent level -> proxied image+audio from missing/)
  4. Empty-but-present folder R5 (zero images -> missing fallback)
  5. Media proxy scoping R1 (in-scope streams; unknown id -> 404)
  6. Content-Type echo R6 (image/png AND audio/mpeg mirrored, never hardcoded)
  7. Theme cookie D3 (no cookie -> horror; theme=sea -> sea in context)
  8. Refresh R2 (changed parent listing -> levels change after POST /api/refresh)
  9. Error mapping (unknown id -> 404; upstream failure -> 502; no secret leak)
"""

from __future__ import annotations

import importlib

import pytest

from app import drive_service
from app import main as main_module
from tests import conftest as fake

DUMMY_KEY = "TEST-DUMMY-KEY-do-not-use"


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
    # Each element is {id, available}
    for lvl in body["levels"]:
        assert set(lvl.keys()) == {"id", "available"}
    # Present folders 1,2 -> available True; 8 present-but-empty is still a
    # discovered folder so its availability flag is True at the /levels layer
    # (availability == "numbered folder exists", emptiness handled in /photos).
    assert by_id[1] is True
    assert by_id[2] is True
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


def test_dynamic_available_set_matches_tree(client):
    body = client.get("/api/levels").json()
    available = sorted(lvl["id"] for lvl in body["levels"] if lvl["available"])
    # Folders present in the fake tree: 1, 2, 8.
    assert available == [1, 2, 8], available


def test_missing_folder_not_treated_as_level(client):
    """The 'missing' child must not appear as a numbered level."""
    cache = drive_service.get_cache()
    assert cache.missing_folder_id == fake.MISSING_ID
    # 'missing' name is non-digit -> never in folder_index.
    assert all(isinstance(k, int) for k in cache.folder_index)


# ===========================================================================
# 3. Missing fallback (R3)
# ===========================================================================
def test_missing_level_photos_returns_proxied_image_and_audio(client):
    resp = client.get("/api/levels/3/photos")  # absent numbered folder
    assert resp.status_code == 200
    body = resp.json()
    assert body["level"] == 3
    assert body["available"] is False
    assert len(body["images"]) == 1
    assert body["fallback_audio"] is not None
    img = body["images"][0]
    aud = body["fallback_audio"]
    # Image is drawn from the mocked missing/ image set.
    assert img["file_id"] in {fake.MISS_IMG_A, fake.MISS_IMG_B}
    # Audio is drawn from the mocked missing/ audio set.
    assert aud["file_id"] in {fake.MISS_AUD_A, fake.MISS_AUD_B}
    # URLs are proxied through our media endpoint, never bare Drive URLs.
    assert img["url"] == f"/api/levels/3/media/{img['file_id']}"
    assert aud["url"] == f"/api/levels/3/media/{aud['file_id']}"
    assert "googleapis" not in resp.text
    assert "drive.google" not in resp.text


def test_missing_fallback_uses_random_selection_and_may_vary(client, monkeypatch):
    """R3: re-rolled each call. Always a valid member of the missing set; the
    selection MAY vary. We prove (a) validity over many calls and (b) the code
    path uses random.choice by forcing it to observe variation deterministically.
    """
    img_set = {fake.MISS_IMG_A, fake.MISS_IMG_B}
    aud_set = {fake.MISS_AUD_A, fake.MISS_AUD_B}
    seen_imgs, seen_auds = set(), set()
    for _ in range(40):
        body = client.get("/api/levels/4/photos").json()
        i = body["images"][0]["file_id"]
        a = body["fallback_audio"]["file_id"]
        assert i in img_set, i
        assert a in aud_set, a
        seen_imgs.add(i)
        seen_auds.add(a)
    # Over 40 re-rolls across a 2-element set, both members should appear
    # (probability of not seeing variation is 2 * 2**-40 — effectively zero).
    assert seen_imgs == img_set, seen_imgs
    assert seen_auds == aud_set, seen_auds


def test_missing_fallback_path_calls_random_choice(client, monkeypatch):
    """Directly assert the code path invokes random.choice (R3)."""
    calls = {"n": 0}
    real_choice = drive_service.random.choice

    def spy(seq):
        calls["n"] += 1
        return real_choice(seq)

    monkeypatch.setattr(drive_service.random, "choice", spy)
    client.get("/api/levels/5/photos")
    # One choice for the image + one for the audio.
    assert calls["n"] == 2


# ===========================================================================
# 4. Empty-but-present folder (R5)
# ===========================================================================
def test_empty_present_folder_falls_through_to_missing(client):
    """Folder 8 exists but holds zero images -> available:false + fallback."""
    resp = client.get("/api/levels/8/photos")
    assert resp.status_code == 200
    body = resp.json()
    assert body["level"] == 8
    assert body["available"] is False  # R5: treated as not-yet-stocked
    assert len(body["images"]) == 1
    assert body["images"][0]["file_id"] in {fake.MISS_IMG_A, fake.MISS_IMG_B}
    assert body["fallback_audio"]["file_id"] in {fake.MISS_AUD_A, fake.MISS_AUD_B}


def test_present_nonempty_folder_returns_its_own_images(client):
    resp = client.get("/api/levels/1/photos")
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is True
    assert body["fallback_audio"] is None
    file_ids = {img["file_id"] for img in body["images"]}
    assert file_ids == {fake.IMG_1A, fake.IMG_1B}
    for img in body["images"]:
        assert img["url"] == f"/api/levels/1/media/{img['file_id']}"


# ===========================================================================
# 5. Media proxy scoping (R1)
# ===========================================================================
def test_media_proxy_in_scope_streams_bytes(client, patched_media):
    resp = client.get(f"/api/levels/1/media/{fake.IMG_1A}")
    assert resp.status_code == 200
    assert resp.content == fake.MEDIA_BYTES[fake.IMG_1A][1]


def test_media_proxy_unknown_file_id_404(client, patched_media):
    """R1: a file id not in the level folder OR missing/ -> 404, no open proxy."""
    resp = client.get("/api/levels/1/media/totally-unknown-id")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Media not found."


def test_media_proxy_rejects_other_levels_file(client, patched_media):
    """A real Drive id that belongs to a DIFFERENT level is out of scope -> 404."""
    # IMG_2A belongs to folder 2, not folder 1.
    resp = client.get(f"/api/levels/1/media/{fake.IMG_2A}")
    assert resp.status_code == 404


def test_media_proxy_missing_asset_in_scope_for_any_level(client, patched_media):
    """Assets in missing/ are in scope for every level id (fallback path)."""
    resp = client.get(f"/api/levels/3/media/{fake.MISS_IMG_A}")
    assert resp.status_code == 200
    assert resp.content == fake.MEDIA_BYTES[fake.MISS_IMG_A][1]


# ===========================================================================
# 6. Content-Type echo (R6)
# ===========================================================================
def test_content_type_echo_image_png(client, patched_media):
    resp = client.get(f"/api/levels/3/media/{fake.MISS_IMG_A}")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"


def test_content_type_echo_audio_mpeg(client, patched_media):
    resp = client.get(f"/api/levels/3/media/{fake.MISS_AUD_A}")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mpeg"


def test_content_type_not_hardcoded_image(client, patched_media):
    """Same endpoint yields different content-types depending on upstream."""
    img = client.get(f"/api/levels/1/media/{fake.IMG_1A}")
    aud = client.get(f"/api/levels/3/media/{fake.MISS_AUD_A}")
    assert img.headers["content-type"] == "image/jpeg"
    assert aud.headers["content-type"] == "audio/mpeg"
    assert img.headers["content-type"] != aud.headers["content-type"]


# ===========================================================================
# 7. Theme cookie (D3)
# ===========================================================================
def test_theme_default_horror_no_cookie(client, monkeypatch):
    captured = {}
    real = main_module.templates.TemplateResponse

    def spy(request, name, context, *a, **k):
        captured["theme"] = context.get("theme")
        return real(request, name, context, *a, **k)

    monkeypatch.setattr(main_module.templates, "TemplateResponse", spy)
    resp = client.get("/")
    assert resp.status_code == 200
    assert captured["theme"] == "horror"


def test_theme_sea_cookie_passed_to_context(client, monkeypatch):
    captured = {}
    real = main_module.templates.TemplateResponse

    def spy(request, name, context, *a, **k):
        captured["theme"] = context.get("theme")
        return real(request, name, context, *a, **k)

    monkeypatch.setattr(main_module.templates, "TemplateResponse", spy)
    client.cookies.set("theme", "sea")
    resp = client.get("/")
    assert resp.status_code == 200
    assert captured["theme"] == "sea"


def test_theme_invalid_cookie_falls_back_to_horror(client, monkeypatch):
    captured = {}
    real = main_module.templates.TemplateResponse

    def spy(request, name, context, *a, **k):
        captured["theme"] = context.get("theme")
        return real(request, name, context, *a, **k)

    monkeypatch.setattr(main_module.templates, "TemplateResponse", spy)
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
# 8. Refresh (R2)
# ===========================================================================
def test_refresh_rebuilds_cache_on_changed_listing(client, patched_drive):
    before = client.get("/api/levels").json()
    before_ids = sorted(l["id"] for l in before["levels"] if l["available"])
    assert before_ids == [1, 2, 8]

    # Mutate the fake parent listing: add folder "12", remove folder "2".
    patched_drive[fake.ROOT_ID] = [
        {"id": fake.FOLDER_1, "name": "1", "mimeType": fake.FOLDER_MIME},
        {"id": fake.FOLDER_8, "name": "8", "mimeType": fake.FOLDER_MIME},
        {"id": "drv_folder_12", "name": "12", "mimeType": fake.FOLDER_MIME},
        {"id": fake.MISSING_ID, "name": "missing", "mimeType": fake.FOLDER_MIME},
    ]
    patched_drive["drv_folder_12"] = [
        {"id": "img_12a", "name": "12.1.jpeg", "mimeType": "image/jpeg"}
    ]

    refresh = client.post("/api/refresh")
    assert refresh.status_code == 200
    rbody = refresh.json()
    assert rbody["ready"] is True
    assert rbody["available"] == [1, 8, 12]
    assert rbody["missing_folder"] is True

    after = client.get("/api/levels").json()
    after_ids = [l["id"] for l in after["levels"]]
    after_available = sorted(l["id"] for l in after["levels"] if l["available"])
    # New span 0..12; available set changed.
    assert after_ids == list(range(0, 13))
    assert after_available == [1, 8, 12]


def test_refresh_without_refresh_keeps_cache(client, patched_drive):
    """Without POST /api/refresh, a mutated tree must NOT change /api/levels."""
    patched_drive[fake.ROOT_ID].append(
        {"id": "drv_folder_15", "name": "15", "mimeType": fake.FOLDER_MIME}
    )
    body = client.get("/api/levels").json()
    ids = [l["id"] for l in body["levels"]]
    assert ids == list(range(0, 9))  # unchanged — cache held (R2)


# ===========================================================================
# 9. Error mapping + secret isolation
# ===========================================================================
def test_unknown_level_id_returns_404(client):
    # Level 99 is outside the discovered span (0..8).
    resp = client.get("/api/levels/99/photos")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Unknown level."


def test_upstream_drive_failure_maps_to_502(client, monkeypatch):
    """A DriveError raised during /photos maps to 502, no leak."""

    async def boom(level_id):
        raise drive_service.DriveError("upstream boom")

    monkeypatch.setattr(drive_service, "get_level_photos", boom)
    resp = client.get("/api/levels/1/photos")
    assert resp.status_code == 502
    assert resp.json()["detail"] == "Upstream Drive error."


def test_media_upstream_failure_maps_to_502(client, monkeypatch):
    """resolve_media raising DriveError -> media proxy 502."""

    async def boom(level_id, file_id):
        raise drive_service.DriveError("upstream boom")

    monkeypatch.setattr(drive_service, "resolve_media", boom)
    resp = client.get(f"/api/levels/1/media/{fake.IMG_1A}")
    assert resp.status_code == 502
    assert resp.json()["detail"] == "Upstream Drive error."


def test_media_upstream_404_maps_to_502_via_real_path(client, patched_drive, patched_media):
    """An in-scope id whose upstream files.get 404s -> DriveError -> 502.

    (The MockTransport returns 404 for ids not in MEDIA_BYTES.) We register an
    in-scope file id that has no media bytes registered.
    """
    # Add a file to folder 1 that is in-scope but unknown to the byte mock.
    patched_drive[fake.FOLDER_1].append(
        {"id": "img_ghost", "name": "ghost.jpeg", "mimeType": "image/jpeg"}
    )
    client.post("/api/refresh")  # re-list so folder 1 children include the ghost
    resp = client.get("/api/levels/1/media/img_ghost")
    assert resp.status_code == 502
    assert resp.json()["detail"] == "Upstream Drive error."


def test_api_key_never_appears_in_any_response_body(client, patched_media):
    """F10/security: the GD_API_KEY must never leak into a client response."""
    bodies = []
    bodies.append(client.get("/api/levels").text)
    bodies.append(client.get("/api/levels/1/photos").text)
    bodies.append(client.get("/api/levels/3/photos").text)  # missing fallback
    bodies.append(client.get("/").text)
    bodies.append(client.get("/level/1").text)
    bodies.append(client.post("/api/refresh").text)
    media = client.get(f"/api/levels/1/media/{fake.IMG_1A}")
    bodies.append(media.content.decode("latin-1"))
    for b in bodies:
        assert DUMMY_KEY not in b
        assert "GD_API_KEY" not in b
        assert "googleapis.com" not in b


def test_key_sent_upstream_but_not_to_client(client, patched_media):
    """Defense-in-depth: the key IS used on the upstream Drive request (so the
    proxy works) yet is absent from the client-facing response."""
    resp = client.get(f"/api/levels/1/media/{fake.IMG_1A}")
    assert resp.status_code == 200
    upstream_req = patched_media["last_request"]
    # The key travels to Google on the server side...
    assert f"key={DUMMY_KEY}" in str(upstream_req.url)
    # ...but never back to the browser.
    assert DUMMY_KEY not in resp.content.decode("latin-1")
    assert "key=" not in resp.text if resp.text else True


# ===========================================================================
# Config / hermeticity guards
# ===========================================================================
def test_app_imports_and_serves_without_real_drive(client):
    """The app boots and serves even though no real Drive is reachable."""
    assert main_module.app.title.startswith("Archive 19")
    assert client.get("/api/levels").status_code == 200


def test_missing_api_key_raises_config_error(monkeypatch):
    """drive_service reads the key ONLY from os.environ; absence fails loudly."""
    monkeypatch.delenv("GD_API_KEY", raising=False)
    with pytest.raises(drive_service.DriveConfigError):
        drive_service._get_api_key()
