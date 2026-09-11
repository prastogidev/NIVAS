"""
NIVAS Dataset Label Review & Correction Tool.

Reads the auto-sort manifest and provides an interactive CLI for reviewing
and correcting model-predicted labels before they are treated as training data.

Workflow:
1. Read manifest from data/wall_condition_dataset/sort_manifest.json.
2. For each pending entry, display prediction, confidence, and probabilities.
3. Accept human correction or approval.
4. Move images to corrected class folders if the label changes.
5. Save the updated manifest with review status and timestamps.

Does NOT fabricate labels, auto-approve predictions, or train a model.
"""

import json
import shutil
import subprocess
import sys
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

from backend.cv.model import WALL_CONDITION_CLASSES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("nivas.cv.review_sort")

DEFAULT_MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "wall_condition_dataset" / "sort_manifest.json"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "wall_condition_dataset" / "raw"


def open_image_viewer(image_path: Path) -> bool:
    """
    Open an image file in the OS default image viewer.

    On macOS this uses ``open <path>`` which launches Preview (or the
    user's configured default app) without blocking the terminal.

    Returns True if the viewer was launched successfully, False otherwise.
    """
    resolved = image_path.resolve()
    if not resolved.exists():
        logger.warning("Cannot open image — file not found: %s", resolved)
        return False

    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(resolved)])
        elif sys.platform == "win32":
            subprocess.Popen(["start", "", str(resolved)], shell=True)
        else:
            # Linux / other — try xdg-open
            subprocess.Popen(["xdg-open", str(resolved)])
        return True
    except (OSError, FileNotFoundError) as exc:
        logger.warning("Failed to open image viewer for '%s': %s", resolved, exc)
        return False


def _resolve_image_path(entry: Dict[str, Any]) -> Optional[Path]:
    """
    Determine the best available image file path for display.

    Priority:
    1. ``sorted_path`` — the copy living in the class folder (most current).
    2. ``original_path`` — the original source file the user dropped in.

    Returns None if neither exists on disk.
    """
    for key in ("sorted_path", "original_path"):
        raw = entry.get(key)
        if raw:
            p = Path(raw)
            if p.exists():
                return p
    return None


def load_manifest(manifest_path: Path) -> Optional[Dict[str, Any]]:
    """Load and validate the sorting manifest JSON."""
    if not manifest_path.exists():
        logger.error("Manifest file '%s' not found. Run auto_sort first.", manifest_path)
        return None

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    return manifest


