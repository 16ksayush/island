"""M14 — Dynamic, atmospheric individual level/island pages (frontend-only).

Regression suite for the M14 redesign of ``/level/{id}`` for BOTH themes and
BOTH states (available slideshow + sealed "Chudail-not-found" fallback). The
image source is Cloudinary (M13); its Admin API is mocked via the shared
``client`` fixture in tests/conftest.py — the suite is hermetic and offline.

What M14 added to templates/level.html (all decorative, all inside the
aria-hidden ``.atmosphere`` overlay or as inert children of ``.level-stage``):
  * Themed CSS environment bands — Horror: ``.level-env-wall`` + ``.level-env-floor``;
    Sea: ``.level-env-sky`` + ``.level-env-sea`` + ``.level-env-sand``.
  * A NEW ``.sea-scene`` inline SVG (the Sea level page previously had an EMPTY
    ``.atmosphere``) — the structural twin of the M9 ``.horror-scene``.
  * A ``.level-ambient`` decor wrapper reusing the landing decor spans/SVGs,
    scoped under ``.level-ambient`` only (never the landing's *-ambient rules).
  * A CSS/SVG photo frame: four ``.frame-corner`` SVGs on ``.level-stage``.
  * A restyled fallback note: ``.level-note`` (retaining the verbatim hard-gate
    substring "salvaged fallback content").
  * ``style.css?v=6`` -> ``?v=7`` on BOTH templates/level.html and index.html.

Theme isolation is the critical guard: the Sea scene must NOT leak into Horror
and the Horror scene must NOT leak into Sea, on the level page exactly as the
M9 landing guard already enforces.
"""

from __future__ import annotations

import re

import pytest

# Mocked discovery (conftest): available levels {1, 2, 8}, span 0..8, missing
# pool populated. So /level/1 is AVAILABLE and /level/3 is MISSING.
AVAILABLE_LEVEL = 1
MISSING_LEVEL = 3

# M14 markers.
SEA_SCENE_MARKERS = [
    'class="sea-scene"',
    "sea-silhouette--sun",
    "sea-silhouette--palm",
    "sea-silhouette--wave-left",
    "sea-silhouette--wave-right",
]
HORROR_SCENE_MARKERS = [
    'class="horror-scene"',
    "horror-silhouette--doorway",
    "horror-silhouette--figure",
    "horror-silhouette--claw-left",
    "horror-silhouette--claw-right",
]
SEA_ENV_BANDS = ["level-env-sky", "level-env-sea", "level-env-sand"]
HORROR_ENV_BANDS = ["level-env-wall", "level-env-floor"]
FRAME_CORNERS = [
    "frame-corner--tl",
    "frame-corner--tr",
    "frame-corner--bl",
    "frame-corner--br",
]


def _set_theme(client, theme: str | None):
    client.cookies.clear()
    if theme is not None:
        client.cookies.set("theme", theme)


def _atmosphere_block(html: str) -> str:
    """Extract the aria-hidden ``.atmosphere`` overlay block (z-0 decor layer).

    Mirrors the slice in tests/test_horror_atmosphere.py: the atmosphere div is
    the first block in <body>; the .layer div follows it.
    """
    start = html.index('<div class="atmosphere"')
    end = html.index('<div class="layer', start)
    return html[start:end]


def _level_stage_block(html: str) -> str:
    """Extract the <main class="level-stage ...> ... </main> block (frame host)."""
    start = html.index('class="level-stage')
    start = html.rindex("<", 0, start)  # back up to the opening tag
    end = html.index("</main>", start)
    return html[start:end]


# ===========================================================================
# 1. Sea scene NEW on the level page; theme-isolated from Horror.
# ===========================================================================
def test_sea_level_page_renders_new_sea_scene(client):
    """The Sea level page now fills its previously-EMPTY .atmosphere with the
    new .sea-scene inline SVG (sun glow, palm/island, foam waves)."""
    _set_theme(client, "sea")
    html = client.get(f"/level/{AVAILABLE_LEVEL}").text
    assert 'class="theme-sea' in html
    block = _atmosphere_block(html)
    for marker in SEA_SCENE_MARKERS:
        assert marker in block, f"{marker!r} missing in Sea level atmosphere"
    # Horror scene must NOT appear under Sea.
    for marker in HORROR_SCENE_MARKERS:
        assert marker not in html, f"{marker!r} leaked into Sea level page"


