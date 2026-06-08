"""M10 — Sea/Light landing map regression suite (NF-SR4).

Verifies the frontend-only Sea-theme arm of templates/index.html: the old island
GRID is replaced by a full-bleed illustrated archipelago map with 19 %-positioned
clickable hotspots -> /level/{id}. Drive stays mocked via tests/conftest.py
(patched_drive) — the suite is hermetic, offline, and passes against placeholder
assets.

The mocked Drive tree (tests/conftest.py) yields discovered/available levels
{1, 2, 8}; every other id in 0..18 is therefore UNAVAILABLE -> rendered .is-sealed
with a "(sunken — fallback content)" aria-label suffix.

Required coverage:
  1. SSR Sea map from cookie; OLD Sea grid markup is gone.
  2. All 19 hotspots href="/level/0".."/level/18".
  3. Sealed styling + a11y (is-sealed + sunken suffix vs "Level N — <Name>").
  4. Horror untouched (NF-SR4 regression): horror map asset only, no sea webp.
  5. Routing unaffected for both themes; /api/levels unchanged.
"""

from __future__ import annotations

import html as _html
import re

import pytest

# Theme-arm asset paths (the load-bearing strings the M10 diff hinges on).
SEA_IMG = "/static/img/light/landing-map.v2.webp"
HORROR_IMG = "/static/img/horror/landing-map.v2.jpg"

# Discovered/available levels from the mocked Drive tree (conftest _default_tree).
AVAILABLE_IDS = [1, 2, 8]
ALL_IDS = list(range(19))
SEALED_IDS = [i for i in ALL_IDS if i not in AVAILABLE_IDS]

# The island names baked into the Sea arm (sea_names dict in index.html).
SEA_NAMES = {
    0: "Ruin", 1: "Crypt", 2: "Witch's Hut", 3: "Mausoleum", 4: "Ruined Abbey",
    5: "Prison", 6: "Graveyard", 7: "Sealed", 8: "Sunken Temple", 9: "Forbidden",
    10: "Cavern", 11: "Sepulcher", 12: "Watch Tower", 13: "Pit", 14: "Final Keep",
    15: "Haunted Tower", 16: "Cursed Orchard", 17: "Dragon's Den",
    18: "Forgotten Armory",
}


def _sea_html(client) -> str:
    client.cookies.set("theme", "sea")
    resp = client.get("/")
    assert resp.status_code == 200, resp.status_code
    return resp.text


# ===========================================================================
# 1. SSR Sea map from cookie; OLD island grid is gone.
# ===========================================================================
def test_sea_cookie_renders_full_bleed_map(client):
    html = _sea_html(client)
    assert '<html lang="en" class="theme-sea">' in html, html[:300]
    assert 'class="theme-sea min-h-screen"' in html
    # Full-bleed map container + image (replaces the island grid).
    assert 'class="layer sea-landing"' in html
    assert 'class="sea-map"' in html
    assert 'class="sea-map-hotspots"' in html
    assert f'src="{SEA_IMG}"' in html, "Sea map asset src missing/changed"


def test_sea_landing_drops_old_island_grid(client):
    """The old Sea arm rendered an island GRID of `level-tile` cards with a
    'Sunken' label and an 'open archipelago — choose an island.' subtitle. The
    map redesign DELETES that grid for Sea; assert those markers are gone.

    NB: the literal word 'archipelago' still legitimately appears in the new
    arm (HTML comment + the map <img alt> text), so we do NOT assert its
    absence — we target the grid-specific copy instead.
    """
    html = _sea_html(client)
    # No island-grid tiles remain in the Sea landing.
    assert "level-tile" not in html, "old Sea island-grid `level-tile` markup leaked"
    # No grid availability badges / status cards.
    assert "badge-unavailable" not in html
    # The old grid subtitle is gone (NB: 'Sunken' now legitimately appears in
    # the island name 'Sunken Temple' and the '(sunken — ...)' suffix, so we
    # target the grid-only subtitle copy instead).
    assert "open archipelago" not in html.lower()
    # The sr-only heading should be the map heading, not a grid subtitle.
    assert '<h1 class="sr-only">Tour-de-Anshika — choose an island</h1>' in html


# ===========================================================================
# 2. All 19 hotspots href="/level/0".."/level/18".
# ===========================================================================
def _hotspot_anchors(html: str) -> list[str]:
    """Return each <a class="map-hotspot...">...</a> block in document order."""
    return re.findall(r'<a\s+class="map-hotspot[^"]*"[^>]*?>', html)


def test_sea_landing_has_19_hotspots(client):
    html = _sea_html(client)
    anchors = _hotspot_anchors(html)
    assert len(anchors) == 19, f"expected 19 hotspots, got {len(anchors)}"
    # Exactly one href per level id 0..18, no duplicates, no extras.
    hrefs = re.findall(r'<a\s+class="map-hotspot[^"]*"\s+href="(/level/\d+)"', html)
    ids = sorted(int(h.rsplit("/", 1)[-1]) for h in hrefs)
    assert ids == ALL_IDS, ids
    for i in ALL_IDS:
        assert f'href="/level/{i}"' in html, f"missing hotspot for level {i}"


# ===========================================================================
# 3. Sealed styling + a11y (is-sealed + sunken suffix vs "Level N — <Name>").
# ===========================================================================
def _anchor_for(html: str, level_id: int) -> str:
    m = re.search(
        r'<a\s+class="(map-hotspot[^"]*)"\s+href="/level/%d"[^>]*?aria-label="([^"]*)"'
        % level_id,
        html,
    )
    assert m is not None, f"no map-hotspot anchor found for level {level_id}"
    return m  # group(1)=class, group(2)=aria-label