def get_pending_entries(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Filter entries that still need human review."""
    return [
        entry for entry in manifest.get("entries", [])
        if entry.get("review_status") == "pending"
        and entry.get("status") in ("sorted", "dry_run")
    ]


def display_entry(entry: Dict[str, Any], index: int, total: int, image_path: Optional[Path] = None) -> None:
    """Display a single entry for human review, including the image path being shown."""
    print(f"\n{'='*60}")
    print(f"  Image {index}/{total}: {entry['original_filename']}")
    print(f"{'='*60}")
    print(f"  Predicted Class : {entry['predicted_class']}")
    print(f"  Confidence      : {entry['confidence'] * 100:.1f}%")
    print(f"  Probabilities   :")
    for cls, prob in entry.get("class_probabilities", {}).items():
        bar = "█" * int(prob * 40)
        marker = " ◄" if cls == entry["predicted_class"] else ""
        print(f"    {cls:6s}: {prob*100:5.1f}% {bar}{marker}")
    if image_path:
        print(f"  Viewing File    : {image_path}")
    elif entry.get("sorted_path"):
        print(f"  Current Location: {entry['sorted_path']}")
    print()


def interactive_review(
    manifest_path: str = str(DEFAULT_MANIFEST_PATH),
    output_dir: str = str(DEFAULT_OUTPUT_DIR),
    auto_approve_threshold: Optional[float] = None,
    _open_image_fn: Optional[Callable[[Path], bool]] = None,
) -> Dict[str, Any]:
    """
    Interactive CLI review of auto-sorted image labels.

    For each pending image the tool opens the actual image file in the OS
    default viewer (Preview on macOS) so the reviewer can visually inspect it
    before accepting or correcting the predicted label.

    Args:
        manifest_path: Path to the sorting manifest JSON.
        output_dir: Base directory for class folders.
        auto_approve_threshold: If set, auto-approve predictions with confidence
            above this threshold (0.0 to 1.0). Images below are still reviewed
            manually. Use with caution — always spot-check approved labels.
        _open_image_fn: Injectable image-opener for testing. Defaults to
            :func:`open_image_viewer`. Pass a no-op lambda in tests to avoid
            launching Preview.

    Returns:
        Summary of review actions taken.
    """
    manifest_file = Path(manifest_path)
    output_path = Path(output_dir)
    manifest = load_manifest(manifest_file)

    # Default to the real OS image viewer when no test stub is provided
    opener: Callable[[Path], bool] = _open_image_fn or open_image_viewer

    if manifest is None:
        return {"status": "error", "message": "Manifest not found."}

    pending = get_pending_entries(manifest)
    if not pending:
        logger.info("No pending entries to review. All labels have been reviewed.")
        return {"status": "complete", "pending": 0}

    logger.info("Found %d images pending review.", len(pending))
    print(f"\nNIVAS Label Review Tool")
    print(f"Classes: {', '.join(WALL_CONDITION_CLASSES)}")
    print(f"Total pending: {len(pending)}")
    print(f"Each image will open in your default viewer for visual inspection.")

    if auto_approve_threshold is not None:
        print(f"Auto-approve threshold: {auto_approve_threshold * 100:.0f}%")

    print(f"\nFor each image, enter:")
    print(f"  [Enter]  = Accept predicted label as correct")
    print(f"  0-4      = Correct to: 0=clean, 1=damp, 2=algae, 3=mold, 4=broken")
    print(f"  s        = Skip (keep as pending)")
    print(f"  d        = Delete (remove from dataset)")
    print(f"  q        = Quit (save progress)")

    actions = {"approved": 0, "corrected": 0, "skipped": 0, "deleted": 0, "auto_approved": 0}

    for i, entry in enumerate(pending, 1):
        # Auto-approve high-confidence predictions if threshold is set
        if auto_approve_threshold is not None and entry.get("confidence", 0) >= auto_approve_threshold:
            entry["review_status"] = "auto_approved"
            entry["corrected_class"] = entry["predicted_class"]
            entry["reviewed_at"] = datetime.now(timezone.utc).isoformat()
            entry["review_note"] = f"Auto-approved (confidence {entry['confidence']*100:.1f}% >= threshold {auto_approve_threshold*100:.0f}%)"
            actions["auto_approved"] += 1
            logger.info(
                "Auto-approved '%s' as '%s' (confidence %.1f%%).",
                entry["original_filename"], entry["predicted_class"], entry["confidence"] * 100,
            )
            continue

        # Resolve actual image file and open it for visual inspection
        image_path = _resolve_image_path(entry)
        display_entry(entry, i, len(pending), image_path=image_path)

        if image_path is not None:
            opened = opener(image_path)
            if not opened:
                print(f"  ⚠ Could not open image file for preview.")
        else:
            print(f"  ⚠ Image file not found on disk — decide based on metadata only.")

        while True:
            choice = input("  Your decision: ").strip().lower()

            if choice == "" or choice == "y":
                # Accept prediction
                entry["review_status"] = "approved"
                entry["corrected_class"] = entry["predicted_class"]
                entry["reviewed_at"] = datetime.now(timezone.utc).isoformat()
                actions["approved"] += 1
                print(f"  ✓ Approved as '{entry['predicted_class']}'")
                break

            elif choice in ("0", "1", "2", "3", "4"):
                new_class = WALL_CONDITION_CLASSES[int(choice)]
                old_class = entry["predicted_class"]

                if new_class == old_class:
                    entry["review_status"] = "approved"
                    entry["corrected_class"] = new_class
                    entry["reviewed_at"] = datetime.now(timezone.utc).isoformat()
                    actions["approved"] += 1
                    print(f"  ✓ Approved as '{new_class}' (same as prediction)")
                else:
                    # Move file to correct class folder
                    old_path = Path(entry.get("sorted_path", ""))
                    if old_path.exists():
                        new_dir = output_path / new_class
                        new_dir.mkdir(parents=True, exist_ok=True)
                        new_path = new_dir / old_path.name
                        if new_path.exists():
                            stem = old_path.stem
                            suffix = old_path.suffix
                            counter = 1
                            while new_path.exists():
                                new_path = new_dir / f"{stem}_{counter}{suffix}"
                                counter += 1
                        shutil.move(str(old_path), str(new_path))
                        entry["sorted_path"] = str(new_path.resolve())
                        logger.info("Moved '%s': %s -> %s", entry["original_filename"], old_class, new_class)
                    else:
                        logger.warning("File '%s' not found at '%s'. Label updated in manifest only.", entry["original_filename"], old_path)

                    entry["review_status"] = "corrected"
                    entry["corrected_class"] = new_class
                    entry["reviewed_at"] = datetime.now(timezone.utc).isoformat()
                    actions["corrected"] += 1
                    print(f"  ✎ Corrected: '{old_class}' -> '{new_class}'")
                break

            elif choice == "s":
                actions["skipped"] += 1
                print(f"  ⏭ Skipped (still pending)")
                break

            elif choice == "d":
                # Remove from dataset
                sorted_path = Path(entry.get("sorted_path", ""))
                if sorted_path.exists():
                    sorted_path.unlink()
                    logger.info("Deleted '%s' from dataset.", entry["original_filename"])
                entry["review_status"] = "deleted"
                entry["reviewed_at"] = datetime.now(timezone.utc).isoformat()
                actions["deleted"] += 1
                print(f"  ✗ Deleted from dataset")
                break

            elif choice == "q":
                print("\n  Saving progress and quitting...")
                _save_manifest(manifest, manifest_file)
                remaining = len(pending) - i
                print(f"  Progress saved. {remaining} images still pending review.")
                actions["quit_early"] = True
                return actions

            else:
                print(f"  Invalid input. Enter 0-4, Enter, s, d, or q.")

    # Save updated manifest
    _save_manifest(manifest, manifest_file)

    # Print summary
    print(f"\n{'='*60}")
    print(f"  Review Summary")
    print(f"{'='*60}")
    print(f"  Approved (human)     : {actions['approved']}")
    print(f"  Auto-approved        : {actions['auto_approved']}")
    print(f"  Corrected            : {actions['corrected']}")
    print(f"  Skipped              : {actions['skipped']}")
    print(f"  Deleted              : {actions['deleted']}")
    still_pending = len(get_pending_entries(manifest))
    print(f"  Still pending        : {still_pending}")
    print()

    if still_pending == 0:
        print("  All images reviewed. Dataset is ready for splitting and training.")
        print(f"  Next steps:")
        print(f"    1. Verify:  PYTHONPATH=. backend/venv/bin/python -m backend.cv.verify_dataset")
        print(f"    2. Split:   PYTHONPATH=. backend/venv/bin/python -m backend.cv.split_dataset --source_dir data/wall_condition_dataset/raw")
        print(f"    3. Train:   PYTHONPATH=. backend/venv/bin/python -m backend.cv.train")
    else:
        print(f"  Run this tool again to review the remaining {still_pending} images.")

    return actions


def _save_manifest(manifest: Dict[str, Any], manifest_file: Path) -> None:
    """Save updated manifest with review timestamp."""
    manifest["last_reviewed"] = datetime.now(timezone.utc).isoformat()

    # Recalculate review stats
    entries = manifest.get("entries", [])
    manifest["review_summary"] = {
        "total": len(entries),
        "approved": sum(1 for e in entries if e.get("review_status") == "approved"),
        "auto_approved": sum(1 for e in entries if e.get("review_status") == "auto_approved"),
        "corrected": sum(1 for e in entries if e.get("review_status") == "corrected"),
        "deleted": sum(1 for e in entries if e.get("review_status") == "deleted"),
        "pending": sum(1 for e in entries if e.get("review_status") == "pending"),
        "skipped_invalid": sum(1 for e in entries if e.get("status") == "skipped_invalid"),
        "skipped_duplicate": sum(1 for e in entries if e.get("status") == "skipped_duplicate"),
    }

    # Count finalized class distribution
    finalized = {}
    for entry in entries:
        final_cls = entry.get("corrected_class") or entry.get("predicted_class")
        if entry.get("review_status") in ("approved", "auto_approved", "corrected") and final_cls:
            finalized[final_cls] = finalized.get(final_cls, 0) + 1
    manifest["finalized_class_distribution"] = finalized

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    logger.info("Manifest saved to: %s", manifest_file)


def batch_approve_all(
    manifest_path: str = str(DEFAULT_MANIFEST_PATH),
) -> Dict[str, Any]:
    """
    Approve ALL pending entries as-is (accept model predictions).
    Use ONLY after visual spot-checking. This is a convenience shortcut.
    """
    manifest_file = Path(manifest_path)
    manifest = load_manifest(manifest_file)
    if manifest is None:
        return {"status": "error"}

    count = 0
    for entry in manifest.get("entries", []):
        if entry.get("review_status") == "pending" and entry.get("status") in ("sorted", "dry_run"):
            entry["review_status"] = "batch_approved"
            entry["corrected_class"] = entry["predicted_class"]
            entry["reviewed_at"] = datetime.now(timezone.utc).isoformat()
            entry["review_note"] = "Batch-approved without individual review"
            count += 1

    _save_manifest(manifest, manifest_file)
    logger.info("Batch-approved %d entries.", count)
    return {"batch_approved": count}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Review and correct auto-sorted wall-condition image labels.")
    parser.add_argument(
        "--manifest", type=str, default=str(DEFAULT_MANIFEST_PATH),
        help="Path to the sorting manifest JSON",
    )
    parser.add_argument(
        "--output_dir", type=str, default=str(DEFAULT_OUTPUT_DIR),
        help="Base directory for class folders",
    )
    parser.add_argument(
        "--auto_approve_above", type=float, default=None,
        help="Auto-approve predictions above this confidence threshold (0.0-1.0)",
    )
    parser.add_argument(
        "--batch_approve", action="store_true",
        help="Approve all pending entries without interactive review (use with caution)",
    )
    args = parser.parse_args()

    if args.batch_approve:
        batch_approve_all(manifest_path=args.manifest)
    else:
        interactive_review(
            manifest_path=args.manifest,
            output_dir=args.output_dir,
            auto_approve_threshold=args.auto_approve_above,
        )
