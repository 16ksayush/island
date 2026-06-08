"""Frontend / SSR behavioral test suite (T11b).

Verifies the now-real Jinja2 templates (templates/index.html, templates/level.html)
against the live backend contract. All Google Drive access stays mocked via the
shared fixtures in tests/conftest.py (patched_drive / patched_media) — the suite
is hermetic and offline.

Covers the 6 required areas:
  1. SSR theme class per cookie (D1/D3) — asserted against rendered HTML.
  2. Dynamic landing nav (F1) — one map hotspot per level; available vs sealed
     (door/island GRID retired by the M9/M10 map redesign).
  3. Level page render (F4/F5) — available + missing both 200; wires photos fetch.
  4. Theme toggle present on every page (F2).
  5. No Drive/secret leakage in rendered HTML (defense-in-depth).
  6. Static assets referenced by the templates resolve / exist.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import main as main_module
from tests import conftest as fake

BASE_DIR = Path(main_module.__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

# Substrings that must NEVER appear in client-facing HTML (key/Drive isolation).
LEAK_NEEDLES = ["googleapis", "drive.google", "AIza", "key="]


# ===========================================================================
# 1. SSR theme class per cookie (D1/D3) — asserted against rendered HTML
# ===========================================================================
def test_index_no_cookie_renders_theme_horror_class(client):
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    # <html class="theme-horror"> AND <body class="theme-horror ...">
    assert '<html lang="en" class="theme-horror">' in html, html[:300]
    assert 'class="theme-horror min-h-screen"' in html
    assert "theme-sea" not in html


def test_index_sea_cookie_renders_theme_sea_class(client):
    client.cookies.set("theme", "sea")
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert '<html lang="en" class="theme-sea">' in html, html[:300]
    assert 'class="theme-sea min-h-screen"' in html
    # Sea copy is rendered, not the horror copy.
    assert "archipelago" in html.lower()
    assert "theme-horror" not in html


def test_index_invalid_cookie_falls_back_to_horror_class(client):
    client.cookies.set("theme", "purple-nonsense")
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert '<html lang="en" class="theme-horror">' in html
    assert "theme-sea" not in html


def test_level_page_theme_class_honors_cookie(client):
    client.cookies.set("theme", "sea")
    resp = client.get("/level/1")
    assert resp.status_code == 200
    assert '<html lang="en" class="theme-sea">' in resp.text
    assert 'class="theme-sea min-h-screen"' in resp.text


# ===========================================================================
# 2. Dynamic landing navigation (F1) — superseded by the M9/M10 map redesign.
#    The door/island GRID (`.level-tile` + `badge-unavailable`) was deliberately
#    removed from BOTH themes (M9 Horror, M10 Sea), replaced by a full-bleed
#    illustrated map of 19 %-positioned `.map-hotspot` anchors -> /level/{id}.
#    These tests now assert the SAME invariants against the Horror map markup;
#    the Sea-arm equivalents live in tests/test_sea_landing.py.
# ===========================================================================
def _hotspot_hrefs(html: str) -> list[str]:
    """Every navigation entry is an <a class="map-hotspot ..." href="/level/{id}">."""
    return re.findall(r'<a\s+class="map-hotspot[^"]*"\s+href="(/level/\d+)"', html)


def test_grid_renders_exactly_one_tile_per_reported_level(client):
    # Superseded by the map redesign (M9/M10): the landing now exposes exactly
    # one hotspot per level id 0..18 (all 19), regardless of discovery span.
    # Invariant preserved: one navigation entry per level, no dupes, no extras.
    html = client.get("/").text  # no cookie -> horror map
    hrefs = _hotspot_hrefs(html)
    rendered_ids = sorted(int(h.rsplit("/", 1)[-1]) for h in hrefs)

    assert len(hrefs) == 19, (len(hrefs), rendered_ids)
    assert rendered_ids == list(range(0, 19))


def test_grid_distinguishes_available_from_unavailable(client):
    # Superseded by the map redesign (M9/M10): availability is now conveyed by
    # the `is-sealed` hotspot modifier + a "(sealed — fallback content)" label
    # suffix instead of the old `is-unavailable` tile + "Lost" badge.
    api = {lvl["id"]: lvl["available"] for lvl in client.get("/api/levels").json()["levels"]}
    html = client.get("/").text  # horror map

    for level_id in range(0, 19):
        available = api.get(level_id, False)
        pattern = re.compile(
            r'<a\s+class="(map-hotspot[^"]*)"\s+href="/level/%d"' % level_id
        )
        m = pattern.search(html)
        assert m, f"no hotspot rendered for level {level_id}"
        cls = m.group(1)
        if available:
            assert "is-sealed" not in cls, f"level {level_id} wrongly marked sealed"
        else:
            assert "is-sealed" in cls, f"level {level_id} should be marked sealed"

    # The sealed label suffix appears exactly once per unavailable level.
    sealed_count = html.count("(sealed — fallback content)")
    expected_sealed = sum(1 for lid in range(0, 19) if not api.get(lid, False))
    assert sealed_count == expected_sealed, (sealed_count, expected_sealed)


def test_grid_available_tiles_match_api_available_set(client):
    # Superseded by the map redesign (M9/M10): available hotspots carry the bare
    # `class="map-hotspot"` (no is-sealed); the set must match /api/levels.
    api = client.get("/api/levels").json()["levels"]
    available_ids = sorted(lvl["id"] for lvl in api if lvl["available"])
    # Mocked tree -> folders 1, 2, 8 present.
    assert available_ids == [1, 2, 8]

    html = client.get("/").text  # horror map
    available_hotspots = re.findall(
        r'<a\s+class="map-hotspot"\s+href="/level/(\d+)"', html
    )
    assert sorted(int(x) for x in available_hotspots) == available_ids


# ===========================================================================
# 3. Level page render (F4/F5) — available + missing both 200; wires fetch
# ===========================================================================
def test_level_page_available_renders_id_and_wires_fetch(client):
    resp = client.get("/level/1")
    assert resp.status_code == 200
    html = resp.text
    # Level id present in markup AND in the inline JS bootstrap.
    assert "Room 1" in html or "Island 1" in html
    assert "var levelId = 1;" in html
    # The inline JS fetches the photos contract for this level.
    assert 'fetch("/api/levels/" + levelId + "/photos"' in html
    # Available -> SSR did not render the salvaged-fallback note.
    assert "var ssrAvailable = true;" in html
    assert "salvaged fallback content" not in html


def test_level_page_missing_renders_fallback_note_and_id(client):
    # Level 3 is absent in the mocked tree (span 0..8, only 1/2/8 present).
    resp = client.get("/level/3")
    assert resp.status_code == 200
    html = resp.text
    assert "var levelId = 3;" in html
    assert "var ssrAvailable = false;" in html
    # Missing-level page shows the salvaged-fallback note (F5).
    assert "salvaged fallback content" in html
    # Still wires the same photos fetch (backend returns fallback payload).
    assert 'fetch("/api/levels/" + levelId + "/photos"' in html


def test_level_page_theme_class_present(client):
    resp = client.get("/level/8")
    assert resp.status_code == 200
    assert '<html lang="en" class="theme-horror">' in resp.text
    assert "var levelId = 8;" in resp.text


# ===========================================================================
# 4. Theme toggle present on every page (F2)
# ===========================================================================
def test_theme_toggle_present_on_index(client):
    html = client.get("/").text
    assert 'id="theme-toggle"' in html
    assert 'aria-label="Toggle between Horror and Sea themes"' in html


def test_theme_toggle_present_on_level_pages(client):
    for path in ("/level/1", "/level/3", "/level/8"):
        html = client.get(path).text
        assert 'id="theme-toggle"' in html, f"toggle missing on {path}"
        assert 'aria-label="Toggle between Horror and Sea themes"' in html, path


def test_theme_toggle_label_swaps_with_theme(client):
    horror = client.get("/").text
    assert "Sail to the Sea" in horror
    client.cookies.set("theme", "sea")
    sea = client.get("/").text
    assert "Enter the Corridor" in sea


# ===========================================================================
# 5. No Drive/secret leakage in rendered HTML (defense-in-depth)
# ===========================================================================
@pytest.mark.parametrize("path", ["/", "/level/1", "/level/3", "/level/8"])
def test_no_secret_or_drive_leak_in_rendered_html(client, path):
    html = client.get(path).text
    for needle in LEAK_NEEDLES:
        assert needle not in html, f"leaked '{needle}' in {path}"
    # The dummy key value itself must never appear.
    assert fake.__dict__.get("DUMMY_KEY", "TEST-DUMMY-KEY-do-not-use") not in html
    assert "TEST-DUMMY-KEY-do-not-use" not in html


def test_no_secret_leak_with_sea_theme(client):
    client.cookies.set("theme", "sea")
    for path in ("/", "/level/3"):
        html = client.get(path).text
        for needle in LEAK_NEEDLES:
            assert needle not in html, f"leaked '{needle}' in {path} (sea)"


# ===========================================================================
# 6. Static assets referenced by templates resolve / exist
# ===========================================================================
REFERENCED_ASSETS = ["/static/style.css", "/static/theme.js", "/static/audio-engine.js"]


@pytest.mark.parametrize("asset", REFERENCED_ASSETS)
def test_referenced_static_asset_exists_on_disk(asset):
    rel = asset[len("/static/"):]
    path = STATIC_DIR / rel
    assert path.exists(), f"{path} referenced by templates but missing on disk"
    assert path.stat().st_size > 0, f"{path} is empty"


@pytest.mark.parametrize("asset", REFERENCED_ASSETS)
def test_referenced_static_asset_served_200(client, asset):
    resp = client.get(asset)
    assert resp.status_code == 200, f"{asset} -> {resp.status_code}"
    assert len(resp.content) > 0


def _links_style_css(html: str) -> bool:
    # style.css is now cache-busted (?v=N) after the M9/M10 map redesign; accept
    # the bare link OR any ?v=<n> query so the guard tracks cache-bust bumps.
    return bool(
        re.search(r'<link rel="stylesheet" href="/static/style\.css(?:\?v=\d+)?" />', html)
    )


def test_index_links_all_static_assets(client):
    html = client.get("/").text
    assert _links_style_css(html), "style.css link missing/unexpected form"
    assert '<script src="/static/theme.js"></script>' in html
    assert '<script src="/static/audio-engine.js"></script>' in html


def test_level_page_links_all_static_assets(client):
    html = client.get("/level/1").text
    assert '<link rel="stylesheet" href="/static/style.css" />' in html
    assert '<script src="/static/theme.js"></script>' in html
    assert '<script src="/static/audio-engine.js"></script>' in html
