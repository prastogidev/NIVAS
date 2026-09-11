"""
NIVAS Dataset Auto-Sorting Utility.

Uses the existing EfficientNet-B0 CV inference pipeline to predict wall-condition
classes for unlabeled property images. Copies each image into a *proposed* class
folder under data/wall_condition_dataset/raw/ and writes a manifest for human review.

Workflow & Safety Rules:
1. For each unlabeled image in data/unsorted_images/:
   - Validates image integrity.
   - Checks for duplicates against already-sorted images.
   - Runs model inference to get class probabilities (clean, damp, algae, mold, broken).
   - Copies image to proposed raw class directory without overwriting.
   - Verifies destination copy exists, is non-empty, and valid.
2. Manifest is written to disk recording original filename, path, prediction, and pending status.
3. Only AFTER inference, copy, verification, and manifest write ALL succeed:
   - Deletes original image from data/unsorted_images/ (unless --keep-source is provided).
4. NEVER deletes source image if:
   - inference fails
   - image is invalid/corrupted
   - destination copy fails
   - destination file cannot be verified
   - manifest cannot be written
   - image is detected as a duplicate
   - any unexpected exception occurs
5. Safety check: NEVER deletes any file outside data/unsorted_images/.
6. Copied images remain review_status = 'pending'. Auto-sorting does NOT approve labels.
"""

import json
import hashlib
import logging
import shutil
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from backend.cv.model import build_efficientnet_b0, get_eval_transforms, WALL_CONDITION_CLASSES
from backend.cv.preprocess import validate_and_load_image

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("nivas.cv.auto_sort")

MODEL_WEIGHTS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "models" / "wall_condition_efficientnet.pth"
DEFAULT_INPUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "unsorted_images"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "wall_condition_dataset" / "raw"
DEFAULT_MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "wall_condition_dataset" / "sort_manifest.json"

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}


