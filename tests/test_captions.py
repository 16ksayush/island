"""Image-caption tests (pytest + FastAPI TestClient, Cloudinary mocked).

M13 conversion: captions are now keyed by ``(level, filename_stem)`` where the
stem is the Cloudinary ``public_id`` with its random ``_xxxxxx`` suffix stripped
(e.g. public_id ``1_uuasv3`` -> stem ``1``; ``2.1_zzzzaa`` -> stem ``2.1``). The
``/api/levels/{id}/photos`` image element adds ``caption: {sea, horror}`` ONLY
when a caption exists for that (level, stem); otherwise it is exactly
``{file_id, url}`` where ``file_id`` is the public_id and ``url`` is the keyless
``res.cloudinary.com`` CDN link.

Converted from the M11/Drive version: caption KEYS changed from Drive filenames
(``1.1.jpeg``) to stems (``1``/``2.1``), the back-compat assert checks the CDN
``url`` (no ``/media/`` proxy), and the CapQ1 regression now guards "keyed by
stem, not by public_id".

These tests do NOT depend on the real ``app/captions.json`` content — they seed
the caption cache directly (``captions._captions``) or point the loader at a
temp file. Cloudinary stays mocked via ``conftest.py`` (levels 1, 2, 8 present).
"""

from __future__ import annotations

import json
import re

import pytest

from app import captions
from app import main as main_module
from tests import conftest as fake


@pytest.fixture(autouse=True)
def reset_caption_cache():
    """Isolate the module-level caption cache before & after each test."""
    original = captions._captions
    captions._captions = None
    yield
    captions._captions = original


def _seed(mapping):
    """Seed the caption cache directly (bypasses disk for determinism)."""
    captions._captions = mapping


# ===========================================================================
# 1. Payload WITH caption (keyed by filename STEM)
# ===========================================================================
def test_photo_payload_includes_caption_when_present(client):
    """A captioned (level, stem) emits caption: {sea, horror} verbatim.

    Level 1 holds public_ids ``1_uuasv3`` (stem "1") and ``1.2_abc123`` (stem
    "1.2"). We caption ONLY stem "1".
    """
    _seed(
        {
            "1": {
                fake.STEM_1A: {
                    "sea": "Sunlit cove of Island 1",
                    "horror": "The first door creaks open",
                }
            }
        }
    )
    body = client.get("/api/levels/1/photos").json()
    by_id = {img["file_id"]: img for img in body["images"]}

    captioned = by_id[fake.PID_1A]
    assert captioned["caption"] == {
        "sea": "Sunlit cove of Island 1",
        "horror": "The first door creaks open",
    }
    # Core contract preserved: file_id = public_id, url = keyless CDN link.
    assert captioned["file_id"] == fake.PID_1A
    assert captioned["url"] == fake._cdn_url(fake.PID_1A, "jpg")


# ===========================================================================
# 2. Payload WITHOUT caption — additive / back-compat contract
# ===========================================================================
def test_photo_without_caption_has_exactly_file_id_and_url(client):
    """An image with no caption entry keeps keys EXACTLY {file_id, url}."""
    _seed({"1": {fake.STEM_1A: {"sea": "x", "horror": "y"}}})
    body = client.get("/api/levels/1/photos").json()
    by_id = {img["file_id"]: img for img in body["images"]}

    uncaptioned = by_id[fake.PID_1B]  # stem "1.2" has no caption
    assert set(uncaptioned.keys()) == {"file_id", "url"}
    assert "caption" not in uncaptioned


def test_photo_payload_no_captions_at_all_is_legacy_shape(client):
    """Empty caption map -> every image element is the legacy {file_id, url}."""
    _seed({})
    body = client.get("/api/levels/1/photos").json()
    assert len(body["images"]) == 2
    for img in body["images"]:
        assert set(img.keys()) == {"file_id", "url"}


# ===========================================================================
# 3. Partial entry (only one theme)
# ===========================================================================
def test_partial_caption_only_sea_yields_empty_horror(client):
    """A caption with only 'sea' -> the payload emits horror: "" (no error)."""
    _seed({"1": {fake.STEM_1A: {"sea": "Only the tide speaks"}}})
    body = client.get("/api/levels/1/photos").json()
    by_id = {img["file_id"]: img for img in body["images"]}

    cap = by_id[fake.PID_1A]["caption"]
    assert cap == {"sea": "Only the tide speaks", "horror": ""}


