"""Shared fixtures for the Archive 19 backend test suite (M13 — Cloudinary).

M13 migration: the image source is now Cloudinary's keyless public CDN, not the
Google-Drive byte proxy. The single network funnel is the Cloudinary Admin API
list (``cloudinary_service._list_all_resources``); discovery groups its result
by ``asset_folder`` into the cache. This conftest mocks THAT one call so the
whole suite is hermetic and offline — no httpx request ever leaves the process.

What was RETIRED here vs the M12 Drive conftest (and why):
  * ``patched_drive`` / ``list_children`` fake tree — Drive discovery is gone;
    replaced by ``CLOUD_RESOURCES`` + a patched ``_list_all_resources``.
  * ``patched_media`` + ``MockTransport`` byte handler / ``MEDIA_BYTES`` — the
    ``/api/levels/{id}/media/{file_id}`` proxy, ``resolve_media`` and the byte
    LRU were REMOVED (M13); images stream straight from ``res.cloudinary.com``,
    so there is no server-side byte fetch to mock.
  * ``isolate_bake`` manifest/baked-image redirect — the ``scripts/fetch_images``
    bake + ``static/img/levels/manifest.json`` loader are gone; Cloudinary is the
    sole source. The hermetic guard is now ``isolate_cloudinary`` below.

The mocked resource set yields available levels {1, 2, 8} with a dynamic span of
0..8 and a populated ``missing`` pool — the same available/span shape the older
Drive fake produced, so the still-valid frontend/SSR/caption tests keep their
expectations.
"""

from __future__ import annotations

import os

import pytest

# Dummy Cloudinary creds BEFORE importing the app, so module import + lifespan
# never try to read a real CLOUDINARY_URL. The secret is a placeholder; the
# patched ``_list_all_resources`` means no real api.cloudinary.com call happens.
os.environ.setdefault("CLOUDINARY_URL", "cloudinary://TESTKEY:TESTSECRET@testcloud")

from app import cloudinary_service  # noqa: E402
from app import main as main_module  # noqa: E402

# The placeholder secret that must NEVER appear in any client-facing payload.
DUMMY_SECRET = "TESTSECRET"
DUMMY_KEY = "TESTKEY"
DUMMY_CLOUD = "testcloud"
DUMMY_CLOUDINARY_URL = f"cloudinary://{DUMMY_KEY}:{DUMMY_SECRET}@{DUMMY_CLOUD}"


# --- Fake Cloudinary Admin-API resource set --------------------------------
# Mirrors the live ``GET resources/image`` payload shape: each item carries a
# ``public_id`` (Cloudinary's "{stem}_{6char}" form), a ``format``, and an
# ``asset_folder`` ("all ages/{N}" -> level N; "all ages/missing" -> fallback).
#
# Present numbered folders: 1 (2 imgs), 2 (1 img), 8 (1 img) -> available {1,2,8}
# Dynamic span -> 0..8.  A "missing" pool with 2 images.  Plus two noise
# resources (root upload + a non-"all ages" folder) that discovery must ignore.

# public_ids (stable identifiers used by tests).
PID_1A = "1_uuasv3"        # level 1, stem "1"
PID_1B = "1.2_abc123"      # level 1, stem "1.2"
PID_2A = "2.1_zzzzaa"      # level 2, stem "2.1"
PID_8A = "8.1_qw12er"      # level 8, stem "8.1"
MISS_A = "stock1_aaaaaa"   # missing pool, stem "stock1"
MISS_B = "stock2_bbbbbb"   # missing pool, stem "stock2"

# Derived stems (what captions key on after the M13 re-key).
STEM_1A = "1"
STEM_1B = "1.2"
STEM_2A = "2.1"
STEM_8A = "8.1"


