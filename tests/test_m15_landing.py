"""M15 — Hybrid responsive landing redesign regression suite (frontend-only).

Verifies the NEW landing contract of templates/index.html for BOTH theme arms
(ARCHITECTURE §15.7 / NF-M15-8). The Cloudinary Admin API stays mocked via the
shared ``client`` fixture in tests/conftest.py — hermetic, offline, passes
against placeholder assets. Mocked resource set -> available {1, 2, 8}; the rest
of 0..18 are sealed.

The hybrid landing renders navigation TWICE in the SSR HTML:
  * z-0 ``<div class="nav-backdrop" aria-hidden>`` — theme-conditional CSS
    background-image to the REUSED raster maps (kept on disk), + an active-theme
    ``<link rel=preload>`` warming the same map.
  * z-1 ``.atmosphere`` + scrim (decorative, aria-hidden).
  * z-2 ``.layer`` holding an inline ``<svg class="nav-map" viewBox="0 0 1600
    900" role="navigation">`` (decorative ``<g class="nav-scene" aria-hidden
    focusable="false">`` + 19 ``<a class="nav-node[ nav-node--sealed]">`` portal/
    isle glyphs instanced via ``<defs>``+``<use>``) AND a sibling
    ``<nav class="nav-list">`` ``<ul>`` of 19 ``<li class="nav-list-item[
    nav-list-item--sealed]"><a>``.
  * CSS-toggled at 768px (mobile-first: .nav-list default; .nav-map at >=768px).

Because BOTH representations are present in the served HTML (the 768px visibility
is CSS display:none, which TestClient cannot evaluate), counts are scoped PER
representation: 19 ``.nav-node`` + 19 ``.nav-list-item`` = 38 anchors per arm.
"""

from __future__ import annotations

import html as _html
import re
from pathlib import Path

import pytest

from app import main as main_module

BASE_DIR = Path(main_module.__file__).resolve().parent.parent
STYLE_CSS = BASE_DIR / "static" / "style.css"

ALL_IDS = list(range(19))
AVAILABLE_IDS = [1, 2, 8]
SEALED_IDS = [i for i in ALL_IDS if i not in AVAILABLE_IDS]

# Active-theme backdrop / preload map targets (KEPT on disk).
THEME_MAP = {
    "horror": "/static/img/horror/landing-map.v2.jpg",
    "sea": "/static/img/light/landing-map.v2.webp",
}
INACTIVE_MAP = {"horror": THEME_MAP["sea"], "sea": THEME_MAP["horror"]}

# Verbatim sealed wording per theme (NF-M15-8 hard gate).
SEALED_SUFFIX = {
    "horror": "(sealed — fallback content)",
    "sea": "(sunken — fallback content)",
}

SEA_NAMES = {
    0: "Ruin", 1: "Crypt", 2: "Witch's Hut", 3: "Mausoleum", 4: "Ruined Abbey",
    5: "Prison", 6: "Graveyard", 7: "Sealed", 8: "Sunken Temple", 9: "Forbidden",
    10: "Cavern", 11: "Sepulcher", 12: "Watch Tower", 13: "Pit", 14: "Final Keep",
    15: "Haunted Tower", 16: "Cursed Orchard", 17: "Dragon's Den",
    18: "Forgotten Armory",
}


def _html_for(client, theme: str) -> str:
    client.cookies.clear()
    if theme == "sea":
        client.cookies.set("theme", theme)
    resp = client.get("/")
    assert resp.status_code == 200, resp.status_code
    text = resp.text
    assert f'class="theme-{theme}' in text, theme
    return text


def _node_ids(html: str) -> list[int]:
    return sorted(
        int(h.rsplit("/", 1)[-1])
        for h in re.findall(r'<a\s+class="nav-node[^"]*"\s+href="(/level/\d+)"', html)
    )


def _list_ids(html: str) -> list[int]:
    return sorted(
        int(m.group(1))
        for m in re.finditer(
            r'<li\s+class="nav-list-item[^"]*">\s*<a\s+href="/level/(\d+)"', html
        )
    )


def _node_aria(html: str, level_id: int) -> tuple[str, str]:
    """Return (class, aria-label) of the SVG .nav-node <a> for a level."""
    m = re.search(
        r'<a\s+class="(nav-node[^"]*)"\s+href="/level/%d"\s+aria-label="([^"]*)"'
        % level_id,
        html,
    )
    assert m is not None, f"no nav-node anchor for level {level_id}"
    return m.group(1), _html.unescape(m.group(2))


