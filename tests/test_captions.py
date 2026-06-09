"""M11 — image-caption tests (pytest + FastAPI TestClient, Drive fully mocked).

Captions are an OPTIONAL, additive feature keyed by ``(level, filename)``:
``/api/levels/{id}/photos`` adds ``caption: {sea, horror}`` to an image element
ONLY when a caption exists for that (level, filename); otherwise the image
element is byte-for-byte the old ``{file_id, url}`` contract.

These tests are deterministic and do NOT depend on the real
``app/captions.json`` content — they control the caption map directly by
seeding the module-cache global ``captions._captions`` (the same global the
loader/cache use), or by pointing the loader at a temp path. The Drive layer is
the same hermetic fake from ``conftest.py`` (folders 1, 2 present; 3+ missing).

Covers the M11 acceptance items:
  1. Payload WITH caption: image element carries {sea, horror} expected strings.
  2. Payload WITHOUT caption (back-compat): keys are exactly {file_id, url}.
  3. Partial entry (only sea) -> horror is "" (no missing-key error).
  4. Loader tolerance: missing file / malformed JSON -> empty map, never raises.
  5. POST /api/refresh reloads captions (reflects a changed source).
  6. /level/{id} HTML carries the slide-caption render path + style.css?v=6.
"""

from __future__ import annotations

import json

import pytest

from app import captions
from app import main as main_module
from tests import conftest as fake


@pytest.fixture(autouse=True)
def reset_caption_cache():
    """Isolate the module-level caption cache before & after each test.

    The production cache is a module global (``captions._captions``); reset it
    to ``None`` (the "not yet loaded" sentinel) so one test's seeded map cannot
    leak into another, and so the cache lazily reloads from disk afterwards.
    """
    original = captions._captions
    captions._captions = None
    yield
    captions._captions = original


def _seed(mapping):
    """Seed the caption cache directly (bypasses disk for determinism)."""
    captions._captions = mapping


# ===========================================================================
# 1. Payload WITH caption
# ===========================================================================
def test_photo_payload_includes_caption_when_present(client):
    """A captioned (level, filename) emits caption: {sea, horror} verbatim.

    Folder 1 holds images named '1.1.jpeg' (IMG_1A) and '1.2.jpeg' (IMG_1B)
    in the fake Drive tree. We caption ONLY '1.1.jpeg'.
    """
    _seed(
        {
            "1": {
                "1.1.jpeg": {
                    "sea": "Sunlit cove of Island 1",
                    "horror": "The first door creaks open",
                }
            }
        }
    )
    body = client.get("/api/levels/1/photos").json()
    by_id = {img["file_id"]: img for img in body["images"]}

    captioned = by_id[fake.IMG_1A]
    assert captioned["caption"] == {
        "sea": "Sunlit cove of Island 1",
        "horror": "The first door creaks open",
    }
    # Core contract preserved alongside the additive key.
    assert captioned["file_id"] == fake.IMG_1A
    assert captioned["url"] == f"/api/levels/1/media/{fake.IMG_1A}"


# ===========================================================================
# 2. Payload WITHOUT caption — additive/back-compat contract
# ===========================================================================
def test_photo_without_caption_has_exactly_file_id_and_url(client):
    """An image with no caption entry keeps keys EXACTLY {file_id, url}.

    Same seeded map as above captions only '1.1.jpeg', so '1.2.jpeg' (IMG_1B)
    must carry NO caption key at all (guards the additive contract).
    """
    _seed({"1": {"1.1.jpeg": {"sea": "x", "horror": "y"}}})
    body = client.get("/api/levels/1/photos").json()
    by_id = {img["file_id"]: img for img in body["images"]}

    uncaptioned = by_id[fake.IMG_1B]
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
    _seed({"1": {"1.1.jpeg": {"sea": "Only the tide speaks"}}})
    body = client.get("/api/levels/1/photos").json()
    by_id = {img["file_id"]: img for img in body["images"]}

    cap = by_id[fake.IMG_1A]["caption"]
    assert cap == {"sea": "Only the tide speaks", "horror": ""}


def test_partial_caption_only_horror_yields_empty_sea(client):
    """Symmetric: only 'horror' -> sea is "" and both keys are always present."""
    _seed({"1": {"1.1.jpeg": {"horror": "Something watches"}}})
    body = client.get("/api/levels/1/photos").json()
    by_id = {img["file_id"]: img for img in body["images"]}

    cap = by_id[fake.IMG_1A]["caption"]
    assert cap == {"sea": "", "horror": "Something watches"}


def test_caption_dict_always_has_both_keys(client):
    """When a caption is emitted, BOTH 'sea' and 'horror' keys exist (client
    can toggle theme without a KeyError)."""
    _seed({"1": {"1.1.jpeg": {"sea": "s"}}})
    body = client.get("/api/levels/1/photos").json()
    cap = next(i for i in body["images"] if i["file_id"] == fake.IMG_1A)["caption"]
    assert set(cap.keys()) == {"sea", "horror"}


