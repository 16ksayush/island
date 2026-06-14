"""M16 — Chest-chooser GATEWAY regression suite (NF-M16-8, the de-risking deliverable).

Verifies the NEW theme-neutral SSR gateway at ``/`` (templates/gateway.html) and
the two relocated, theme-FORCED map subpages (``/map/horror`` + ``/map/sea``)
introduced by the M16 change request (docs/ARCHITECTURE.md §17, REQUIREMENTS §17).
The Cloudinary Admin API stays mocked via the shared ``client`` fixture in
tests/conftest.py — the suite is hermetic and offline.

Coverage (docs/ARCHITECTURE.md §17.7 "NEW gateway tests to ADD"):
  1. ``GET /`` -> 200, renders gateway.html, is theme-NEUTRAL even with a
     ``theme=horror``/``theme=sea`` cookie (D16/Q-M16-12); ``data-theme-neutral``
     present; no ``.theme-*`` class on <html>/<body>; never 3xx (D17).
  2. Cursive ``<h1 id="gw-heading">choose a chest</h1>``.
  3. Exactly THREE ``.gw-chest`` buttons (horror/random/sea), each with its
     symbol + a non-empty aria-label; the only focusable controls are the 3
     chests + the brand logo; no ``tabindex`` anywhere.
  4. Cookie-before-navigate wiring (theme.js + gateway.js loaded;
     ``Archive19Theme.choose`` + ``location.assign("/map/horror"|"/map/sea")``).
  5. Chest-2 RANDOM rule (Math.random) + reduced-motion skip path (D21/D22).
  6. Subpage forced-theme proof (D15): /map/horror -> theme-horror +
     data-force-theme even with the OPPOSITE cookie; /map/sea -> theme-sea.
  7. gateway.html asset set: style.css?v=9, theme.js, gateway.js; references the
     painted backdrop /static/img/gateway/gateway-bg.jpg (file exists on disk).
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
# The `googleapis` host is narrowed to the Drive/credential hosts so the benign
# `fonts.googleapis.com` Google-Fonts CDN (loaded by gateway.html) is not a false
# positive — see the note in tests/test_frontend.py::LEAK_NEEDLES.
LEAK_NEEDLES = [
    "www.googleapis.com",
    "drive.googleapis.com",
    "drive.google",
    "AIza",
    "key=",
]


def _strip_comments(html: str) -> str:
    """Remove HTML comments so an example ``<html ...>`` string embedded in a
    leading ``<!-- ... -->`` doc comment (gateway.html) is never mistaken for the
    real document tag."""
    return re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)


def _html_open_tag(html: str) -> str:
    """Return the REAL ``<html ...>`` opening tag (comment-stripped)."""
    cleaned = _strip_comments(html)
    start = cleaned.index("<html")
    return cleaned[start: cleaned.index(">", start) + 1]


def _body_open_tag(html: str) -> str:
    """Return the literal ``<body ...>`` opening tag."""
    start = html.index("<body")
    return html[start: html.index(">", start) + 1]


# ===========================================================================
# 1. GET / -> 200, gateway.html, theme-NEUTRAL (D16/Q-M16-12), no redirect (D17).
# ===========================================================================
def test_gateway_renders_and_is_200(client):
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert html.startswith("<!"), "not a rendered HTML page"
    # The .gateway namespace + gateway-page body marker identify gateway.html.
    assert 'class="gateway"' in html
    assert 'class="gateway-page"' in html


@pytest.mark.parametrize("cookie", [None, "horror", "sea", "purple-nonsense"])
def test_gateway_is_theme_neutral_regardless_of_cookie(client, cookie):
    """D16/Q-M16-12: the gateway ignores any stored theme cookie for its OWN
    render — NO ``.theme-horror``/``.theme-sea`` on <html>/<body>, and the
    explicit ``data-theme-neutral`` marker is present."""
    if cookie is not None:
        client.cookies.set("theme", cookie)
    html = client.get("/").text

    html_tag = _html_open_tag(html)
    body_tag = _body_open_tag(html)
    assert "data-theme-neutral" in html_tag, html_tag
    # No theme class on the structural tags (the neutral signal).
    assert "theme-horror" not in html_tag, html_tag
    assert "theme-sea" not in html_tag, html_tag
    assert "theme-horror" not in body_tag, body_tag
    assert "theme-sea" not in body_tag, body_tag
    # Belt-and-braces: the theme-class strings the maps carry never appear at all
    # on the gateway document (no .atmosphere/.layer map machinery either).
    assert 'class="theme-horror' not in html
    assert 'class="theme-sea' not in html


@pytest.mark.parametrize("cookie", [None, "horror", "sea"])
def test_gateway_never_redirects(client, cookie):
    """D17: ``/`` is ALWAYS the gateway, never a 301/302 — even with a stored
    cookie (Q-M16-7 lean: show the chests every visit)."""
    if cookie is not None:
        client.cookies.set("theme", cookie)
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 200, resp.status_code
    assert not (300 <= resp.status_code < 400), f"gateway redirected: {resp.status_code}"


# ===========================================================================
# 2. The cursive heading.
# ===========================================================================
def test_gateway_has_cursive_choose_a_chest_heading(client):
    html = client.get("/").text
    m = re.search(r'<h1[^>]*\bid="gw-heading"[^>]*>(.*?)</h1>', html, re.DOTALL)
    assert m is not None, "no <h1 id=\"gw-heading\"> on the gateway"
    h1_open = html[html.index("<h1"): html.index(">", html.index("<h1")) + 1]
    assert "gw-heading" in h1_open
    inner = m.group(1)
    # Two-tier dragon's message: a big "reward" line + a smaller call-to-action.
    assert "gw-heading-main" in inner and "gw-heading-sub" in inner, inner
    assert "brave soul" in inner, inner
    assert "choose a chest" in inner, inner  # the call-to-action is preserved


# ===========================================================================
# 3. Exactly three chests (horror/random/sea), symbols, a11y, focus surface.
# ===========================================================================
def _chest_buttons(html: str) -> list[str]:
    """Return each ``<button class="gw-chest ...">...</button>`` block."""
    return re.findall(r'<button\b[^>]*class="gw-chest[^"]*"[^>]*>.*?</button>', html, re.DOTALL)


def test_gateway_has_exactly_three_chests_with_expected_themes(client):
    html = client.get("/").text
    chests = _chest_buttons(html)
    assert len(chests) == 3, f"expected 3 .gw-chest buttons, got {len(chests)}"
    themes = re.findall(r'<button\b[^>]*class="gw-chest[^"]*"[^>]*data-theme="([^"]+)"', html)
    # Document order: chest1 = moon -> horror, chest2 = twin -> random, chest3 = sun -> sea.
    assert themes == ["horror", "random", "sea"], themes


def test_each_chest_bears_its_symbol_marker(client):
    """Each chest carries its differentiating SVG symbol (M16R5 / Q-M16-11):
    chest1 a moon, chest2 the half-sun/half-moon (largest), chest3 a sun. All
    three share the inert ``.gw-symbol`` group; their wood-gradient ids
    (wood1/wood2/wood3) tag the individual chest art."""
    html = client.get("/").text
    chests = _chest_buttons(html)
    assert len(chests) == 3
    # Every chest renders a .gw-symbol group (the on-lid emblem).
    for i, block in enumerate(chests, start=1):
        assert 'class="gw-symbol"' in block, f"chest {i} missing .gw-symbol"
    # The three chest variants are distinct (per-chest modifier + gradient id).
    assert "gw-chest--1" in chests[0] and "wood1" in chests[0]
    assert "gw-chest--2" in chests[1] and "wood2" in chests[1]
    assert "gw-chest--3" in chests[2] and "wood3" in chests[2]


def test_each_chest_has_nonempty_aria_label(client):
    """M16R10: every chest is a focusable <button> with a non-empty aria-label."""
    html = client.get("/").text
    labels = re.findall(
        r'<button\b[^>]*class="gw-chest[^"]*"[^>]*aria-label="([^"]+)"', html
    )
    assert len(labels) == 3, f"expected 3 aria-labelled chests, got {len(labels)}"
    for label in labels:
        assert label.strip(), f"empty chest aria-label: {label!r}"


def test_chests_have_no_visible_text_label(client):
    """M16R5/Q-M16-11: uniform chests differentiated by SYMBOL only — no visible
    text inside the button (only the inert SVG art)."""
    html = client.get("/").text
    for i, block in enumerate(_chest_buttons(html), start=1):
        # Strip out all tags; whatever text remains would be a visible label.
        text = re.sub(r"<[^>]+>", "", block)
        # Unescape comment-free whitespace; SVG comments were already inside tags.
        assert text.strip() == "", f"chest {i} has visible text: {text.strip()!r}"


def test_decorative_svg_is_inert(client):
    """NF-M16-2: the chest art + reveal SVG layers are decorative — aria-hidden,
    ``focusable="false"`` and NOT focusable. No interactive elements other than
    the 3 chests + the brand logo, and NO tabindex anywhere on the gateway."""
    html = client.get("/").text
    # Every decorative <svg> opts out of focus + the a11y tree.
    for svg_open in re.findall(r"<svg\b[^>]*>", html):
        assert 'focusable="false"' in svg_open, f"svg missing focusable=false: {svg_open}"
        assert 'aria-hidden="true"' in svg_open, f"svg missing aria-hidden: {svg_open}"
    # The reveal overlay itself is aria-hidden.
    assert 'class="gw-reveal"' in html
    assert 'id="gw-reveal"' in html
    gw_reveal_open = html[html.index('<div class="gw-reveal"'):]
    gw_reveal_open = gw_reveal_open[: gw_reveal_open.index(">") + 1]
    assert 'aria-hidden="true"' in gw_reveal_open, gw_reveal_open
    # NO tabindex is emitted anywhere (no positive tabindex, no focus traps).
    assert "tabindex" not in html, "gateway must not emit tabindex"


def test_only_focusable_controls_are_three_chests_and_brand_logo(client):
    """The only interactive/focusable controls on the neutral gateway are the
    three chest buttons + the brand-logo link (Q-M16-10: logo -> "/"). There is
    NO map toggle here (it lives on the subpages, Q-M16-9)."""
    html = client.get("/").text
    buttons = re.findall(r"<button\b", html)
    anchors = re.findall(r"<a\b", html)
    # Exactly the 3 chests, no other buttons (no theme-toggle).
    assert len(buttons) == 3, f"expected 3 buttons (chests), got {len(buttons)}"
    # Exactly one anchor: the brand logo linking home.
    assert len(anchors) == 1, f"expected 1 anchor (brand logo), got {len(anchors)}"
    assert 'class="brand-logo" href="/"' in html
    # No other focusable form controls.
    for tag in ("<input", "<select", "<textarea"):
        assert tag not in html, f"unexpected focusable control {tag!r} on gateway"


def test_gateway_has_no_map_toggle(client):
    """Q-M16-9: the in-page theme toggle stays on the MAP subpages; the gateway
    carries chests instead (paired with test_frontend's relocated toggle test)."""
    html = client.get("/").text
    assert 'id="theme-toggle"' not in html
    assert "Sail to the Sea" not in html
    assert "Enter the Corridor" not in html


# ===========================================================================
# 4. Cookie-before-navigate wiring (theme.js + gateway.js; choose() + assign()).
# ===========================================================================
def test_gateway_loads_theme_js_then_gateway_js(client):
    """D19/D20: the gateway loads theme.js (for Archive19Theme.choose) and
    gateway.js (the reveal orchestrator), in that order."""
    html = client.get("/").text
    assert '<script src="/static/theme.js"></script>' in html
    assert '<script src="/static/gateway.js"></script>' in html
    assert html.index('src="/static/theme.js"') < html.index('src="/static/gateway.js"'), (
        "theme.js must load BEFORE gateway.js (gateway.js depends on it)"
    )


def test_gateway_js_wires_choose_then_navigate(client):
    """Assert the load-bearing wiring literals in gateway.js (the established
    house style of asserting JS strings, mirroring test_frontend's fetch checks):
    it calls ``Archive19Theme.choose(...)`` BEFORE navigating, and both map
    destinations are reachable via ``location.assign``."""
    js = (STATIC_DIR / "gateway.js").read_text(encoding="utf-8")
    assert "Archive19Theme.choose" in js, "gateway.js must call Archive19Theme.choose"
    assert "location.assign" in js, "gateway.js must navigate via location.assign"
    assert '"/map/horror"' in js, "gateway.js missing the /map/horror destination"
    assert '"/map/sea"' in js, "gateway.js missing the /map/sea destination"


# ===========================================================================
# 5. Chest-2 RANDOM rule (D21) + reduced-motion skip path (D22).
# ===========================================================================
def test_chest2_random_resolution(client):
    """D21/Q-M16-1: chest2 (data-theme="random") resolves via a single
    Math.random() coin -> "horror" | "sea", driving BOTH the reveal art AND the
    destination. Both /map/horror and /map/sea must be reachable from it."""
    html = client.get("/").text
    # The random chest is present in the markup.
    assert 'data-theme="random"' in html
    js = (STATIC_DIR / "gateway.js").read_text(encoding="utf-8")
    assert "Math.random()" in js, "chest2 must use a Math.random() coin (D21)"
    # The DEST map exposes BOTH realms (so chest2's coin can reach either).
    assert "/map/horror" in js and "/map/sea" in js


def test_reduced_motion_skip_path_exists(client):
    """D22/NF-M16-2: under prefers-reduced-motion the reveal is SKIPPED — the JS
    has a matchMedia branch that navigates immediately, and the CSS freezes the
    reveal keyframes in a reduce media block."""
    js = (STATIC_DIR / "gateway.js").read_text(encoding="utf-8")
    assert 'matchMedia("(prefers-reduced-motion: reduce)")' in js, (
        "gateway.js missing the reduced-motion matchMedia guard"
    )
    css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")
    blocks = re.findall(
        r"@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{(.*?)\n\}",
        css,
        re.DOTALL,
    )
    gw_block = next((b for b in blocks if "gw-reveal" in b or "gw-zoom" in b
                     or "gw-reveal-ghost" in b), None)
    assert gw_block is not None, (
        "no prefers-reduced-motion block neutralizes the gateway reveal animation"
    )


def test_reveal_keyframes_are_defined(client):
    """Sanity: the reveal animation the reduced-motion block neutralizes exists."""
    css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")
    for kf in ("gw-zoom", "gw-veil"):
        assert f"@keyframes {kf}" in css, f"missing keyframes {kf}"


# ===========================================================================
# 6. Subpage forced-theme proof (D15) — deep-linkable standalone, cookie-immune.
# ===========================================================================
def test_map_horror_forces_horror_even_with_sea_cookie(client):
    """D15/M16R13: /map/horror renders horror + data-force-theme="horror" and the
    horror map markup, even when the stored cookie says ``sea`` (forced-theme proof)."""
    client.cookies.set("theme", "sea")
    resp = client.get("/map/horror")
    assert resp.status_code == 200
    html = resp.text
    html_tag = _html_open_tag(html)
    assert 'class="theme-horror"' in html_tag, html_tag
    assert 'data-force-theme="horror"' in html_tag, html_tag
    assert 'class="theme-horror min-h-screen"' in _body_open_tag(html)
    # Real horror MAP markup is present (hotspot machinery).
    assert 'class="horror-map"' in html
    assert 'class="map-hotspot' in html
    assert "theme-sea" not in html


def test_map_sea_forces_sea_even_with_horror_cookie(client):
    """D15/M16R13: /map/sea renders sea + data-force-theme="sea" and the sea map
    markup, even when the stored cookie says ``horror``."""
    client.cookies.set("theme", "horror")
    resp = client.get("/map/sea")
    assert resp.status_code == 200
    html = resp.text
    html_tag = _html_open_tag(html)
    assert 'class="theme-sea"' in html_tag, html_tag
    assert 'data-force-theme="sea"' in html_tag, html_tag
    assert 'class="theme-sea min-h-screen"' in _body_open_tag(html)
    # Real sea MAP markup is present.
    assert 'class="sea-map"' in html
    assert 'class="map-hotspot' in html
    assert "theme-horror" not in html


@pytest.mark.parametrize("path,theme", [("/map/horror", "horror"), ("/map/sea", "sea")])
def test_map_subpages_deep_linkable_no_cookie(client, path, theme):
    """M16R13: each map subpage is correct standalone (no cookie at all)."""
    resp = client.get(path)
    assert resp.status_code == 200
    html = resp.text
    assert f'class="theme-{theme}"' in _html_open_tag(html)
    assert f'data-force-theme="{theme}"' in _html_open_tag(html)


# ===========================================================================
# 7. gateway.html asset set + painted backdrop reference (NF-M16-9).
# ===========================================================================
def test_gateway_links_versioned_style_css(client):
    html = client.get("/").text
    assert '<link rel="stylesheet" href="/static/style.css?v=9" />' in html, (
        "gateway must link the M16-bumped style.css?v=9 (NF-M16-9)"
    )


def test_gateway_backdrop_painting_referenced_in_css_and_exists_on_disk(client):
    """The painted dragon-vault backdrop is applied via CSS (.gateway background).
    Assert the CSS references it AND the asset exists on disk (hermetic — no net)."""
    css = (STATIC_DIR / "style.css").read_text(encoding="utf-8")
    assert "/static/img/gateway/gateway-bg.jpg" in css, (
        "gateway backdrop painting not referenced in style.css"
    )
    bg = STATIC_DIR / "img" / "gateway" / "gateway-bg.jpg"
    assert bg.exists(), f"{bg} referenced by .gateway CSS but missing on disk"
    assert bg.stat().st_size > 0, f"{bg} is empty"


# ===========================================================================
# 8. No secret/Drive leak on the gateway (defense-in-depth, mirrors test_frontend).
# ===========================================================================
@pytest.mark.parametrize("cookie", [None, "horror", "sea"])
def test_no_secret_or_drive_leak_on_gateway(client, cookie):
    if cookie is not None:
        client.cookies.set("theme", cookie)
    html = client.get("/").text
    for needle in LEAK_NEEDLES:
        assert needle not in html, f"leaked {needle!r} on the gateway"
    assert fake.DUMMY_SECRET not in html
    assert fake.DUMMY_KEY not in html
