"""Sea/Light landing regression suite — MIGRATED to the M15 hybrid landing.

ORIGIN: this suite began as the M10 full-bleed raster-map Sea arm (19 %-pinned
`.map-hotspot` anchors over `<img class="sea-map" src=SEA_IMG>`). M15
(ARCHITECTURE §15.7 / NF-M15-8) retired that markup: the raster maps are KEPT on
disk but are now painted as the z-0 `.nav-backdrop` (CSS background-image +
active-theme preload <link>), and navigation is rendered TWICE per arm — an SVG
`<a class="nav-node">` per level AND a `<a>` inside a `.nav-list-item` per level
— CSS-toggled at 768px. So the SSR HTML carries 19 of EACH family (38 total) per
arm; counts here are scoped PER family, never a bare 19/38 over the document.

The Cloudinary Admin API stays mocked via tests/conftest.py — hermetic, offline,
passes against placeholder assets. Mocked resource set -> available {1, 2, 8};
every other id in 0..18 is UNAVAILABLE -> rendered with `--sealed` + the Sea
"(sunken — fallback content)" aria-label suffix.

Migrated coverage (old -> new):
  * `.sea-map` / `.sea-map-hotspots` / `<img src=SEA_IMG>`  ->  `.nav-backdrop`
    (aria-hidden) + active-theme preload <link> to the same map file. The map
    FILE-on-disk check is kept; the `<img src>` HTML assertion is removed.
  * `.map-hotspot` 19-anchor regex  ->  19 `.nav-node` AND 19 `.nav-list-item`.
  * `is-sealed` modifier  ->  `nav-node--sealed` / `nav-list-item--sealed`.
  * calibrate-JS `document.querySelector(".horror-map, .sea-map")`  -> REMOVED.
  * `sea_names` (e.g. "Level 5 — Prison")  -> kept, now in nav-node aria-labels
    and `.nav-list-name`.
"""

from __future__ import annotations

import html as _html
import re
from pathlib import Path

import pytest

from app import main as main_module