def _file_sha256(filepath: Path) -> str:
    """Compute SHA-256 hash of file contents for duplicate detection."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_model(device: torch.device) -> torch.nn.Module:
    """Load the EfficientNet-B0 model using the same logic as the production inference service."""
    if MODEL_WEIGHTS_PATH.exists():
        model = build_efficientnet_b0(num_classes=len(WALL_CONDITION_CLASSES), pretrained=False)
        state_dict = torch.load(MODEL_WEIGHTS_PATH, map_location=device)
        model.load_state_dict(state_dict)
        logger.info("Loaded fine-tuned checkpoint from %s", MODEL_WEIGHTS_PATH)
    else:
        model = build_efficientnet_b0(num_classes=len(WALL_CONDITION_CLASSES), pretrained=True)
        logger.info(
            "No fine-tuned checkpoint at %s. Using pretrained EfficientNet-B0 backbone "
            "(predictions may be unreliable — human review is essential).",
            MODEL_WEIGHTS_PATH,
        )

    model.to(device)
    model.eval()
    return model


def _predict_single(
    model: torch.nn.Module,
    transform,
    img: Image.Image,
    device: torch.device,
) -> Dict[str, Any]:
    """Run single-image inference and return class probabilities."""
    input_tensor = transform(img).unsqueeze(0).to(device)

    with torch.no_grad():
        outputs = model(input_tensor)
        probs = F.softmax(outputs, dim=1).squeeze(0).cpu().tolist()

    prob_dict = {cls: round(p, 4) for cls, p in zip(WALL_CONDITION_CLASSES, probs)}
    top_idx = int(np.argmax(probs))
    predicted_class = WALL_CONDITION_CLASSES[top_idx]
    confidence = round(float(probs[top_idx]), 4)

    return {
        "predicted_class": predicted_class,
        "confidence": confidence,
        "class_probabilities": prob_dict,
    }


def auto_sort_images(
    input_dir: str = str(DEFAULT_INPUT_DIR),
    output_dir: str = str(DEFAULT_OUTPUT_DIR),
    manifest_path: str = str(DEFAULT_MANIFEST_PATH),
    dry_run: bool = False,
    keep_source: bool = False,
    device_name: str = "auto",
) -> Dict[str, Any]:
    """
    Scans input_dir for unlabeled images, predicts wall-condition class for each,
    copies them into proposed class folders, and writes a review manifest.

    When keep_source is False (default) and dry_run is False:
    Successfully verified images are removed from input_dir ONLY AFTER:
    1. Inference succeeds
    2. Destination copy succeeds
    3. Destination file exists, is non-empty, and is verified readable
    4. Manifest is successfully saved to disk

    Args:
        input_dir: Directory containing unlabeled images.
        output_dir: Base directory for class folders (e.g. data/wall_condition_dataset/raw/).
        manifest_path: Path to write the sorting manifest JSON.
        dry_run: If True, predict classes but do not copy or delete files.
        keep_source: If True, preserve source images in input_dir instead of deleting them.
        device_name: Compute device ('auto', 'cpu', 'cuda', 'mps').

    Returns:
        Summary dict with counts and manifest entries.
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    manifest_file = Path(manifest_path)

    if not input_path.exists():
        logger.error("Input directory '%s' does not exist.", input_dir)
        logger.info(
            "Create the directory and place your unlabeled property images there:\n"
            "  mkdir -p %s\n"
            "  cp /path/to/your/images/*.jpg %s/",
            input_dir, input_dir,
        )
        return {"status": "error", "message": f"Input directory '{input_dir}' does not exist."}

    # Discover image files
    image_files = sorted([
        f for f in input_path.iterdir()
        if f.is_file()
        and f.suffix.lower() in SUPPORTED_EXTENSIONS
        and not f.name.startswith(".")
    ])

    if not image_files:
        logger.warning("No image files found in '%s'.", input_dir)
        return {"status": "empty", "message": f"No image files found in '{input_dir}'."}

    logger.info("Found %d image files in '%s'.", len(image_files), input_dir)

    # Create output class directories
    for cls in WALL_CONDITION_CLASSES:
        (output_path / cls).mkdir(parents=True, exist_ok=True)

    # Select device
    if device_name == "auto":
        device = torch.device(
            "cuda" if torch.cuda.is_available()
            else "mps" if torch.backends.mps.is_available()
            else "cpu"
        )
    else:
        device = torch.device(device_name)

    # Load model and transforms
    model = _load_model(device)
    transform = get_eval_transforms()

    # Track duplicates by hash across all existing raw class folders
    existing_hashes: Dict[str, str] = {}
    for cls in WALL_CONDITION_CLASSES:
        cls_dir = output_path / cls
        for existing_file in cls_dir.glob("*"):
            if existing_file.is_file() and not existing_file.name.startswith("."):
                existing_hashes[_file_sha256(existing_file)] = str(existing_file)

    # Process each image
    manifest_entries: List[Dict[str, Any]] = []
    counts = {cls: 0 for cls in WALL_CONDITION_CLASSES}
    skipped_invalid = 0
    skipped_duplicate = 0
    failed_inference = 0
    failed_copy = 0

    # Track candidates for source cleanup: (src_path, dst_path, entry)
    successful_sources_to_remove: List[Tuple[Path, Path, Dict[str, Any]]] = []

    for img_path in image_files:
        entry: Dict[str, Any] = {
            "original_filename": img_path.name,
            "original_path": str(img_path.resolve()),
            "source_removed": False,
        }

        # Step 1: Validate image
        valid, err_msg, img = validate_and_load_image(img_path)
        if not valid or img is None:
            logger.warning("Skipping invalid image '%s': %s", img_path.name, err_msg)
            entry["status"] = "skipped_invalid"
            entry["error"] = err_msg
            manifest_entries.append(entry)
            skipped_invalid += 1
            continue

        # Step 2: Duplicate check
        file_hash = _file_sha256(img_path)
        entry["sha256"] = file_hash
        if file_hash in existing_hashes:
            logger.info(
                "Skipping duplicate '%s' (identical to '%s').",
                img_path.name, existing_hashes[file_hash],
            )
            entry["status"] = "skipped_duplicate"
            entry["duplicate_of"] = existing_hashes[file_hash]
            manifest_entries.append(entry)
            skipped_duplicate += 1
            continue

        # Step 3: Run inference
        try:
            prediction = _predict_single(model, transform, img, device)
            entry.update(prediction)
        except Exception as inf_err:
            logger.error("Inference failed for '%s': %s", img_path.name, inf_err)
            entry["status"] = "failed_inference"
            entry["error"] = str(inf_err)
            manifest_entries.append(entry)
            failed_inference += 1
            continue

        entry["review_status"] = "pending"  # Must be reviewed by human
        entry["corrected_class"] = None  # Will be set during review

        predicted_cls = prediction["predicted_class"]

        # Step 4: Determine destination filename (avoid overwriting)
        dest_dir = output_path / predicted_cls
        dest_file = dest_dir / img_path.name
        if dest_file.exists():
            stem = img_path.stem
            suffix = img_path.suffix
            counter = 1
            while dest_file.exists():
                dest_file = dest_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        entry["sorted_path"] = str(dest_file.resolve())

        # Step 5: Copy and verify
        if not dry_run:
            try:
                shutil.copy2(img_path, dest_file)

                # Strict destination verification: exists, non-empty, and loadable
                if not dest_file.exists() or dest_file.stat().st_size == 0:
                    raise IOError(f"Destination file '{dest_file}' missing or 0 bytes after copy.")
                valid_dest, dest_err, _ = validate_and_load_image(dest_file)
                if not valid_dest:
                    raise IOError(f"Destination file '{dest_file}' failed verification: {dest_err}")

                entry["status"] = "sorted"
                existing_hashes[file_hash] = str(dest_file)
                counts[predicted_cls] += 1
                successful_sources_to_remove.append((img_path, dest_file, entry))
                logger.info(
                    "Copied '%s' -> %s/%s (predicted=%s, confidence=%.2f%%)",
                    img_path.name, predicted_cls, dest_file.name,
                    predicted_cls, prediction["confidence"] * 100,
                )
            except Exception as copy_err:
                logger.error("Failed to copy/verify '%s' -> '%s': %s", img_path.name, dest_file, copy_err)
                entry["status"] = "failed_copy"
                entry["error"] = str(copy_err)
                failed_copy += 1
                manifest_entries.append(entry)
                continue
        else:
            entry["status"] = "dry_run"
            counts[predicted_cls] += 1
            logger.info(
                "[DRY RUN] Would copy '%s' -> %s/%s (predicted=%s, confidence=%.2f%%)",
                img_path.name, predicted_cls, dest_file.name,
                predicted_cls, prediction["confidence"] * 100,
            )

        manifest_entries.append(entry)

    # Check if fine-tuned checkpoint was used
    has_finetuned = MODEL_WEIGHTS_PATH.exists()

    # Build summary
    total_failed = skipped_invalid + failed_inference + failed_copy
    summary: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_directory": str(input_path.resolve()),
        "output_directory": str(output_path.resolve()),
        "model_checkpoint": str(MODEL_WEIGHTS_PATH) if has_finetuned else "pretrained_backbone_only",
        "warning": (
            "These labels are MODEL PREDICTIONS, not ground truth. "
            "You MUST review and correct them before using as training data. "
            + ("No fine-tuned checkpoint was found — predictions use the pretrained backbone "
               "and are likely unreliable. Human review is essential."
               if not has_finetuned else "")
        ),
        "total_images_found": len(image_files),
        "sorted_count": sum(counts.values()),
        "source_images_removed": 0,
        "failed_count": total_failed,
        "duplicate_count": skipped_duplicate,
        "pending_review_count": sum(counts.values()),
        "keep_source": keep_source,
        "dry_run": dry_run,
        "class_distribution": counts,
        "entries": manifest_entries,
    }

    # Step 6: Write manifest to disk
    # This MUST succeed before any source image is deleted!
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_manifest = manifest_file.with_suffix(".json.tmp")
    with open(tmp_manifest, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    tmp_manifest.replace(manifest_file)
    logger.info("Manifest written to: %s", manifest_file)

    # Step 7: Delete original source images ONLY after copy, verification, and manifest write succeed
    source_removed_count = 0
    if not dry_run and not keep_source:
        input_resolved = input_path.resolve()
        output_resolved = output_path.resolve()

        for src_path, dst_path, entry in successful_sources_to_remove:
            try:
                src_resolved = src_path.resolve()

                # Safety check 1: File must exist
                if not src_resolved.exists():
                    continue

                # Safety check 2: File must be strictly inside input_dir
                if not src_resolved.is_relative_to(input_resolved):
                    logger.warning(
                        "Safety violation: '%s' is not within input directory '%s'. Refusing to delete.",
                        src_resolved, input_resolved,
                    )
                    continue

                # Safety check 3: File must NOT be inside output_dir
                if src_resolved.is_relative_to(output_resolved):
                    logger.warning(
                        "Safety violation: '%s' is within output directory '%s'. Refusing to delete.",
                        src_resolved, output_resolved,
                    )
                    continue

                # Safety check 4: Destination must exist and be non-empty
                if not dst_path.exists() or dst_path.stat().st_size == 0:
                    logger.warning(
                        "Safety check failed: destination '%s' missing or empty. Preserving source '%s'.",
                        dst_path, src_resolved,
                    )
                    continue

                # Perform safe removal
                src_resolved.unlink()
                entry["source_removed"] = True
                source_removed_count += 1
                logger.info("Removed source image: %s", src_resolved.name)
            except Exception as del_err:
                logger.warning("Could not remove source image '%s': %s", src_path.name, del_err)

        # Update summary with removal count and re-save manifest
        summary["source_images_removed"] = source_removed_count
        with open(tmp_manifest, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        tmp_manifest.replace(manifest_file)

    # Step 8: Print clean, standardized summary
    logger.info("=== Auto-Sort Summary ===")
    logger.info("Total images found: %d", len(image_files))
    logger.info("Successfully sorted: %d", sum(counts.values()))
    logger.info(
        "Source images removed: %d%s",
        source_removed_count,
        " (keep-source enabled)" if keep_source else (" (dry-run)" if dry_run else ""),
    )
    logger.info("Failed: %d", total_failed)
    logger.info("Duplicates: %d", skipped_duplicate)
    logger.info("Pending review: %d", sum(counts.values()))
    for cls, cnt in counts.items():
        logger.info("  %s: %d images", cls, cnt)

    if not has_finetuned:
        logger.warning(
            "⚠ No fine-tuned checkpoint found. Predictions are from the pretrained backbone. "
            "Review ALL labels carefully before treating them as training data."
        )
    logger.info(
        "Next step: Review the manifest at '%s' and run:\n"
        "  PYTHONPATH=. backend/venv/bin/python -m backend.cv.review_sort",
        manifest_file,
    )

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Auto-sort unlabeled property images into wall-condition class folders using CV model predictions."
    )
    parser.add_argument(
        "--input_dir", type=str, default=str(DEFAULT_INPUT_DIR),
        help="Directory containing unlabeled images (default: data/unsorted_images/)",
    )
    parser.add_argument(
        "--output_dir", type=str, default=str(DEFAULT_OUTPUT_DIR),
        help="Base directory for class folders (default: data/wall_condition_dataset/raw/)",
    )
    parser.add_argument(
        "--manifest", type=str, default=str(DEFAULT_MANIFEST_PATH),
        help="Path to write the sorting manifest JSON",
    )
    parser.add_argument(
        "--dry_run", action="store_true",
        help="Predict classes but do not copy files or delete source images",
    )
    parser.add_argument(
        "--keep-source", dest="keep_source", action="store_true", default=False,
        help="Preserve source images in input_dir instead of deleting after successful sort (useful for testing/debugging)",
    )
    parser.add_argument(
        "--device", type=str, default="auto",
        help="Compute device ('auto', 'cpu', 'cuda', 'mps')",
    )
    args = parser.parse_args()

    auto_sort_images(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        manifest_path=args.manifest,
        dry_run=args.dry_run,
        keep_source=args.keep_source,
        device_name=args.device,
    )
