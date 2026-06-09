"""Image caption loader for Archive 19 — dual-theme, tolerant by design.

Implements docs/ARCHITECTURE.md §11.1 / §11.2:

- A single committed ``app/captions.json`` is the source of truth (CapR3),
  keyed by ``(level, filename)`` — NOT by Drive ``file_id`` (CapQ1: ids are not
  stable across re-upload). Schema (top-level keys are level ids as STRINGS):

      { "<level-id>": { "<filename>": { "sea": "...", "horror": "..." } } }

- The file is read ONCE and cached in a module global, mirroring the R2
  discovery-cache model (§5.1). ``load_captions()`` is called in the FastAPI
  ``lifespan`` startup; ``reload_captions()`` is called on ``POST /api/refresh``
  so a caption edit is picked up without a redeploy.

- The feature is OPTIONAL / degrade-to-nothing (CapR6, NF-Cap1, NF-Cap5):
    * a missing file -> empty map (debug note),
    * malformed JSON / wrong shape -> empty map (warning),
    * a missing level, filename, or ``sea``/``horror`` sub-key -> no caption.
  The loader NEVER raises — an image with no caption renders exactly as today.

Security: this module reads only a committed JSON data file. It touches no
secret, no environment variable, and no network — ``GD_API_KEY`` is never
involved here. Lookups are pure in-memory dict gets (no per-request I/O).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("archive19.captions")

# captions.json lives next to this module, inside the app/ package (§11.2).
CAPTIONS_PATH = Path(__file__).resolve().parent / "captions.json"

# Module-level cache: { level_id_str: { filename: { "sea": str, "horror": str } } }.
# Loaded once by ``load_captions`` (startup) and rebuilt by ``reload_captions``
# (POST /api/refresh). ``None`` means "not yet loaded"; an empty dict means
# "loaded, but no captions" (the inert, fully-supported default).
_captions: Optional[dict[str, dict[str, dict[str, str]]]] = None


def _read_captions_file() -> dict[str, dict[str, dict[str, str]]]:
    """Read + validate ``app/captions.json``, returning a normalized map.

    Tolerant by design (§11.2): a missing file, malformed JSON, or an
    unexpected top-level shape all degrade to an empty map. Never raises.

    Normalization keeps only well-formed entries: a level whose value is an
    object, each filename whose value is an object, and within that only the
    ``sea`` / ``horror`` keys that are strings. This means a partial entry
    (only one theme present) survives, while garbage is silently dropped — the
    payload builder then treats any absence as "no caption for that theme".
    """
    if not CAPTIONS_PATH.is_file():
        # Expected during local/dev/CI runs and before captions are authored.
        logger.debug("captions.json not found at %s; captions disabled.", CAPTIONS_PATH)
        return {}

    try:
        raw = json.loads(CAPTIONS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning(
            "captions.json could not be loaded (%s); captions disabled.",
            type(exc).__name__,
        )
        return {}

    if not isinstance(raw, dict):
        logger.warning(
            "captions.json top-level is %s, expected an object; captions disabled.",
            type(raw).__name__,
        )
        return {}

    normalized: dict[str, dict[str, dict[str, str]]] = {}
    for level_key, files in raw.items():
        if not isinstance(files, dict):
            continue
        clean_files: dict[str, dict[str, str]] = {}
        for filename, entry in files.items():
            if not isinstance(entry, dict):
                continue
            clean_entry = {
                theme: text
                for theme in ("sea", "horror")
                if isinstance((text := entry.get(theme)), str)
            }
            if clean_entry:
                clean_files[str(filename)] = clean_entry
        if clean_files:
            normalized[str(level_key)] = clean_files
    return normalized


def load_captions() -> dict[str, dict[str, dict[str, str]]]:
    """Load captions once and cache them; return the cached map.

    Subsequent calls return the cache without re-reading the file (mirrors the
    R2 discovery pattern). Call this in the FastAPI ``lifespan`` startup.
    """
    global _captions
    if _captions is None:
        _captions = _read_captions_file()
        logger.info("Captions loaded: %d level(s) carry captions.", len(_captions))
    return _captions


def reload_captions() -> dict[str, dict[str, dict[str, str]]]:
    """Re-read ``app/captions.json`` from disk and replace the cache.

    Used by ``POST /api/refresh`` so a caption edit takes effect without a
    redeploy (consistent with how refresh rebuilds discovery state).
    """
    global _captions
    _captions = _read_captions_file()
    logger.info("Captions reloaded: %d level(s) carry captions.", len(_captions))
    return _captions


def get_caption(level_id: int, filename: str) -> Optional[dict[str, str]]:
    """Return the ``{"sea", "horror"}`` dict for one image, or ``None``.

    Keyed by ``(level, filename)`` using ``PhotoRef.name`` (NOT ``file_id`` —
    CapQ1). ``None`` is returned when the level, the filename, or any caption
    data is absent. The returned dict MAY be partial (only one theme). Lookups
    are pure dict gets — no I/O (NF-Cap5). Loads lazily if not yet initialized.
    """
    captions = load_captions()
    entry = captions.get(str(level_id), {}).get(filename)
    return entry or None