def _default_resources() -> list[dict]:
    """Return a fresh copy of the fake Admin-API resource list."""
    return [
        {"public_id": PID_1A, "format": "jpg", "asset_folder": "all ages/1"},
        {"public_id": PID_1B, "format": "jpg", "asset_folder": "all ages/1"},
        {"public_id": PID_2A, "format": "png", "asset_folder": "all ages/2"},
        {"public_id": PID_8A, "format": "jpg", "asset_folder": "all ages/8"},
        {"public_id": MISS_A, "format": "jpg", "asset_folder": "all ages/missing"},
        {"public_id": MISS_B, "format": "png", "asset_folder": "all ages/missing"},
        # Noise that must be ignored by _build_cache:
        {"public_id": "root_upload_xxxxxx", "format": "jpg", "asset_folder": ""},
        {"public_id": "other_yyyyyy", "format": "jpg", "asset_folder": "misc/stuff"},
    ]


def _cdn_url(public_id: str, fmt: str) -> str:
    """The expected keyless CDN delivery URL for an asset under the dummy cloud."""
    return (
        f"https://res.cloudinary.com/{DUMMY_CLOUD}/image/upload/"
        f"f_auto,q_auto/{public_id}.{fmt}"
    )


@pytest.fixture
def cloud_resources():
    """Mutable fake resource list the test can edit (e.g. for /api/refresh)."""
    return _default_resources()


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset the module-level discovery cache before & after each test."""
    cloudinary_service._cache = cloudinary_service.DiscoveryCache()
    yield
    cloudinary_service._cache = cloudinary_service.DiscoveryCache()


@pytest.fixture(autouse=True)
def isolate_cloudinary(monkeypatch):
    """Make the whole suite hermetic w.r.t. the real Cloudinary Admin API.

    Forces dummy ``CLOUDINARY_URL`` for EVERY test regardless of the ambient
    environment / a local ``.env`` (so a real cloud is never contacted), and
    keeps ``IMAGE_SYNC_INTERVAL_SECONDS`` empty so the background re-list loop is
    never scheduled (the lifespan gate needs interval>0 AND creds). Tests that
    need NO creds (graceful-degrade cases) delete the var themselves.

    Also installs a network-refusing default for ``_list_all_resources`` so a
    test that forgets to patch the resource list can NEVER reach api.cloudinary.
    The ``cloud_client`` fixture re-patches it with the fake resources; pytest's
    monkeypatch layering lets that win.
    """
    monkeypatch.setenv("CLOUDINARY_URL", DUMMY_CLOUDINARY_URL)
    monkeypatch.setenv("IMAGE_SYNC_INTERVAL_SECONDS", "")

    async def _no_network(cfg, client):  # pragma: no cover - safety net
        raise AssertionError(
            "cloudinary_service._list_all_resources reached live network in a "
            "test; a fixture must patch it (the suite is hermetic)."
        )

    monkeypatch.setattr(cloudinary_service, "_list_all_resources", _no_network)
    yield


@pytest.fixture
def patched_cloudinary(monkeypatch, cloud_resources):
    """Patch ``_list_all_resources`` to serve ``cloud_resources`` (no network).

    Returns the resource list so tests can mutate it (add/remove resources) and
    then ``POST /api/refresh`` to observe re-discovery. The Admin secret in the
    dummy ``CLOUDINARY_URL`` is the only auth; no real request is ever made.
    """

    async def fake_list(cfg, client):
        # Mirror the real signature; ignore cfg/client. Return a copy so a test's
        # later mutation of cloud_resources only takes effect on the next call.
        return list(cloud_resources)

    monkeypatch.setattr(cloudinary_service, "_list_all_resources", fake_list)
    return cloud_resources


@pytest.fixture
def client(patched_cloudinary):
    """A TestClient with discovery pre-built from the fake resource list.

    Using the context manager triggers the lifespan handler, which calls
    ``discover(force=True)`` against the patched ``_list_all_resources``.
    """
    from fastapi.testclient import TestClient

    with TestClient(main_module.app) as c:
        yield c