def test_horror_level_page_keeps_horror_scene_and_omits_sea_scene(client):
    """The Horror level page still renders the M9 .horror-scene (contract) and
    must NOT render the new .sea-scene."""
    _set_theme(client, None)  # default -> horror
    html = client.get(f"/level/{AVAILABLE_LEVEL}").text
    assert 'class="theme-horror">' in html
    block = _atmosphere_block(html)
    for marker in HORROR_SCENE_MARKERS:
        assert marker in block, f"{marker!r} missing in Horror level atmosphere"
    for marker in SEA_SCENE_MARKERS:
        assert marker not in html, f"{marker!r} leaked into Horror level page"


# ===========================================================================
# 2. Environment bands + .level-ambient decor wrapper per theme.
# ===========================================================================
def test_sea_level_renders_env_bands_and_ambient(client):
    _set_theme(client, "sea")
    block = _atmosphere_block(client.get(f"/level/{AVAILABLE_LEVEL}").text)
    for band in SEA_ENV_BANDS:
        assert band in block, f"sea env band {band!r} missing on level page"
    assert 'class="level-ambient"' in block, "Sea .level-ambient wrapper missing"
    # Horror bands must not bleed into Sea.
    for band in HORROR_ENV_BANDS:
        assert band not in block, f"horror env band {band!r} leaked into Sea"


def test_horror_level_renders_env_bands_and_ambient(client):
    _set_theme(client, None)
    block = _atmosphere_block(client.get(f"/level/{AVAILABLE_LEVEL}").text)
    for band in HORROR_ENV_BANDS:
        assert band in block, f"horror env band {band!r} missing on level page"
    assert 'class="level-ambient"' in block, "Horror .level-ambient wrapper missing"
    for band in SEA_ENV_BANDS:
        assert band not in block, f"sea env band {band!r} leaked into Horror"


# ===========================================================================
# 3. .frame-corner photo frame on .level-stage, both themes.
# ===========================================================================
@pytest.mark.parametrize("theme", ["sea", "horror"])
def test_level_stage_has_four_frame_corners(client, theme):
    _set_theme(client, None if theme == "horror" else theme)
    stage = _level_stage_block(client.get(f"/level/{AVAILABLE_LEVEL}").text)
    for corner in FRAME_CORNERS:
        assert corner in stage, f"{corner!r} missing on .level-stage ({theme})"
    # The frame must not displace the slideshow it wraps.
    assert 'id="slideshow"' in stage, f"slideshow missing from stage ({theme})"


# ===========================================================================
# 4. Both STATES get the M14 treatment (available + missing), both themes.
#    The missing page still carries the verbatim fallback gate AND .level-note.
# ===========================================================================
@pytest.mark.parametrize("theme", ["sea", "horror"])
@pytest.mark.parametrize("level_id", [AVAILABLE_LEVEL, MISSING_LEVEL])
def test_both_states_render_environment_and_frame(client, theme, level_id):
    _set_theme(client, None if theme == "horror" else theme)
    html = client.get(f"/level/{level_id}").text
    assert html.startswith("<!"), "not a rendered page"
    atmosphere = _atmosphere_block(html)
    stage = _level_stage_block(html)
    bands = SEA_ENV_BANDS if theme == "sea" else HORROR_ENV_BANDS
    scene = SEA_SCENE_MARKERS if theme == "sea" else HORROR_SCENE_MARKERS
    for band in bands:
        assert band in atmosphere, f"{band!r} missing ({theme} level {level_id})"
    assert scene[0] in atmosphere, f"scene missing ({theme} level {level_id})"
    assert 'class="level-ambient"' in atmosphere
    for corner in FRAME_CORNERS:
        assert corner in stage, f"{corner!r} missing ({theme} level {level_id})"