def _list_aria(html: str, level_id: int) -> tuple[str, str]:
    """Return (li-class, aria-label) of the .nav-list-item <a> for a level."""
    m = re.search(
        r'<li\s+class="(nav-list-item[^"]*)">\s*<a\s+href="/level/%d"\s+aria-label="([^"]*)"'
        % level_id,
        html,
    )
    assert m is not None, f"no nav-list-item anchor for level {level_id}"
    return m.group(1), _html.unescape(m.group(2))


# ===========================================================================
# 1. Both representations render 19 anchors (ids 0..18) per theme.
# ===========================================================================
@pytest.mark.parametrize("theme", ["horror", "sea"])
def test_both_representations_render_19_anchors(client, theme):
    html = _html_for(client, theme)
    assert _node_ids(html) == ALL_IDS, "SVG nav-node ids != 0..18"
    assert _list_ids(html) == ALL_IDS, "nav-list-item ids != 0..18"
    # 19 of each family = 38 total per arm in the served HTML.
    assert len(re.findall(r'<a\s+class="nav-node[^"]*"\s+href="/level/\d+"', html)) == 19
    assert len(re.findall(r'<li\s+class="nav-list-item[^"]*">', html)) == 19


# ===========================================================================
# 2. .nav-backdrop present + aria-hidden; theme-conditional preload <link>.
# ===========================================================================
@pytest.mark.parametrize("theme", ["horror", "sea"])
def test_nav_backdrop_present_and_aria_hidden(client, theme):
    html = _html_for(client, theme)
    assert 'class="nav-backdrop" aria-hidden="true"' in html


@pytest.mark.parametrize("theme", ["horror", "sea"])
def test_active_theme_backdrop_preload_link(client, theme):
    html = _html_for(client, theme)
    active = THEME_MAP[theme]
    inactive = INACTIVE_MAP[theme]
    # Exactly the active-theme map is preloaded, same-origin /static/...
    m = re.search(r'<link rel="preload"[^>]*href="([^"]+)"[^>]*/?>', html)
    assert m is not None, "no preload <link> on landing"
    assert m.group(1) == active, f"{theme}: preload -> {m.group(1)!r}, want {active!r}"
    assert active.startswith("/static/"), "backdrop preload must be same-origin"
    assert f'href="{active}"' in html
    assert f'href="{inactive}"' not in html, f"inactive map {inactive} preloaded"


def test_backdrop_is_theme_conditional(client):
    """Horror and Sea arms preload DIFFERENT maps (theme-conditional backdrop)."""
    horror = _html_for(client, "horror")
    sea = _html_for(client, "sea")
    assert THEME_MAP["horror"] in horror and THEME_MAP["sea"] not in horror
    assert THEME_MAP["sea"] in sea and THEME_MAP["horror"] not in sea


# ===========================================================================
# 3. .nav-map is an <svg viewBox role=navigation>; scene inert; glyphs use <use>.
# ===========================================================================
@pytest.mark.parametrize("theme", ["horror", "sea"])
def test_nav_map_is_svg_navigation(client, theme):
    html = _html_for(client, theme)
    assert re.search(
        r'<svg class="nav-map" viewBox="0 0 1600 900" preserveAspectRatio="xMidYMid meet"\s+'
        r'role="navigation"',
        html,
    ), f"{theme}: .nav-map is not the expected <svg ... role=navigation>"


@pytest.mark.parametrize("theme", ["horror", "sea"])
def test_nav_scene_is_inert(client, theme):
    html = _html_for(client, theme)
    assert 'class="nav-scene" aria-hidden="true" focusable="false"' in html, (
        f"{theme}: .nav-scene must be aria-hidden + focusable=false"
    )


@pytest.mark.parametrize(
    "theme,use_ref", [("horror", "#h-portal-glyph"), ("sea", "#s-isle-base")]
)
def test_node_glyphs_use_defs_instances(client, theme, use_ref):
    html = _html_for(client, theme)
    # The reusable glyph is defined once in <defs> and instanced via <use>.
    assert f'id="{use_ref[1:]}"' in html, f"{theme}: glyph def {use_ref} missing"
    assert html.count(f'<use href="{use_ref}"') == 19, (
        f"{theme}: expected 19 <use href={use_ref}> instances"
    )