# ===========================================================================
# 4. Loader tolerance — missing / malformed / wrong-shape, never raises
# ===========================================================================
def test_load_missing_file_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(captions, "CAPTIONS_PATH", tmp_path / "nope.json")
    captions._captions = None
    assert captions.load_captions() == {}
    # And a lookup against the empty map returns None, never raises.
    assert captions.get_caption(1, "1.1.jpeg") is None


def test_load_malformed_json_returns_empty(monkeypatch, tmp_path):
    bad = tmp_path / "captions.json"
    bad.write_text("{ this is : not json ,,, ", encoding="utf-8")
    monkeypatch.setattr(captions, "CAPTIONS_PATH", bad)
    captions._captions = None
    assert captions.load_captions() == {}
    assert captions.get_caption(1, "1.1.jpeg") is None


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
            "good.jpeg": {"sea": "S", "horror": "H"},
            "bad.jpeg": "not-an-object",  # dropped
            "nonstr.jpeg": {"sea": 123, "horror": None},  # non-str -> dropped
        },
        "2": "not-a-dict",  # whole level dropped
    }
    f = tmp_path / "captions.json"
    f.write_text(json.dumps(src), encoding="utf-8")
    monkeypatch.setattr(captions, "CAPTIONS_PATH", f)
    captions._captions = None
    loaded = captions.load_captions()
    assert loaded == {"1": {"good.jpeg": {"sea": "S", "horror": "H"}}}
    assert "2" not in loaded


def test_get_caption_unknown_level_and_filename_return_none():
    _seed({"1": {"1.1.jpeg": {"sea": "s", "horror": "h"}}})
    assert captions.get_caption(99, "1.1.jpeg") is None  # unknown level
    assert captions.get_caption(1, "absent.jpeg") is None  # unknown filename


# ===========================================================================
# 5. POST /api/refresh reloads captions
# ===========================================================================
def test_refresh_reloads_captions_from_disk(client, monkeypatch, tmp_path):
    """Changing the source file + POST /api/refresh reflects the new caption."""
    f = tmp_path / "captions.json"
    monkeypatch.setattr(captions, "CAPTIONS_PATH", f)

    # v1 of the file: no caption for 1.1.jpeg.
    f.write_text(json.dumps({"1": {"other.jpeg": {"sea": "x", "horror": "y"}}}),
                 encoding="utf-8")
    captions._captions = None
    body = client.get("/api/levels/1/photos").json()
    one_one = next(i for i in body["images"] if i["file_id"] == fake.IMG_1A)
    assert "caption" not in one_one

    # Edit the file, then refresh — the new caption must now appear.
    f.write_text(
        json.dumps({"1": {"1.1.jpeg": {"sea": "fresh sea", "horror": "fresh horror"}}}),
        encoding="utf-8",
    )
    assert client.post("/api/refresh").status_code == 200
    body2 = client.get("/api/levels/1/photos").json()
    one_one2 = next(i for i in body2["images"] if i["file_id"] == fake.IMG_1A)
    assert one_one2["caption"] == {"sea": "fresh sea", "horror": "fresh horror"}


def test_reload_captions_replaces_cache(monkeypatch, tmp_path):
    """reload_captions() re-reads disk and replaces the in-memory cache."""
    f = tmp_path / "captions.json"
    monkeypatch.setattr(captions, "CAPTIONS_PATH", f)
    f.write_text(json.dumps({"1": {"a.jpeg": {"sea": "1", "horror": "1"}}}),
                 encoding="utf-8")
    captions._captions = None
    assert captions.load_captions() == {"1": {"a.jpeg": {"sea": "1", "horror": "1"}}}

    f.write_text(json.dumps({"2": {"b.jpeg": {"sea": "2", "horror": "2"}}}),
                 encoding="utf-8")
    # Without reload the cache is stale...
    assert "2" not in captions.load_captions()
    # ...reload picks up the change.
    assert captions.reload_captions() == {"2": {"b.jpeg": {"sea": "2", "horror": "2"}}}


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
    assert "/static/style.css?v=6" in html


# ===========================================================================
# 7. Caption keyed by filename, not file_id (CapQ1 regression guard)
# ===========================================================================
def test_caption_lookup_uses_filename_not_file_id(client):
    """Seeding by the Drive FILE ID (wrong key) must NOT produce a caption;
    only the PhotoRef.name (filename) is the lookup key."""
    _seed({"1": {fake.IMG_1A: {"sea": "wrong-key", "horror": "wrong-key"}}})
    body = client.get("/api/levels/1/photos").json()
    captioned = next(i for i in body["images"] if i["file_id"] == fake.IMG_1A)
    assert "caption" not in captioned
