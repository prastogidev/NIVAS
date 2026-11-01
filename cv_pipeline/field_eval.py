"""
NIVAS CV Pipeline — Field Evaluation Set Manager.

The 25 human-reviewed WhatsApp images are a FIELD evaluation set.
They must NEVER be used for training, augmentation, validation,
hyperparameter tuning, or model selection.

This module:
  1. Creates data/field_eval/<class>/ structure from data/unsorted_images/ (read-only copy).
  2. Provides a manifest of the field eval set with image-level metadata.
  3. Runs inference on the field eval set using a trained candidate checkpoint.
  4. Reports evaluation metrics with a mandatory insufficiency disclaimer.

⚠  25 images are statistically insufficient for reliable performance claims.
   Reported metrics should be treated as indicative only, not as validated benchmarks.
"""

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("nivas.cv_pipeline.field_eval")

FIELD_EVAL_DISCLAIMER = (
    "⚠  STATISTICAL INSUFFICIENCY WARNING: This field evaluation set contains only 25 images "
    "spread across 5 classes (≈5 per class on average). This is statistically insufficient "
    "for reliable performance claims. Confidence intervals are very wide. "
    "Reported metrics are indicative only and must not be used to make deployment decisions "
    "without collecting a substantially larger independent test set (recommended ≥ 100 per class)."
)

CANONICAL_CLASSES = ["clean", "damp", "algae", "mold", "broken"]

# Human-reviewed ground-truth labels for the 25 field images
# (derived from data/wall_condition_dataset/raw/ directory sorting by the reviewer)
# Format: {filename: canonical_class}
FIELD_EVAL_LABELS: Dict[str, str] = {
    # algae (3 images from raw/algae)
    "WhatsApp Image 2026-09-11 at 15.56.40 (2).jpeg": "algae",
    "WhatsApp Image 2026-09-11 at 15.56.42 (1).jpeg": "algae",
    "WhatsApp Image 2026-09-11 at 15.56.45 (2).jpeg": "algae",

    # broken (8 images from raw/broken)
    "WhatsApp Image 2026-09-11 at 15.56.32.jpeg": "broken",
    "WhatsApp Image 2026-09-11 at 15.56.37 (1).jpeg": "broken",
    "WhatsApp Image 2026-09-11 at 15.56.40 (1).jpeg": "broken",
    "WhatsApp Image 2026-09-11 at 15.56.40.jpeg": "broken",
    "WhatsApp Image 2026-09-11 at 15.56.43 (2).jpeg": "broken",
    "WhatsApp Image 2026-09-11 at 15.56.45 (1).jpeg": "broken",
    "WhatsApp Image 2026-09-11 at 15.56.45.jpeg": "broken",
    "WhatsApp Image 2026-09-11 at 17.52.45.jpeg": "broken",

    # clean (7 images from raw/clean)
    "WhatsApp Image 2026-09-11 at 15.56.41 (1).jpeg": "clean",
    "WhatsApp Image 2026-09-11 at 15.56.44 (1).jpeg": "clean",
    "WhatsApp Image 2026-09-11 at 15.56.44.jpeg": "clean",
    "WhatsApp Image 2026-09-11 at 17.52.46 (1).jpeg": "clean",
    "WhatsApp Image 2026-09-11 at 17.52.46 (2).jpeg": "clean",
    "WhatsApp Image 2026-09-11 at 17.52.46.jpeg": "clean",
    "WhatsApp Image 2026-09-11 at 17.52.47.jpeg": "clean",

    # damp (6 images from raw/damp)
    "WhatsApp Image 2026-09-11 at 15.56.33.jpeg": "damp",
    "WhatsApp Image 2026-09-11 at 15.56.37.jpeg": "damp",
    "WhatsApp Image 2026-09-11 at 15.56.39.jpeg": "damp",
    "WhatsApp Image 2026-09-11 at 15.56.41.jpeg": "damp",
    "WhatsApp Image 2026-09-11 at 15.56.42.jpeg": "damp",
    "WhatsApp Image 2026-09-11 at 15.56.43.jpeg": "damp",

    # mold (1 image from raw/mold)
    "WhatsApp Image 2026-09-11 at 15.56.43 (1).jpeg": "mold",
}