BASE_DIR = Path(main_module.__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

# Theme-arm backdrop map paths (KEPT on disk; now the .nav-backdrop background +
# the active-theme preload <link> target). These are the load-bearing strings.
SEA_IMG = "/static/img/light/landing-map.v2.webp"
HORROR_IMG = "/static/img/horror/landing-map.v2.jpg"

# Discovered/available levels from the mocked Cloudinary resource set.
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
# 1. SSR Sea hybrid from cookie; OLD raster-map + island-grid markers are gone.
# ===========================================================================
def test_sea_cookie_renders_hybrid_landing(client):
    html = _sea_html(client)
    assert '<html lang="en" class="theme-sea">' in html, html[:300]
    assert 'class="theme-sea min-h-screen"' in html
    # The hybrid Sea layer + BOTH representations + the painted backdrop.
    assert 'class="layer sea-landing"' in html
    assert 'class="nav-backdrop" aria-hidden="true"' in html
    assert 'class="nav-map"' in html
    assert 'class="nav-list"' in html
    # The retired raster-map overlay markers must be GONE.
    assert 'class="sea-map"' not in html, "retired .sea-map element leaked"
    assert 'class="sea-map-hotspots"' not in html, "retired hotspot layer leaked"
    assert 'class="map-hotspot' not in html, "retired .map-hotspot leaked"
    # The raster map is now the painted backdrop (CSS bg + preload), NOT an <img>.
    assert f'src="{SEA_IMG}"' not in html, "Sea map must not be an <img src> now"
    # Active-theme backdrop preload <link> points at the Sea map (same origin).
    assert f'href="{SEA_IMG}"' in html, "Sea backdrop preload <link> missing"


def test_sea_landing_drops_old_island_grid(client):
    """The old Sea arm rendered an island GRID of `level-tile` cards. That grid
    was retired by the map redesign and is NOT reintroduced by the M15 hybrid.
    """
    html = _sea_html(client)
    assert "level-tile" not in html, "old Sea island-grid `level-tile` markup leaked"
    assert "badge-unavailable" not in html
    assert "open archipelago" not in html.lower()
    # The sr-only heading is the hybrid Sea heading.
    assert '<h1 class="sr-only">Tour-de-Anshika — choose an island</h1>' in html


# ===========================================================================
# 2. 19 nav targets per family, href="/level/0".."/level/18".
# ===========================================================================
def _nav_node_anchors(html: str) -> list[str]:
    """Each <a class="nav-node...">...</a> open tag in document order."""
    return re.findall(r'<a\s+class="nav-node[^"]*"\s+href="/level/\d+"', html)


def test_sea_landing_has_19_nav_nodes(client):
    html = _sea_html(client)
    anchors = _nav_node_anchors(html)
    assert len(anchors) == 19, f"expected 19 nav-nodes, got {len(anchors)}"
    hrefs = re.findall(r'<a\s+class="nav-node[^"]*"\s+href="(/level/\d+)"', html)
    ids = sorted(int(h.rsplit("/", 1)[-1]) for h in hrefs)
    assert ids == ALL_IDS, ids


def test_sea_landing_has_19_nav_list_items(client):
    html = _sea_html(client)
    # The .nav-list-item <li>s each wrap an <a href="/level/{id}">.
    items = re.findall(r'<li\s+class="nav-list-item[^"]*">', html)
    assert len(items) == 19, f"expected 19 nav-list-items, got {len(items)}"
    list_hrefs = _nav_list_hrefs(html)
    assert sorted(list_hrefs) == ALL_IDS, list_hrefs


def _nav_list_hrefs(html: str) -> list[int]:
    """Level ids from the .nav-list <li> anchors (phone representation)."""
    out = []
    for m in re.finditer(
        r'<li\s+class="nav-list-item[^"]*">\s*<a\s+href="/level/(\d+)"', html
    ):
        out.append(int(m.group(1)))
    return out


# ===========================================================================
# 3. Sealed styling + a11y — nav-node--sealed + sunken suffix vs "Level N — Name".
#    Sea sealed wording is verbatim "(sunken — fallback content)".
# ===========================================================================
def _node_anchor_for(html: str, level_id: int):
    m = re.search(
        r'<a\s+class="(nav-node[^"]*)"\s+href="/level/%d"\s+aria-label="([^"]*)"'
        % level_id,
        html,
    )
    assert m is not None, f"no nav-node anchor found for level {level_id}"
    return m  # group(1)=class, group(2)=aria-label


@pytest.mark.parametrize("level_id", AVAILABLE_IDS)
def test_available_nav_node_label_and_class(client, level_id):
    html = _sea_html(client)
    m = _node_anchor_for(html, level_id)
    cls, raw_label = m.group(1), m.group(2)
    label = _html.unescape(raw_label)  # Jinja autoescapes ' -> &#39;
    assert "nav-node--sealed" not in cls, f"available level {level_id} wrongly sealed"
    expected = f"Level {level_id} — {SEA_NAMES[level_id]}"
    assert label == expected, f"level {level_id}: aria-label={label!r}"
    assert "sunken" not in label, f"available level {level_id} has sunken suffix"


@pytest.mark.parametrize("level_id", SEALED_IDS)
def test_sealed_nav_node_label_and_class(client, level_id):
    html = _sea_html(client)
    m = _node_anchor_for(html, level_id)
    cls, raw_label = m.group(1), m.group(2)
    label = _html.unescape(raw_label)
    assert "nav-node--sealed" in cls, f"unavailable level {level_id} not sealed"
    expected = (
        f"Level {level_id} — {SEA_NAMES[level_id]} (sunken — fallback content)"
    )
    assert label == expected, f"level {level_id}: aria-label={label!r}"


def test_sealed_vs_available_counts_match_discovery(client):
    """Sealed set is exactly the complement of discovery's available set, on the
    nav-node family. The Sea sealed suffix appears once per sealed level in EACH
    family (nav-node + nav-list) -> 2x the sealed count over the document."""
    html = _sea_html(client)
    sealed = re.findall(
        r'<a\s+class="nav-node nav-node--sealed[^"]*"\s+href="/level/(\d+)"', html
    )
    sealed_ids = sorted(int(x) for x in sealed)
    assert sealed_ids == SEALED_IDS, sealed_ids
    assert html.count("(sunken — fallback content)") == len(SEALED_IDS) * 2
    # Available nav-nodes carry no --sealed modifier (bare or kind-only classes).
    available = re.findall(
        r'<a\s+class="nav-node nav-node--(?!sealed)[a-z]+"\s+href="/level/(\d+)"',
        html,
    )
    assert sorted(int(x) for x in available) == AVAILABLE_IDS


def test_sea_names_come_from_template_dict(client):
    """Spot-check the requirement's named example: Level 5 — Prison (sealed)."""
    html = _sea_html(client)
    assert 'aria-label="Level 5 — Prison (sunken — fallback content)"' in html


def test_sea_list_name_carries_island_name(client):
    """The phone .nav-list-name reuses the same sea_names source."""
    html = _sea_html(client)
    # Available island name appears plain in the list.
    assert ">Crypt<" in html  # level 1, available
    # Sealed island name carries the "(sunken)" list-suffix.
    assert ">Prison (sunken)<" in html  # level 5, sealed


# ===========================================================================
# 4. Horror untouched (regression): backdrop is the horror map; no Sea bleed.
# ===========================================================================
@pytest.mark.parametrize("cookie", [None, "horror", "purple-nonsense"])
def test_horror_arm_unchanged_and_no_sea_bleed(client, cookie):
    """Default/no-cookie + explicit horror + invalid cookie all -> horror arm.
    The Sea hybrid machinery must NOT bleed into the Horror landing.
    """
    if cookie is not None:
        client.cookies.set("theme", cookie)
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert '<html lang="en" class="theme-horror">' in html, html[:300]
    # Horror hybrid: backdrop present + active-theme preload to the horror map.
    assert 'class="nav-backdrop" aria-hidden="true"' in html
    assert f'href="{HORROR_IMG}"' in html, "Horror backdrop preload <link> missing"
    # No Sea ELEMENTS / Sea backdrop preload leak into the Horror arm.
    assert 'class="layer sea-landing"' not in html, "sea-landing leaked into Horror"
    assert f'href="{SEA_IMG}"' not in html, "sea webp preload leaked into Horror"
    assert "theme-sea" not in html
    # Retired raster-map markers are absent in Horror too.
    assert 'class="map-hotspot' not in html
    assert 'class="horror-map"' not in html
    assert 'class="sea-map"' not in html


def test_horror_landing_still_has_19_nav_nodes(client):
    """Horror keeps its own 19 nav-nodes (contract unbroken by M15)."""
    html = client.get("/").text  # no cookie -> horror
    hrefs = re.findall(r'<a\s+class="nav-node[^"]*"\s+href="(/level/\d+)"', html)
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


def test_api_levels_unchanged_by_m15(client):
    resp = client.get("/api/levels")
    assert resp.status_code == 200
    body = resp.json()
    available = sorted(lvl["id"] for lvl in body["levels"] if lvl["available"])
    assert available == AVAILABLE_IDS, available
    # /api/levels is JSON only — no map/nav markup or theme HTML bled into it.
    text = resp.text
    assert "nav-node" not in text and "nav-list" not in text
    assert "sea-map" not in text and "map-hotspot" not in text


# ===========================================================================
# 6. Map FILES still exist on disk (kept as the backdrop source), even though
#    they are no longer rendered as an <img src>.
# ===========================================================================
@pytest.mark.parametrize("rel", [SEA_IMG, HORROR_IMG])
def test_backdrop_map_files_exist_on_disk(rel):
    path = STATIC_DIR / rel[len("/static/"):]
    assert path.exists(), f"{path} (backdrop source) missing on disk"
    assert path.stat().st_size > 0, f"{path} is empty"


def test_calibrate_js_removed(client):
    """The retired calibrate-JS selector is GONE from both arms (M15)."""
    for cookie in (None, "sea"):
        if cookie:
            client.cookies.set("theme", cookie)
        else:
            client.cookies.clear()
        html = client.get("/").text
        assert 'document.querySelector(".horror-map, .sea-map")' not in html
        assert "?calibrate" not in html
