"""M9 — Horror Atmosphere Redesign regression suite (H7).

Verifies the frontend-only visual restyle of the HORROR theme against the
acceptance criteria in docs/PLAN.md (M9) and docs/REQUIREMENTS.md §9
(HR1-HR8, NF-HR1-NF-HR6). Drive stays mocked via tests/conftest.py — hermetic
and offline.

Critical guards:
  * Theme isolation (NF-HR4): horror renders the decorative scene; Sea does NOT.
  * Decorative layer inert/accessible (HR5, NF-HR2): aria-hidden, no interactive
    elements, pointer-events:none.
  * Door grid + functionality unchanged (HR3, NF-HR5).
  * Reduced-motion gating present (R-H3, NF-HR2).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import main as main_module

BASE_DIR = Path(main_module.__file__).resolve().parent.parent
STYLE_CSS = BASE_DIR / "static" / "style.css"

# Decorative markers injected by the M9 redesign (templates/*.html).
HORROR_SCENE_MARKERS = [
    'class="horror-scene"',
    "horror-silhouette--doorway",
    "horror-silhouette--figure",
    "horror-silhouette--claw-left",
    "horror-silhouette--claw-right",
]


# ===========================================================================
# 2. Theme isolation (critical) — Horror renders the scene; Sea does NOT.
# ===========================================================================
@pytest.mark.parametrize("path", ["/", "/level/1", "/level/3", "/level/8"])
def test_horror_renders_decorative_scene(client, path):
    """Default/no-cookie horror theme must contain the full decorative scene."""
    html = client.get(path).text
    assert 'class="theme-horror">' in html, path
    for marker in HORROR_SCENE_MARKERS:
        assert marker in html, f"{marker!r} missing on {path} (horror)"


@pytest.mark.parametrize("path", ["/", "/level/1", "/level/3", "/level/8"])
def test_sea_omits_decorative_scene(client, path):
    """The {% if theme != 'sea' %} gate must strip ALL horror decoration.

    This is the key regression guard: Sea must be visually unaffected.
    """
    client.cookies.set("theme", "sea")
    html = client.get(path).text
    assert 'class="theme-sea' in html, path
    for marker in HORROR_SCENE_MARKERS:
        assert marker not in html, f"{marker!r} leaked into Sea on {path}"
    # The SVG <path>/<radialGradient> decoration must be gone too.
    assert "<radialGradient" not in html, f"SVG defs leaked into Sea on {path}"


def test_sea_atmosphere_div_present_but_empty(client):
    """Sea still has the .atmosphere overlay (shared vignette) but no scene."""
    client.cookies.set("theme", "sea")
    html = client.get("/").text
    assert 'class="atmosphere" aria-hidden="true"' in html
    # Between the atmosphere open tag and its close, no horror-scene div.
    assert "horror-scene" not in html


# ===========================================================================
# 3. Decorative layer inert / accessible (HR5, NF-HR2).
# ===========================================================================
def _atmosphere_block(html: str) -> str:
    """Extract the <div class="atmosphere" ...> ... </div> outer block."""
    start = html.index('<div class="atmosphere"')
    # The atmosphere div is the first block in <body>; the .layer div follows.
    end = html.index('<div class="layer', start)
    return html[start:end]


@pytest.mark.parametrize("path", ["/", "/level/1", "/level/8"])
def test_atmosphere_block_is_aria_hidden(client, path):
    html = client.get(path).text
    block = _atmosphere_block(html)
    # Both the atmosphere wrapper and the inner horror-scene are aria-hidden.
    assert 'class="atmosphere" aria-hidden="true"' in html, path
    assert 'class="horror-scene" aria-hidden="true"' in block, path


@pytest.mark.parametrize("path", ["/", "/level/1", "/level/8"])
def test_decorative_layer_has_no_interactive_elements(client, path):
    """No focusable/clickable controls inside the decorative atmosphere block.

    Screen-reader / keyboard users must be unaffected; the door grid (in .layer)
    stays the only interactive surface.
    """
    block = _atmosphere_block(client.get(path).text)
    for tag in ("<a", "<button", "<input", "<select", "<textarea", "href=", "onclick"):
        assert tag not in block, f"interactive {tag!r} found in atmosphere on {path}"
    # SVGs explicitly opt out of focus.
    assert block.count("focusable=\"false\"") >= 4, path
    # No positive tabindex sneaking in.
    assert "tabindex" not in block, path


# ===========================================================================
# 4. Horror landing nav + functionality intact (HR3, NF-HR5).
#    (Belt-and-braces alongside test_frontend.py — proves the redesign did not
#     alter the hotspot/toggle/slideshow contract.)
# ===========================================================================
def test_grid_tile_markup_contract_unchanged(client):
    # Superseded by the M9 map redesign: the door GRID (`class="level-tile"` +
    # `badge-unavailable` "Lost" badge) is gone, replaced by 19 `.map-hotspot`
    # anchors. Converted to assert the equivalent Horror-map availability
    # contract so the invariant (available 1/2/8 vs sealed rest) keeps coverage.
    html = client.get("/").text
    # Available hotspots keep the bare `class="map-hotspot" href="/level/{id}"`.
    available_hotspots = re.findall(
        r'<a\s+class="map-hotspot"\s+href="/level/(\d+)"', html
    )
    assert sorted(int(x) for x in available_hotspots) == [1, 2, 8]
    # Sealed hotspots carry is-sealed + the "(sealed — fallback content)" label.
    assert html.count("(sealed — fallback content)") == 16  # levels 0,3-7,9-18


def test_toggle_and_slideshow_js_intact(client):
    idx = client.get("/").text
    assert 'id="theme-toggle"' in idx
    lvl = client.get("/level/1").text
    assert 'id="slideshow"' in lvl
    assert 'fetch("/api/levels/" + levelId + "/photos"' in lvl
    assert 'id="theme-toggle"' in lvl


def test_horror_scene_sits_outside_the_layer(client):
    """The decorative scene must live in .atmosphere (z-0), NOT in .layer (z-1)."""
    html = client.get("/").text
    atmosphere = _atmosphere_block(html)
    assert "horror-scene" in atmosphere
    layer = html[html.index('<div class="layer'):]
    assert "horror-scene" not in layer


# ===========================================================================
# 5. Reduced-motion gating present (R-H3, NF-HR2) — scan style.css.
# ===========================================================================
def test_reduced_motion_block_neutralizes_m9_animations():
    css = STYLE_CSS.read_text(encoding="utf-8")
    # Find every prefers-reduced-motion media block.
    blocks = re.findall(
        r"@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{(.*?)\n\}",
        css,
        re.DOTALL,
    )
    assert blocks, "no prefers-reduced-motion block found in style.css"
    joined = "\n".join(blocks)
    # An explicit horror-scoped fallback (not just the global kill-switch).
    horror_block = next(
        (b for b in blocks if ".theme-horror" in b), None
    )
    assert horror_block is not None, (
        "no horror-scoped prefers-reduced-motion fallback (R-H3 wants an "
        "explicit static frame, not only the global kill-switch)"
    )
    # The fog + glow animations are explicitly neutralized.
    assert "animation: none" in horror_block.replace("animation:none", "animation: none")
    assert ".atmosphere::before" in horror_block
    assert "horror-silhouette--doorway" in horror_block


def test_fog_and_glow_animations_are_defined():
    """Sanity: the M9 motion the reduced-motion block neutralizes actually exists."""
    css = STYLE_CSS.read_text(encoding="utf-8")
    for kf in ("hr-fog-a", "hr-fog-b", "hr-glow-flicker"):
        assert f"@keyframes {kf}" in css, f"missing keyframes {kf}"


# ===========================================================================
# 6. WCAG AA contrast (R-H2 / HR6 / NF-HR2).
# ===========================================================================
def _lin(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _lum(hexc: str) -> float:
    hexc = hexc.lstrip("#")
    r, g, b = (int(hexc[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _contrast(fg: str, bg: str) -> float:
    l1, l2 = _lum(fg), _lum(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def _horror_token_block() -> str:
    """Return the body of the `.theme-horror { ... }` token-declaration block.

    Mirrors the slicing in test_navy_tokens_are_horror_scoped: the token block
    is the first `.theme-horror` selector, ending where the Sea block begins.
    """
    css = STYLE_CSS.read_text(encoding="utf-8")
    # Anchor on the actual selector `.theme-horror {` (the string ".theme-horror"
    # also appears in the file header comment, which would slice in :root's
    # neutral defaults). The token block ends at its closing brace.
    start = css.index(".theme-horror {")
    end = css.index("}", start)
    return css[start:end]


def _horror_token(name: str) -> str:
    """Parse a `--name: #hex;` custom-property value from the .theme-horror block.

    Reads the ACTUAL CSS token so these guards track the real stylesheet rather
    than a frozen literal copy.
    """
    block = _horror_token_block()
    m = re.search(rf"{re.escape(name)}:\s*(#[0-9a-fA-F]{{3,8}})\s*;", block)
    assert m is not None, f"{name} not found in .theme-horror token block"
    return m.group(1)


# --bg is parsed from the real .theme-horror token (darkest field behind text).
HORROR_BG = _horror_token("--bg")


def test_horror_bg_token_is_navy():
    # Sanity-pin the parsed background so the contrast guards below are anchored
    # to the documented field; if --bg moves, this surfaces it explicitly.
    assert HORROR_BG.lower() == "#0a0e1a"


def test_fg_meets_aa_normal_text():
    fg = _horror_token("--fg")
    assert _contrast(fg, HORROR_BG) >= 4.5, f"--fg {fg} vs {HORROR_BG}"


def test_muted_meets_aa_normal_text():
    # --muted was bumped lighter specifically for AA (R-H2).
    muted = _horror_token("--muted")
    assert _contrast(muted, HORROR_BG) >= 4.5, f"--muted {muted} vs {HORROR_BG}"


def test_accent_meets_aa_large_text():
    # --accent amber drives big level numbers (large text -> >=3:1).
    accent = _horror_token("--accent")
    assert _contrast(accent, HORROR_BG) >= 3.0, f"--accent {accent} vs {HORROR_BG}"


def test_unavailable_fg_meets_aa_normal_text():
    """The horror --unavailable-fg styles the 'Sealed' label (0.75rem normal)
    and the 'Lost' badge (0.6rem), so AA requires >=4.5:1 over --bg.

    Parses the LIVE token (frontend-engineer's fix: #9a907b ~= 6.09:1). This is
    now a real passing guard — it will fail if anyone regresses the token.
    """
    fg = _horror_token("--unavailable-fg")
    ratio = _contrast(fg, HORROR_BG)
    assert ratio >= 4.5, f"--unavailable-fg {fg} vs {HORROR_BG} = {ratio:.2f}:1"


def test_unavailable_label_is_not_dimmed_by_subunit_opacity():
    """Legibility fix (R-H2/HR6): horror must lift the shared `.is-unavailable`
    `opacity: 0.75` whole-tile dim so the label renders at the token's full
    contrast (a child opacity can't exceed a 0.75 parent, dropping AA).
    """
    css = STYLE_CSS.read_text(encoding="utf-8")
    m = re.search(
        r"\.theme-horror\s+\.level-tile\.is-unavailable\s*\{([^}]*)\}", css
    )
    assert m is not None, "no horror-scoped .level-tile.is-unavailable rule"
    body = m.group(1)
    assert re.search(r"opacity:\s*1\b", body), (
        "horror .is-unavailable must reset opacity to 1 so the label is not "
        f"sub-unit dimmed; got: {body.strip()!r}"
    )


# ===========================================================================
# 7. Theme-isolation at the CSS-token level (NF-HR4) — no Sea bleed.
# ===========================================================================
def test_navy_tokens_are_horror_scoped():
    css = STYLE_CSS.read_text(encoding="utf-8")
    # The new navy bg lives under .theme-horror, not in :root (would bleed).
    root_block = css[css.index(":root"): css.index(".theme-horror")]
    assert "#0a0e1a" not in root_block, "navy --bg leaked into :root (would hit Sea)"
    # The navy --bg token must appear under a .theme-horror selector before the
    # Sea block (token override is horror-scoped, not a shared neutral).
    horror_token_block = css[css.index(".theme-horror"): css.index(".theme-sea {")]
    assert "--bg: #0a0e1a;" in horror_token_block, (
        "navy --bg not horror-scoped"
    )