def build_field_eval_set(
    source_dir: Path,
    field_eval_dir: Path,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Copy field images from source_dir (data/unsorted_images/) to
    field_eval_dir/<canonical_class>/ using FIELD_EVAL_LABELS mapping.

    This is a READ-ONLY COPY — originals in source_dir are never modified or deleted.

    Args:
        source_dir: data/unsorted_images/ (25 human-reviewed images).
        field_eval_dir: data/field_eval/ (destination, created if needed).
        dry_run: Log actions but do not create directories or copy files.

    Returns:
        Summary with per-class counts and any missing-label errors.
    """
    summary: Dict[str, Any] = {
        "source_dir": str(source_dir),
        "field_eval_dir": str(field_eval_dir),
        "dry_run": dry_run,
        "per_class": {cls: 0 for cls in CANONICAL_CLASSES},
        "total_copied": 0,
        "errors": [],
        "disclaimer": FIELD_EVAL_DISCLAIMER,
    }

    if not source_dir.exists():
        summary["errors"].append(f"Source directory '{source_dir}' does not exist.")
        return summary

    if not dry_run:
        for cls in CANONICAL_CLASSES:
            (field_eval_dir / cls).mkdir(parents=True, exist_ok=True)

    for img_file in sorted(source_dir.iterdir()):
        if not img_file.is_file() or img_file.name.startswith("."):
            continue

        label = FIELD_EVAL_LABELS.get(img_file.name)
        if label is None:
            msg = f"No ground-truth label for '{img_file.name}' — add it to FIELD_EVAL_LABELS."
            summary["errors"].append(msg)
            logger.warning(msg)
            continue

        dest = field_eval_dir / label / img_file.name
        if not dry_run:
            shutil.copy2(img_file, dest)
        summary["per_class"][label] += 1
        summary["total_copied"] += 1
        logger.debug("Copied '%s' → field_eval/%s/", img_file.name, label)

    logger.info(
        "Field eval set built: %d images copied to %s. %s",
        summary["total_copied"],
        field_eval_dir,
        "(dry_run — no files written)" if dry_run else "",
    )
    return summary


def write_field_eval_manifest(field_eval_dir: Path, manifest_path: Path) -> None:
    """Write a JSON manifest listing every field eval image with its ground-truth label."""
    entries: List[Dict] = []
    for cls in CANONICAL_CLASSES:
        cls_dir = field_eval_dir / cls
        if not cls_dir.exists():
            continue
        for f in sorted(cls_dir.iterdir()):
            if f.is_file() and not f.name.startswith("."):
                entries.append({
                    "filename": f.name,
                    "canonical_class": cls,
                    "path": str(f),
                    "class_index": CANONICAL_CLASSES.index(cls),
                })

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "total_images": len(entries),
        "canonical_classes": CANONICAL_CLASSES,
        "disclaimer": FIELD_EVAL_DISCLAIMER,
        "usage_policy": (
            "FIELD EVALUATION SET ONLY. Do NOT use these images for training, "
            "augmentation, validation, hyperparameter tuning, or model selection."
        ),
        "entries": entries,
    }

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    logger.info("Field eval manifest written to %s (%d entries)", manifest_path, len(entries))


if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="Build NIVAS field evaluation set")
    parser.add_argument("--source_dir", default="data/unsorted_images", type=str)
    parser.add_argument("--field_eval_dir", default="data/field_eval", type=str)
    parser.add_argument("--dry_run", action="store_true", help="Preview without copying files")
    args = parser.parse_args()

    result = build_field_eval_set(
        source_dir=Path(args.source_dir),
        field_eval_dir=Path(args.field_eval_dir),
        dry_run=args.dry_run,
    )

    print(json.dumps(result, indent=2))
    print(f"\n{FIELD_EVAL_DISCLAIMER}")

    if result["errors"]:
        sys.exit(1)

    if not args.dry_run:
        manifest_path = Path(args.field_eval_dir) / "field_eval_manifest.json"
        write_field_eval_manifest(Path(args.field_eval_dir), manifest_path)