# ===========================================================================
# 4. a11y / inert: decorative layers aria-hidden + focusable=false; no tabindex;
#    the 19 nav-node <a>s are the focusable items (have href).
# ===========================================================================
@pytest.mark.parametrize("theme", ["horror", "sea"])
def test_decorative_layers_aria_hidden(client, theme):
    html = _html_for(client, theme)
    assert 'class="nav-backdrop" aria-hidden="true"' in html
    assert 'class="atmosphere" aria-hidden="true"' in html
    assert 'class="nav-scene" aria-hidden="true" focusable="false"' in html
    assert 'class="nav-list-banner" aria-hidden="true"' in html


@pytest.mark.parametrize("theme", ["horror", "sea"])
def test_no_tabindex_anywhere_on_landing(client, theme):
    html = _html_for(client, theme)
    assert "tabindex" not in html, f"{theme}: tabindex must not appear on landing"


@pytest.mark.parametrize("theme", ["horror", "sea"])
def test_every_decorative_svg_is_focusable_false(client, theme):
    html = _html_for(client, theme)
    # Strip HTML comments first — the template's prose comments mention an inline
    # "<svg viewBox=\"0 0 1600 900\">" that is NOT a real element.
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    # The ONE interactive svg is .nav-map (role=navigation, holds the <a>s); it
    # carries no focusable="false". Every OTHER <svg> in the page is decorative
    # and must opt out of focus.
    svg_opens = re.findall(r"<svg\b[^>]*>", html)
    decorative = [s for s in svg_opens if 'class="nav-map"' not in s]
    assert decorative, f"{theme}: expected decorative SVGs"
    for s in decorative:
        assert 'focusable="false"' in s, f"{theme}: decorative <svg> not focusable=false: {s[:80]}"


@pytest.mark.parametrize("theme", ["horror", "sea"])
def test_nav_nodes_are_the_focusable_links(client, theme):
    html = _html_for(client, theme)
    # Every nav-node <a> has an href (focusable); count matches 0..18.
    for i in ALL_IDS:
        assert f'href="/level/{i}"' in html, f"{theme}: missing href for level {i}"


# ===========================================================================
# 5. available-vs-sealed parity across BOTH representations + aria-label parity.
# ===========================================================================
@pytest.mark.parametrize("theme", ["horror", "sea"])
def test_sealed_set_marks_both_representations(client, theme):
    html = _html_for(client, theme)
    for i in ALL_IDS:
        node_cls, _ = _node_aria(html, i)
        list_cls, _ = _list_aria(html, i)
        if i in AVAILABLE_IDS:
            assert "nav-node--sealed" not in node_cls, f"{theme} L{i} node wrongly sealed"
            assert "nav-list-item--sealed" not in list_cls, f"{theme} L{i} list wrongly sealed"
        else:
            assert "nav-node--sealed" in node_cls, f"{theme} L{i} node not sealed"
            assert "nav-list-item--sealed" in list_cls, f"{theme} L{i} list not sealed"


@pytest.mark.parametrize("theme", ["horror", "sea"])
def test_sealed_wording_verbatim_per_theme(client, theme):
    html = _html_for(client, theme)
    suffix = SEALED_SUFFIX[theme]
    # Sealed suffix appears once per sealed level in EACH family -> 2x.
    assert html.count(suffix) == len(SEALED_IDS) * 2, (
        f"{theme}: {html.count(suffix)} '{suffix}' vs {len(SEALED_IDS) * 2}"
    )
    # The opposite theme's wording never appears.
    other = SEALED_SUFFIX["sea" if theme == "horror" else "horror"]
    assert other not in html, f"{theme}: leaked other-theme sealed wording {other!r}"


@pytest.mark.parametrize("theme", ["horror", "sea"])
def test_aria_label_byte_identical_node_vs_list(client, theme):
    """Per level, the SVG nav-node aria-label is byte-identical to the list row's."""
    html = _html_for(client, theme)
    for i in ALL_IDS:
        _, node_label = _node_aria(html, i)
        _, list_label = _list_aria(html, i)
        assert node_label == list_label, (
            f"{theme} L{i}: node aria={node_label!r} != list aria={list_label!r}"
        )


