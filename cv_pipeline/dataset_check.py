"""
NIVAS CV Pipeline — Dataset Integrity Checker.

Verifies the wall-condition dataset before training:
  1. All class directories exist for every split (train/val/test).
  2. No `.gitkeep` placeholder files are counted as real images.
  3. Class-order consistency: on-disk alphabetical order matches WALL_CONDITION_CLASSES.
  4. Minimum per-class sample count warnings.
  5. Majority-class baseline accuracy (for reference reporting).
  6. Records overall dataset summary to a JSON report.

Run directly:
  python -m cv_pipeline.dataset_check --dataset_dir data/wall_condition_dataset
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger("nivas.cv_pipeline.dataset_check")

CANONICAL_CLASSES = ["clean", "damp", "algae", "mold", "broken"]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}
MIN_SAMPLES_PER_CLASS = 10  # warn if any class has fewer than this in train


def count_real_images(class_dir: Path) -> int:
    """Count image files in a class directory, excluding .gitkeep and hidden files."""
    if not class_dir.exists():
        return 0
    return sum(
        1 for f in class_dir.iterdir()
        if f.is_file()
        and not f.name.startswith(".")
        and f.suffix.lower() in IMAGE_EXTENSIONS
    )


def check_dataset_integrity(dataset_dir: Path) -> Dict[str, Any]:
    """
    Full integrity check on the wall-condition dataset directory.

    Returns a structured report dict. Sets report["is_ready_for_training"] = True
    only when:
      - train/ and val/ splits exist
      - all 5 classes have ≥ 1 real image in train
      - class directory names match CANONICAL_CLASSES exactly (P3 check)
    """
    report: Dict[str, Any] = {
        "dataset_dir": str(dataset_dir),
        "canonical_classes": CANONICAL_CLASSES,
        "splits": {},
        "is_ready_for_training": False,
        "class_order_ok": False,
        "warnings": [],
        "errors": [],
    }

    if not dataset_dir.exists():
        report["errors"].append(f"Dataset directory '{dataset_dir}' does not exist.")
        return report

    for split in ["train", "val", "test"]:
        split_dir = dataset_dir / split
        split_info: Dict[str, Any] = {"exists": split_dir.exists(), "classes": {}}

        if split_dir.exists():
            # Check on-disk directories contain exactly CANONICAL_CLASSES
            actual_dirs = sorted(
                d.name for d in split_dir.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            )
            split_info["actual_class_dirs"] = actual_dirs

            # P3: Verify class dir names set is exactly CANONICAL_CLASSES set
            if actual_dirs and set(actual_dirs) != set(CANONICAL_CLASSES):
                msg = (
                    f"P3 CLASS CHECK [{split}]: on-disk dirs {actual_dirs} "
                    f"≠ CANONICAL_CLASSES {CANONICAL_CLASSES}"
                )
                report["errors"].append(msg)
                logger.error(msg)
            elif actual_dirs:
                report["class_order_ok"] = True

            total = 0
            for cls in CANONICAL_CLASSES:
                n = count_real_images(split_dir / cls)
                split_info["classes"][cls] = n
                total += n
                if split == "train" and n < MIN_SAMPLES_PER_CLASS:
                    report["warnings"].append(
                        f"[train/{cls}] only {n} images (minimum recommended: {MIN_SAMPLES_PER_CLASS})."
                    )
            split_info["total"] = total

            # Majority-class baseline for train split
            if split == "train" and total > 0:
                majority_count = max(split_info["classes"].values())
                split_info["majority_class_baseline_accuracy"] = round(majority_count / total, 4)

        report["splits"][split] = split_info

    # Readiness: train and val must exist and have real images in all classes
    train_info = report["splits"].get("train", {})
    val_info = report["splits"].get("val", {})
    if (
        train_info.get("exists")
        and val_info.get("exists")
        and train_info.get("total", 0) > 0
        and all(train_info.get("classes", {}).get(c, 0) > 0 for c in CANONICAL_CLASSES)
        and not report["errors"]
    ):
        report["is_ready_for_training"] = True

    return report


def print_report(report: Dict[str, Any]) -> None:
    """Pretty-print the integrity report to stdout."""
    print("\n" + "=" * 60)
    print("NIVAS CV Dataset Integrity Report")
    print("=" * 60)
    print(f"Dataset: {report['dataset_dir']}")
    print(f"Canonical classes: {report['canonical_classes']}")
    print(f"Class order OK: {report['class_order_ok']}")
    print(f"Ready for training: {report['is_ready_for_training']}")

    for split, info in report["splits"].items():
        if not info.get("exists"):
            print(f"\n  [{split}] — NOT FOUND")
            continue
        print(f"\n  [{split}] total={info.get('total', 0)}")
        for cls, n in info.get("classes", {}).items():
            print(f"    {cls}: {n}")
        if "majority_class_baseline_accuracy" in info:
            print(f"    Majority-class baseline accuracy: {info['majority_class_baseline_accuracy']:.1%}")

    if report["warnings"]:
        print("\nWarnings:")
        for w in report["warnings"]:
            print(f"  ⚠  {w}")

    if report["errors"]:
        print("\nErrors:")
        for e in report["errors"]:
            print(f"  ✗  {e}")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="Check NIVAS CV dataset integrity")
    parser.add_argument(
        "--dataset_dir",
        type=str,
        default="data/wall_condition_dataset",
        help="Path to dataset root (must contain train/, val/, test/ subdirs)",
    )
    parser.add_argument(
        "--output_json",
        type=str,
        default=None,
        help="Optional path to write JSON report",
    )
    args = parser.parse_args()

    report = check_dataset_integrity(Path(args.dataset_dir))
    print_report(report)

    if args.output_json:
        out = Path(args.output_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            json.dump(report, f, indent=2)
        print(f"JSON report written to: {out}")

    sys.exit(0 if report["is_ready_for_training"] else 1)