@pytest.mark.parametrize("theme", ["sea", "horror"])
def test_missing_level_keeps_fallback_gate_and_level_note_skin(client, theme):
    _set_theme(client, None if theme == "horror" else theme)
    html = client.get(f"/level/{MISSING_LEVEL}").text
    assert f"var ssrAvailable = false;" in html
    # Hard gate NF-M14-7: the verbatim substring must be retained.
    assert "salvaged fallback content" in html, f"fallback gate dropped ({theme})"
    # The M14 restyle wraps the note in .level-note (diegetic plaque/signpost).
    assert 'class="level-note"' in html, f".level-note skin missing ({theme})"


@pytest.mark.parametrize("theme", ["sea", "horror"])
def test_available_level_has_no_fallback_note(client, theme):
    _set_theme(client, None if theme == "horror" else theme)
    html = client.get(f"/level/{AVAILABLE_LEVEL}").text
    assert "var ssrAvailable = true;" in html
    assert "salvaged fallback content" not in html
    assert 'class="level-note"' not in html


# ===========================================================================
# 5. a11y / contract guard — the new decor is inert (NF-M14: aria-hidden,
#    focusable="false", no tabindex, no interactive elements).
# ===========================================================================
@pytest.mark.parametrize("theme", ["sea", "horror"])
@pytest.mark.parametrize("level_id", [AVAILABLE_LEVEL, MISSING_LEVEL])
def test_atmosphere_decor_is_inert(client, theme, level_id):
    _set_theme(client, None if theme == "horror" else theme)
    block = _atmosphere_block(client.get(f"/level/{level_id}").text)
    # Wrapper + scene + ambient are aria-hidden.
    assert 'class="atmosphere" aria-hidden="true"' in block
    scene_cls = "sea-scene" if theme == "sea" else "horror-scene"
    assert f'class="{scene_cls}" aria-hidden="true"' in block
    assert 'class="level-ambient" aria-hidden="true"' in block
    # No interactive elements / no focus traps inside the decor layer.
    for tag in ("<a", "<button", "<input", "<select", "<textarea", "href=", "onclick"):
        assert tag not in block, f"interactive {tag!r} in atmosphere ({theme})"
    assert "tabindex" not in block, f"tabindex in atmosphere ({theme})"
    # Every SVG in the decor opts out of focus.
    svg_opens = block.count("<svg")
    focusable_false = block.count('focusable="false"')
    assert svg_opens >= 1, f"no decorative SVG in atmosphere ({theme})"
    assert focusable_false >= svg_opens, (
        f"{svg_opens} <svg> but only {focusable_false} focusable=\"false\" "
        f"({theme} level {level_id})"
    )


@pytest.mark.parametrize("theme", ["sea", "horror"])
def test_frame_corners_are_inert(client, theme):
    """The four .frame-corner SVGs on .level-stage are decorative: aria-hidden,
    focusable="false", no interactivity."""
    _set_theme(client, None if theme == "horror" else theme)
    stage = _level_stage_block(client.get(f"/level/{AVAILABLE_LEVEL}").text)
    # Isolate just the frame-corner SVGs (everything before #slideshow).
    frame_region = stage[: stage.index('id="slideshow"')]
    assert frame_region.count("frame-corner") >= 4, f"<4 frame corners ({theme})"
    for corner_svg in re.findall(r"<svg[^>]*frame-corner[^>]*>", frame_region):
        assert 'aria-hidden="true"' in corner_svg, f"frame corner not aria-hidden ({theme})"
        assert 'focusable="false"' in corner_svg, f"frame corner focusable ({theme})"
    assert "tabindex" not in frame_region, f"tabindex in frame region ({theme})"


# ===========================================================================
# 6. Cache-bust: style.css?v=8 on BOTH the level page and the index page.
#    MIGRATED (M15): the hybrid landing redesign bumped ?v=7 -> ?v=8 on BOTH
#    templates/index.html AND templates/level.html (ARCHITECTURE §15.7). The
#    level-page contract is otherwise unchanged by M15.
# ===========================================================================
@pytest.mark.parametrize("path", ["/", f"/level/{AVAILABLE_LEVEL}"])
def test_style_css_is_v8_on_level_and_index(client, path):
    html = client.get(path).text
    assert '<link rel="stylesheet" href="/static/style.css?v=8" />' in html, (
        f"expected style.css?v=8 on {path}; M15 bumped ?v=7 -> ?v=8"
    )