def test_partial_caption_only_horror_yields_empty_sea(client):
    """Symmetric: only 'horror' -> sea is "" and both keys are always present."""
    _seed({"1": {fake.STEM_1A: {"horror": "Something watches"}}})
    body = client.get("/api/levels/1/photos").json()
    by_id = {img["file_id"]: img for img in body["images"]}

    cap = by_id[fake.PID_1A]["caption"]
    assert cap == {"sea": "", "horror": "Something watches"}


def test_caption_dict_always_has_both_keys(client):
    """When a caption is emitted, BOTH 'sea' and 'horror' keys exist."""
    _seed({"1": {fake.STEM_1A: {"sea": "s"}}})
    body = client.get("/api/levels/1/photos").json()
    cap = next(i for i in body["images"] if i["file_id"] == fake.PID_1A)["caption"]
    assert set(cap.keys()) == {"sea", "horror"}


# ===========================================================================
# 4. Loader tolerance — missing / malformed / wrong-shape, never raises
# ===========================================================================
def test_load_missing_file_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(captions, "CAPTIONS_PATH", tmp_path / "nope.json")
    captions._captions = None
    assert captions.load_captions() == {}
    # And a lookup against the empty map returns None, never raises.
    assert captions.get_caption(1, "1") is None


def test_load_malformed_json_returns_empty(monkeypatch, tmp_path):
    bad = tmp_path / "captions.json"
    bad.write_text("{ this is : not json ,,, ", encoding="utf-8")
    monkeypatch.setattr(captions, "CAPTIONS_PATH", bad)
    captions._captions = None
    assert captions.load_captions() == {}
    assert captions.get_caption(1, "1") is None


def test_load_wrong_toplevel_shape_returns_empty(monkeypatch, tmp_path):
    """A JSON array (not an object) at top level degrades to empty."""
    bad = tmp_path / "captions.json"
    bad.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    monkeypatch.setattr(captions, "CAPTIONS_PATH", bad)
    captions._captions = None
    assert captions.load_captions() == {}


def test_load_drops_garbage_entries_keeps_valid(monkeypatch, tmp_path):
    """Normalization keeps well-formed entries and silently drops garbage."""
    src = {
        "1": {
            "good": {"sea": "S", "horror": "H"},
            "bad": "not-an-object",  # dropped
            "nonstr": {"sea": 123, "horror": None},  # non-str -> dropped
        },
        "2": "not-a-dict",  # whole level dropped
    }
    f = tmp_path / "captions.json"
    f.write_text(json.dumps(src), encoding="utf-8")
    monkeypatch.setattr(captions, "CAPTIONS_PATH", f)
    captions._captions = None
    loaded = captions.load_captions()
    assert loaded == {"1": {"good": {"sea": "S", "horror": "H"}}}
    assert "2" not in loaded


def test_get_caption_unknown_level_and_stem_return_none():
    _seed({"1": {fake.STEM_1A: {"sea": "s", "horror": "h"}}})
    assert captions.get_caption(99, fake.STEM_1A) is None  # unknown level
    assert captions.get_caption(1, "absent-stem") is None  # unknown stem


# ===========================================================================
# 5. POST /api/refresh reloads captions
# ===========================================================================
def test_refresh_reloads_captions_from_disk(client, monkeypatch, tmp_path):
    """Changing the source file + POST /api/refresh reflects the new caption."""
    f = tmp_path / "captions.json"
    monkeypatch.setattr(captions, "CAPTIONS_PATH", f)

    # v1 of the file: no caption for stem "1".
    f.write_text(json.dumps({"1": {"other": {"sea": "x", "horror": "y"}}}),
                 encoding="utf-8")
    captions._captions = None
    body = client.get("/api/levels/1/photos").json()
    one = next(i for i in body["images"] if i["file_id"] == fake.PID_1A)
    assert "caption" not in one

    # Edit the file, then refresh — the new caption must now appear.
    f.write_text(
        json.dumps({"1": {fake.STEM_1A: {"sea": "fresh sea", "horror": "fresh horror"}}}),
        encoding="utf-8",
    )
    assert client.post("/api/refresh").status_code == 200
    body2 = client.get("/api/levels/1/photos").json()
    one2 = next(i for i in body2["images"] if i["file_id"] == fake.PID_1A)
    assert one2["caption"] == {"sea": "fresh sea", "horror": "fresh horror"}


