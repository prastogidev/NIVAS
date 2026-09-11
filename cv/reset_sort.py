"""
NIVAS Auto-Sort Reset & Redo Workflow Utility.

Handles safely resetting the auto-sort workflow and preparing for a redo.

IMPORTANT SAFETY RULES:
1. Resetting labels must NEVER assume the original images still exist in data/unsorted_images/.
   Because auto_sort deletes source images upon successful verification, those files
   cannot be magically recovered from unsorted_images/.
2. Prominently warns the user before performing any reset action.
3. Does NOT silently fabricate, mock, or recover missing original images.
4. To redo auto-sorting from scratch:
   - Archive/clear previous proposed raw images and manifest.
   - User re-adds/restores fresh authentic images into data/unsorted_images/.
   - Re-run auto_sort.
"""

import os
import json
import logging
import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

from backend.cv.model import WALL_CONDITION_CLASSES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("nivas.cv.reset_sort")

DEFAULT_INPUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "unsorted_images"
DEFAULT_RAW_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "wall_condition_dataset" / "raw"
DEFAULT_MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "wall_condition_dataset" / "sort_manifest.json"


def inspect_status(
    input_dir: Path = DEFAULT_INPUT_DIR,
    raw_dir: Path = DEFAULT_RAW_DIR,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> Dict[str, Any]:
    """Inspect current counts and manifest status."""
    unsorted_count = 0
    if input_dir.exists():
        unsorted_count = len([f for f in input_dir.iterdir() if f.is_file() and not f.name.startswith(".")])

    raw_counts = {cls: 0 for cls in WALL_CONDITION_CLASSES}
    if raw_dir.exists():
        for cls in WALL_CONDITION_CLASSES:
            cls_dir = raw_dir / cls
            if cls_dir.exists():
                raw_counts[cls] = len([f for f in cls_dir.iterdir() if f.is_file() and not f.name.startswith(".")])

    manifest_exists = manifest_path.exists()
    manifest_entries_count = 0
    if manifest_exists:
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                manifest_entries_count = len(data.get("entries", []))
        except Exception:
            manifest_entries_count = -1

    return {
        "unsorted_count": unsorted_count,
        "raw_counts": raw_counts,
        "total_raw": sum(raw_counts.values()),
        "manifest_exists": manifest_exists,
        "manifest_entries_count": manifest_entries_count,
    }


def print_warning_banner() -> None:
    """Print standard required warning banner."""
    print("\n" + "=" * 72)
    print("  WARNING: RESETTING AUTO-SORT WORKFLOW")
    print("=" * 72)
    print("  Source images previously processed by auto_sort were safely moved/deleted")
    print("  from data/unsorted_images/. Resetting will NOT recover deleted originals.")
    print("  Do not assume original files still exist in data/unsorted_images/.")
    print("  To redo auto-sorting, you must supply a fresh or backup batch of images.")
    print("=" * 72 + "\n")


def reset_workflow(
    input_dir: Path = DEFAULT_INPUT_DIR,
    raw_dir: Path = DEFAULT_RAW_DIR,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    clean_raw_pending: bool = False,
    archive_manifest: bool = True,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Safely reset the auto-sort manifest and optionally clean pending proposed raw images.

    Args:
        input_dir: Path to unsorted_images
        raw_dir: Path to raw dataset directory
        manifest_path: Path to sort_manifest.json
        clean_raw_pending: If True, delete unreviewed proposed files from raw class folders.
        archive_manifest: If True, archive manifest instead of deleting it.
        force: If True, bypass interactive confirmation prompt.
    """
    print_warning_banner()
    status = inspect_status(input_dir, raw_dir, manifest_path)

    print(f"Current Status:")
    print(f"  - Unsorted images in {input_dir.name}: {status['unsorted_count']}")
    print(f"  - Raw dataset images: {status['total_raw']} (across {len(WALL_CONDITION_CLASSES)} classes)")
    for cls, cnt in status["raw_counts"].items():
        print(f"      {cls}: {cnt}")
    print(f"  - Manifest exists: {status['manifest_exists']} ({status['manifest_entries_count']} entries)")
    print()

    if not force:
        confirm = input("Are you sure you want to proceed with reset? (y/N): ").strip().lower()
        if confirm != "y":
            print("Reset aborted by user.")
            return {"status": "aborted"}

    actions_taken = {
        "raw_files_removed": 0,
        "manifest_archived": False,
    }

    # 1. Archive or remove manifest
    if manifest_path.exists():
        if archive_manifest:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            archive_target = manifest_path.with_name(f"sort_manifest_archive_{ts}.json")
            shutil.move(str(manifest_path), str(archive_target))
            actions_taken["manifest_archived"] = str(archive_target)
            logger.info("Archived manifest to: %s", archive_target.name)
        else:
            manifest_path.unlink()
            actions_taken["manifest_deleted"] = True
            logger.info("Removed manifest: %s", manifest_path.name)

    # 2. Optionally clean raw proposed images
    if clean_raw_pending and raw_dir.exists():
        removed = 0
        for cls in WALL_CONDITION_CLASSES:
            cls_dir = raw_dir / cls
            if cls_dir.exists():
                for f in cls_dir.iterdir():
                    if f.is_file() and not f.name.startswith("."):
                        f.unlink()
                        removed += 1
        actions_taken["raw_files_removed"] = removed
        logger.info("Removed %d proposed images from %s", removed, raw_dir)

    print("\n" + "=" * 72)
    print("  RESET COMPLETE")
    print("=" * 72)
    print(f"  Manifest archived : {actions_taken.get('manifest_archived')}")
    print(f"  Raw files cleared : {actions_taken['raw_files_removed']}")
    print()
    print("  NEXT STEPS FOR COMPLETE REDO:")
    print("  1. Copy a fresh batch of authentic property wall photos into:")
    print(f"       {input_dir}")
    print("     Example:")
    print(f"       cp /path/to/my_backup_photos/*.jpg {input_dir}/")
    print("  2. Run auto-sorter:")
    print("       PYTHONPATH=. backend/venv/bin/python -m backend.cv.auto_sort")
    print("  3. Review predictions:")
    print("       PYTHONPATH=. backend/venv/bin/python -m backend.cv.review_sort")
    print("=" * 72 + "\n")

    return actions_taken


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Safely reset auto-sort workflow and prepare for a fresh redo batch.")
    parser.add_argument("--clean-raw-pending", action="store_true", help="Remove previously sorted images from raw class folders")
    parser.add_argument("--no-archive", dest="archive_manifest", action="store_false", default=True, help="Delete manifest instead of archiving")
    parser.add_argument("--force", action="store_true", help="Bypass interactive confirmation prompt")
    args = parser.parse_args()

    reset_workflow(
        clean_raw_pending=args.clean_raw_pending,
        archive_manifest=args.archive_manifest,
        force=args.force,
    )