def test_sea_aria_labels_carry_island_names(client):
    """sea_names survive into the Sea aria-labels (e.g. Level 5 — Prison)."""
    html = _html_for(client, "sea")
    # Available example.
    _, lbl1 = _node_aria(html, 1)
    assert lbl1 == f"Level 1 — {SEA_NAMES[1]}"
    # Sealed example named in REQUIREMENTS.
    _, lbl5 = _node_aria(html, 5)
    assert lbl5 == f"Level 5 — Prison {SEALED_SUFFIX['sea']}"


def test_horror_aria_labels_are_level_n(client):
    html = _html_for(client, "horror")
    _, lbl1 = _node_aria(html, 1)
    assert lbl1 == "Level 1"
    _, lbl5 = _node_aria(html, 5)
    assert lbl5 == f"Level 5 {SEALED_SUFFIX['horror']}"


# ===========================================================================
# 6. Retired M9/M10 markers are GONE from both arms.
# ===========================================================================
@pytest.mark.parametrize("theme", ["horror", "sea"])
def test_retired_markers_absent(client, theme):
    html = _html_for(client, theme)
    assert 'class="map-hotspot' not in html, "retired .map-hotspot present"
    assert 'class="horror-map"' not in html, 'retired class="horror-map" present'
    assert 'class="sea-map"' not in html, 'retired class="sea-map" present'
    assert 'class="sea-map-hotspots"' not in html
    assert "?calibrate" not in html, "retired ?calibrate present"
    assert 'document.querySelector(".horror-map, .sea-map")' not in html
    assert "landing-map" not in re.sub(
        r'<link[^>]*>', "", html
    ), "landing-map referenced in HTML outside the preload <link> (stray <img>?)"


# ===========================================================================
# 7. style.css?v=8 on / AND /level/{id}.
# ===========================================================================
@pytest.mark.parametrize("path", ["/", "/level/1", "/level/3"])
def test_style_css_v8(client, path):
    html = client.get(path).text
    assert '<link rel="stylesheet" href="/static/style.css?v=8" />' in html, (
        f"expected style.css?v=8 on {path}"
    )


# ===========================================================================
# 8. Theme toggle, brand logo, sr-only h1 still present (both arms).
# ===========================================================================
@pytest.mark.parametrize("theme", ["horror", "sea"])
def test_toggle_brand_and_heading_present(client, theme):
    html = _html_for(client, theme)
    assert 'id="theme-toggle"' in html
    assert 'aria-label="Toggle between Horror and Sea themes"' in html
    assert 'class="brand-logo"' in html
    if theme == "sea":
        assert '<h1 class="sr-only">Tour-de-Anshika — choose an island</h1>' in html
        assert "Enter the Corridor" in html
    else:
        assert '<h1 class="sr-only">Tour-de-Anshika — choose a destination</h1>' in html
        assert "Sail to the Sea" in html


# ===========================================================================
# 9. Responsive: BOTH .nav-map and .nav-list in served HTML; the 768px CSS
#    boundary + mobile-first defaults exist in static/style.css (SSR can't
#    evaluate display:none, so we read the stylesheet for the toggle rule).
# ===========================================================================
@pytest.mark.parametrize("theme", ["horror", "sea"])
def test_both_nav_map_and_nav_list_in_html(client, theme):
    html = _html_for(client, theme)
    assert 'class="nav-map"' in html
    assert 'class="nav-list"' in html


def test_css_has_mobile_first_defaults_and_768_toggle():
    css = STYLE_CSS.read_text(encoding="utf-8")
    # Mobile-first default: .nav-map hidden (list shown) at the phone default.
    m = re.search(r"\.nav-map\s*\{([^}]*)\}", css)
    assert m is not None, ".nav-map rule missing in style.css"
    assert re.search(r"display:\s*none", m.group(1)), (
        "mobile-first default: .nav-map should be display:none by default"
    )
    nl = re.search(r"\.nav-list\s*\{([^}]*)\}", css)
    assert nl is not None and re.search(r"display:\s*block", nl.group(1)), (
        "mobile-first default: .nav-list should be display:block by default"
    )
    # The single map<->list boundary at min-width:768px.
    media = re.search(
        r"@media\s*\(min-width:\s*768px\)\s*\{(.*?)\n\}", css, re.DOTALL
    )
    assert media is not None, "no @media (min-width: 768px) toggle block in style.css"
    body = media.group(1)
    assert re.search(r"\.nav-map\s*\{\s*display:\s*block", body), (
        ">=768px must show the .nav-map"
    )
    assert ".nav-list" in body and "display: none" in body, (
        ">=768px must hide the .nav-list"
    )