def test_reload_captions_replaces_cache(monkeypatch, tmp_path):
    """reload_captions() re-reads disk and replaces the in-memory cache."""
    f = tmp_path / "captions.json"
    monkeypatch.setattr(captions, "CAPTIONS_PATH", f)
    f.write_text(json.dumps({"1": {"a": {"sea": "1", "horror": "1"}}}),
                 encoding="utf-8")
    captions._captions = None
    assert captions.load_captions() == {"1": {"a": {"sea": "1", "horror": "1"}}}

    f.write_text(json.dumps({"2": {"b": {"sea": "2", "horror": "2"}}}),
                 encoding="utf-8")
    # Without reload the cache is stale...
    assert "2" not in captions.load_captions()
    # ...reload picks up the change.
    assert captions.reload_captions() == {"2": {"b": {"sea": "2", "horror": "2"}}}


# ===========================================================================
# 6. Level page renders the caption path + cache-busted CSS
# ===========================================================================
def test_level_page_contains_slide_caption_render_path(client):
    html = client.get("/level/1").text
    assert html.startswith("<!") or "<html" in html.lower()  # real page
    # The JS render path and the figcaption class must be present.
    assert "slide-caption" in html
    assert "img.caption" in html


def test_level_page_links_versioned_stylesheet(client):
    html = client.get("/level/1").text
    # A2 sign-off bumped the cache-bust token (?v=6 -> ?v=7). Use a regex so the
    # guard tracks future cache-bust bumps instead of a frozen literal, matching
    # test_frontend.py's _links_style_css(...) (?v=\d+) pattern.
    assert re.search(r"/static/style\.css\?v=\d+", html), html[:300]


# ===========================================================================
# 7. Caption keyed by STEM, not public_id (CapQ1 regression guard)
# ===========================================================================
def test_caption_lookup_uses_stem_not_public_id(client):
    """Seeding by the Cloudinary public_id (wrong key) must NOT produce a
    caption; only the derived filename stem is the lookup key."""
    _seed({"1": {fake.PID_1A: {"sea": "wrong-key", "horror": "wrong-key"}}})
    body = client.get("/api/levels/1/photos").json()
    captioned = next(i for i in body["images"] if i["file_id"] == fake.PID_1A)
    assert "caption" not in captioned


def test_caption_attaches_for_dotted_stem(client):
    """A dotted stem like "2.1" (public_id 2.1_zzzzaa) attaches correctly."""
    _seed({"2": {fake.STEM_2A: {"sea": "island two", "horror": "room two"}}})
    body = client.get("/api/levels/2/photos").json()
    img = next(i for i in body["images"] if i["file_id"] == fake.PID_2A)
    assert img["caption"] == {"sea": "island two", "horror": "room two"}


# ===========================================================================
# 8. Real committed captions.json is stem-keyed (M13 re-key sanity)
# ===========================================================================
def test_committed_captions_json_is_stem_keyed():
    """The shipped app/captions.json keys files by stem (e.g. "1", "2.1"),
    NOT by a Cloudinary public_id (no random "_xxxxxx" suffix) and NOT by a
    legacy ".jpeg" filename. This guards the M13 re-key from regressing."""
    import re as _re

    captions._captions = None
    monkey_path = captions.CAPTIONS_PATH
    if not monkey_path.is_file():
        pytest.skip("app/captions.json not present in this checkout")
    loaded = captions.load_captions()
    assert loaded, "captions.json loaded empty (expected real content)"
    suffix_re = _re.compile(r"_[A-Za-z0-9]{6}$")
    for level_key, files in loaded.items():
        for stem in files:
            assert not stem.endswith(".jpeg") and not stem.endswith(".jpg"), (
                f"caption key {stem!r} looks like a legacy filename, not a stem"
            )
            assert not suffix_re.search(stem), (
                f"caption key {stem!r} carries a Cloudinary random suffix; "
                "captions must key on the stripped stem"
            )