@pytest.mark.parametrize("level_id", AVAILABLE_IDS)
def test_available_hotspot_label_and_class(client, level_id):
    html = _sea_html(client)
    m = _anchor_for(html, level_id)
    cls, raw_label = m.group(1), m.group(2)
    label = _html.unescape(raw_label)  # Jinja autoescapes ' -> &#39;
    assert "is-sealed" not in cls, f"available level {level_id} wrongly sealed"
    expected = f"Level {level_id} — {SEA_NAMES[level_id]}"
    assert label == expected, f"level {level_id}: aria-label={label!r}"
    assert "sunken" not in label, f"available level {level_id} has sunken suffix"


@pytest.mark.parametrize("level_id", SEALED_IDS)
def test_sealed_hotspot_label_and_class(client, level_id):
    html = _sea_html(client)
    m = _anchor_for(html, level_id)
    cls, raw_label = m.group(1), m.group(2)
    label = _html.unescape(raw_label)  # Jinja autoescapes ' -> &#39;
    assert "is-sealed" in cls, f"unavailable level {level_id} not marked is-sealed"
    expected = f"Level {level_id} — {SEA_NAMES[level_id]} (sunken — fallback content)"
    assert label == expected, f"level {level_id}: aria-label={label!r}"


def test_sealed_vs_available_counts_match_discovery(client):
    """Sealed set is exactly the complement of discovery's available set."""
    html = _sea_html(client)
    sealed = re.findall(
        r'<a\s+class="map-hotspot is-sealed"\s+href="/level/(\d+)"', html
    )
    sealed_ids = sorted(int(x) for x in sealed)
    assert sealed_ids == SEALED_IDS, sealed_ids
    assert html.count("(sunken — fallback content)") == len(SEALED_IDS)
    # Available hotspots carry the bare class (no is-sealed).
    available = re.findall(
        r'<a\s+class="map-hotspot"\s+href="/level/(\d+)"', html
    )
    assert sorted(int(x) for x in available) == AVAILABLE_IDS


def test_sea_names_come_from_template_dict(client):
    """Spot-check the requirement's named example: Level 5 — Prison (sealed)."""
    html = _sea_html(client)
    assert 'aria-label="Level 5 — Prison (sunken — fallback content)"' in html


# ===========================================================================
# 4. Horror untouched (NF-SR4 regression).
# ===========================================================================
@pytest.mark.parametrize("cookie", [None, "horror", "purple-nonsense"])
def test_horror_arm_unchanged_and_no_sea_bleed(client, cookie):
    """Default/no-cookie + explicit horror + invalid cookie all -> horror map.
    The Sea map machinery must NOT bleed into the Horror landing.
    """
    if cookie is not None:
        client.cookies.set("theme", cookie)
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert '<html lang="en" class="theme-horror">' in html, html[:300]
    assert 'class="horror-map"' in html
    assert f'src="{HORROR_IMG}"' in html, "Horror map asset src missing/changed"
    # No Sea map ELEMENTS leak into the Horror arm. (The shared calibrate-JS
    # selector string ".horror-map, .sea-map" legitimately contains the
    # substring "sea-map", so we target the actual rendered sea elements.)
    assert 'class="sea-map"' not in html, "sea-map container leaked into Horror"
    assert 'class="layer sea-landing"' not in html, "sea-landing leaked into Horror"
    assert 'class="sea-map-img"' not in html, "sea-map-img leaked into Horror"
    assert SEA_IMG not in html, "sea webp leaked into Horror landing"
    assert "theme-sea" not in html


def test_horror_landing_still_has_19_hotspots(client):
    """Horror map keeps its own 19 hotspots (M9 contract unbroken by M10)."""
    html = client.get("/").text  # no cookie -> horror
    hrefs = re.findall(r'<a\s+class="map-hotspot[^"]*"\s+href="(/level/\d+)"', html)
    ids = sorted(int(h.rsplit("/", 1)[-1]) for h in hrefs)
    assert ids == ALL_IDS, ids


# ===========================================================================
# 5. Routing unaffected for both themes; /api/levels unchanged.
# ===========================================================================
@pytest.mark.parametrize("theme", ["sea", "horror"])
@pytest.mark.parametrize("level_id", [0, 1, 5, 8, 18])
def test_level_routes_200_under_both_themes(client, theme, level_id):
    client.cookies.set("theme", theme)
    resp = client.get(f"/level/{level_id}")
    assert resp.status_code == 200, (theme, level_id, resp.status_code)
    assert f'class="theme-{theme}' in resp.text, (theme, level_id)


def test_api_levels_unchanged_by_m10(client):
    resp = client.get("/api/levels")
    assert resp.status_code == 200
    body = resp.json()
    available = sorted(lvl["id"] for lvl in body["levels"] if lvl["available"])
    assert available == AVAILABLE_IDS, available
    # /api/levels is JSON only — no map markup or theme HTML bled into it.
    text = resp.text
    assert "sea-map" not in text and "map-hotspot" not in text


def test_calibrate_js_targets_both_maps(client):
    """The one-line calibrate-JS change must select `.horror-map, .sea-map`."""
    html = _sea_html(client)
    assert 'document.querySelector(".horror-map, .sea-map")' in html
