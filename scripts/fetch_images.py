#!/usr/bin/env python3
"""Build-time + local-dev image bake for Archive 19 (M12 — ARCHITECTURE §12.2).

Downloads every available level's images (and the ``missing/`` fallback set,
§12.2/§12.3) from Google Drive into ``static/img/levels/{id}/{PhotoRef.name}``
and writes ``static/img/levels/manifest.json``. The app then serves these as
plain static files (no per-request Drive proxy on the image path — BakeR2).

This script is NOT imported by the app at runtime; it runs only at build time
(via ``render.yaml`` ``buildCommand``) and locally for dev parity (BakeQ6). It
reuses ``drive_service`` for discovery (metadata, not throttled — §12.1) and the
SAME paced downloader the runtime background sync uses (NF-Bake7: one source of
truth for the pacing/backoff/atomic-write logic).

Security (NF-Bake5): ``GD_API_KEY`` is read ONLY via ``os.environ``
(``drive_service._get_api_key``); it is NEVER written to disk, NEVER placed in
the manifest, and NEVER logged. The manifest carries only ``file_id`` + ``name``
(both already client-visible today — §12.7). Hostile filenames (``/``, ``\\``,
``..``) are rejected; same-folder name collisions are flagged loudly.

Usage:
    python scripts/fetch_images.py [--out DIR] [--concurrency N] [--delay S]
        [--max-retries N] [--force] [--skip-missing] [--no-manifest]

Failure policy (§12.6, proxy KEPT default): retry-with-backoff then WARN +
serve-partial — a file that still fails after its retry budget is logged and
skipped; the build still succeeds and the kept media proxy backstops the gap.
Exit code is non-zero ONLY when a hard configuration error prevents any bake.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Make the repo root importable so ``import app.drive_service`` works whether
# this is run as ``python scripts/fetch_images.py`` or from elsewhere.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Load a local .env for dev parity (no-op in CI/prod where real env vars win).
try:
    from dotenv import load_dotenv

    load_dotenv(_REPO_ROOT / ".env", override=False)
except ImportError:
    pass

from app import drive_service  # noqa: E402
from app.drive_service import (  # noqa: E402
    DiscoveryCache,
    DriveConfigError,
    PhotoRef,
    build_manifest_dict,
    download_images_paced,
    is_safe_name,
)

logger = logging.getLogger("archive19.bake")


def _plan_targets(
    cache: DiscoveryCache, out_dir: Path, bake_missing: bool
) -> list[tuple[Path, str]]:
    """Build the ``(dest_path, file_id)`` download plan from the discovery cache.

    Rejects hostile filenames and flags same-folder name collisions loudly
    (§12.3 BakeQ5 edge). The confirmed real set never trips these branches; they
    exist so a future odd upload fails visibly, not silently.
    """
    targets: list[tuple[Path, str]] = []

    def _collect(refs: list[PhotoRef], subdir: str) -> None:
        seen: dict[str, str] = {}  # name -> file_id (collision detection)
        for ref in refs:
            name = ref.name
            if not is_safe_name(name):
                logger.warning(
                    "REJECTED unsafe filename in %s (path separator or '..'); "
                    "skipping a file (NF-Bake5).",
                    subdir,
                )
                continue
            if name in seen and seen[name] != ref.file_id:
                logger.warning(
                    "COLLISION: two different files share name %r in %s/ — this "
                    "ALSO breaks the M11 caption key; flagging loudly and "
                    "suffixing the second copy.",
                    name,
                    subdir,
                )
                # Suffix so we never silently overwrite; signals an upstream bug.
                stem_name = f"{name}#2"
                targets.append((out_dir / subdir / stem_name, ref.file_id))
                continue
            seen[name] = ref.file_id
            targets.append((out_dir / subdir / name, ref.file_id))

    for level_id, refs in sorted(cache.level_images.items()):
        if level_id in cache.folder_index:
            _collect(refs, str(level_id))

    if bake_missing and cache.missing_images:
        _collect(cache.missing_images, drive_service.MISSING_DIR_NAME)

    return targets


async def _run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = _REPO_ROOT / out_dir

    # 1) Discovery — metadata only (NOT throttled, §12.1). Same code path as the
    #    app, so the bake set is exactly the discovered set (NF-Bake7).
    try:
        drive_service._get_api_key()  # fail fast if the key is absent
        drive_service._get_root_folder()
    except DriveConfigError as exc:
        logger.error("Cannot bake: %s", exc)
        return 2

    cache = await drive_service.discover_levels(force=True)
    if not cache.ready:
        logger.error("Discovery did not complete (Drive unreachable?). Aborting bake.")
        return 2

    available = sorted(cache.folder_index.keys())
    n_imgs = sum(len(cache.level_images.get(i, [])) for i in available)
    n_missing = len(cache.missing_images or [])
    logger.info(
        "Discovered %d available level(s) %s, %d level image(s), %d missing image(s).",
        len(available),
        available,
        n_imgs,
        n_missing,
    )

    # 2) Plan + download (paced, idempotent, atomic — shared downloader).
    targets = _plan_targets(cache, out_dir, bake_missing=not args.skip_missing)
    logger.info("Planned %d download target(s) into %s.", len(targets), out_dir)

    downloaded, skipped, failures = await download_images_paced(
        targets,
        concurrency=args.concurrency,
        delay=args.delay,
        force=args.force,
    )
    logger.info(
        "Bake summary: %d downloaded, %d skipped (already present), %d failed.",
        downloaded,
        skipped,
        len(failures),
    )
    if failures:
        # §12.6 (proxy KEPT default): WARN + serve-partial. The build still
        # succeeds; the kept media proxy backstops any un-baked id at runtime.
        logger.warning(
            "%d file(s) failed after the retry budget; the build proceeds "
            "(serve-partial, §12.6). The kept media proxy backstops these at "
            "runtime. Re-run the script (idempotent) to retry just the missing.",
            len(failures),
        )

    # 3) Write the manifest (PRIMARY discovery source — §12.4). Carries only
    #    file_id + name (no key, no folder ids — §12.7).
    if args.manifest:
        manifest = build_manifest_dict(cache)
        drive_service.MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        manifest_path = (
            out_dir / "manifest.json"
            if out_dir != drive_service.LEVELS_IMG_DIR
            else drive_service.MANIFEST_PATH
        )
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        logger.info("Wrote manifest: %s", manifest_path)

    # Serve-partial policy keeps the exit code 0 even with failures (proxy KEPT).
    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bake Drive images into static/.")
    p.add_argument("--out", default="static/img/levels", help="base output dir")
    p.add_argument(
        "--concurrency",
        type=int,
        default=drive_service.DOWNLOAD_CONCURRENCY,
        help="max simultaneous alt=media downloads (default 2)",
    )
    p.add_argument(
        "--delay",
        type=float,
        default=drive_service.DOWNLOAD_DELAY,
        help="seconds between request starts, per worker (default 0.4)",
    )
    p.add_argument(
        "--max-retries",
        type=int,
        default=drive_service.DOWNLOAD_MAX_RETRIES,
        help="retry budget per file on 403/429/5xx (default 5)",
    )
    p.add_argument(
        "--force", action="store_true", help="re-download even if the file exists"
    )
    p.add_argument(
        "--skip-missing",
        action="store_true",
        help="do NOT bake the missing/ set (default: bake it)",
    )
    p.add_argument(
        "--no-manifest",
        dest="manifest",
        action="store_false",
        help="do not write manifest.json (default: write it)",
    )
    p.set_defaults(manifest=True)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    # Apply the retry-budget override globally (the shared downloader reads it).
    drive_service.DOWNLOAD_MAX_RETRIES = args.max_retries
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
