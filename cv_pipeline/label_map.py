"""
NIVAS CV Pipeline — Dataset Label Mapping and Integrity Check.

Maps raw dataset labels from external sources to the canonical 5-class
NIVAS schema and records every excluded image with its reason.

Approved label mappings (from design review):
  wall_crack     → broken
  spalling       → broken
  algae          → algae
  damp           → damp
  efflorescence  → damp
  fungus         → mold
  peeling        → EXCLUDED (ambiguous; not representative)
  electrical_fault → EXCLUDED (out-of-scope for wall condition)

Exclusion policy:
  - Mendeley concrete images: EXCLUDED — not representative of real residential walls.
  - peeling: EXCLUDED — semantically ambiguous.
  - electrical_fault: EXCLUDED — out of scope.

Every excluded image and its reason are recorded in the exclusion log.
Unknown/unmapped classes are never silently mapped; they are rejected with an error.
"""

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("nivas.cv_pipeline.label_map")

# ---------------------------------------------------------------------------
# Canonical NIVAS class schema (must match WALL_CONDITION_CLASSES in model.py)
# Order: clean, damp, algae, mold, broken
# ---------------------------------------------------------------------------
CANONICAL_CLASSES = ["clean", "damp", "algae", "mold", "broken"]

# ---------------------------------------------------------------------------
# Approved label mapping (source_label -> canonical_label | None = exclude)
# ---------------------------------------------------------------------------
LABEL_MAP: Dict[str, Optional[str]] = {
    # Direct pass-through
    "algae": "algae",
    "clean": "clean",
    "damp": "damp",
    "mold": "mold",
    "broken": "broken",

    # Mapped labels from external datasets (Wall FDobo, Wall Quality Detection, House-Wall-Damage)
    "wall_crack": "broken",
    "crack": "broken",
    "cracks": "broken",
    "spalling": "broken",
    "efflorescence": "damp",
    "fungus": "mold",
    "mildew": "mold",
    "normal": "clean",
    "undamaged": "clean",

    # Excluded labels (value = None means "exclude with reason")
    "peeling": None,               # Ambiguous; not representative
    "electrical_fault": None,      # Out of scope for wall-condition classifier
    "hollowing": None,             # Sub-surface acoustic defect, cannot be reliably classified visually
    "overlap": None,               # Annotation artifact / color overlap, ambiguous defect
    "crackdamp": None,             # Mixed/composite defect, violates clean single-defect boundary
}

# Reasons for exclusion (used in the exclusion log)
EXCLUSION_REASONS: Dict[str, str] = {
    "peeling": "Excluded: 'peeling' is semantically ambiguous and not representative of the target defect categories.",
    "electrical_fault": "Excluded: out of scope for wall-condition classifier (electrical hazards are not a wall surface defect).",
    "hollowing": "Excluded: 'hollowing' is a sub-surface hollow drum acoustic defect, unrepresentative of visual surface wall defects.",
    "overlap": "Excluded: 'overlap' is an annotation artifact / color overlap rather than a standard wall condition defect.",
    "crackdamp": "Excluded: 'crackdamp' is a composite multi-class label (crack + damp); cannot be cleanly mapped to single-defect class.",
    "_mendeley_concrete": "Excluded: Mendeley concrete dataset images are not representative of real residential walls.",
    "_unknown_class": "Excluded: unrecognised source label — silent mapping is prohibited.",
}


def map_label(source_label: str, source_dataset: str = "") -> Tuple[Optional[str], Optional[str]]:
    """
    Map a source dataset label to the canonical NIVAS class.

    Args:
        source_label: Raw label string from the source dataset.
        source_dataset: Name of the source dataset (used to flag Mendeley images).

    Returns:
        (canonical_class, exclusion_reason)
        - If mapped successfully: (canonical_class, None)
        - If excluded by policy:  (None, reason_string)
        - If unknown:             raises ValueError (no silent mapping)

    Raises:
        ValueError: when the source_label is not in LABEL_MAP and is not a known
                    exclusion. Unknown classes are never silently mapped.
    """
    # Mendeley concrete dataset: exclude all regardless of label
    if "mendeley" in source_dataset.lower() or "mendeley" in source_label.lower():
        return None, EXCLUSION_REASONS["_mendeley_concrete"]

    norm = source_label.strip().lower().replace(" ", "_").replace("-", "_")

    if norm not in LABEL_MAP:
        raise ValueError(
            f"Unknown source label '{source_label}' from dataset '{source_dataset}'. "
            "Silent mapping is prohibited. Add this label to LABEL_MAP explicitly "
            "or classify it as an exclusion with a documented reason."
        )

    canonical = LABEL_MAP[norm]
    if canonical is None:
        reason = EXCLUSION_REASONS.get(norm, f"Excluded: label '{norm}' is in the exclusion list.")
        return None, reason

    return canonical, None


def apply_label_mapping(
    source_dir: Path,
    target_raw_dir: Path,
    exclusion_log_path: Path,
    source_dataset_name: str = "unknown",
    dry_run: bool = False,
) -> Dict[str, int]:
    """
    Walk source_dir, apply label mapping, copy accepted images to target_raw_dir/<canonical_class>/,
    and write every excluded image + reason to exclusion_log_path (JSONL format).

    Args:
        source_dir: Root of the source dataset. Expected structure:
                    source_dir/<source_label>/<image_files>
        target_raw_dir: Destination. Will create target_raw_dir/<canonical_class>/.
        exclusion_log_path: File where excluded image records are appended (JSONL).
        source_dataset_name: Dataset identifier for the exclusion log.
        dry_run: If True, log actions but do not copy files or write logs.

    Returns:
        Summary counts: {"accepted": N, "excluded": N, "errors": N, **per_canonical_class_counts}
    """
    counts: Dict[str, int] = {"accepted": 0, "excluded": 0, "errors": 0}
    for cls in CANONICAL_CLASSES:
        counts[cls] = 0

    exclusion_records: List[Dict] = []

    if not source_dir.exists():
        logger.error("Source directory '%s' does not exist.", source_dir)
        return counts

    if not dry_run:
        for cls in CANONICAL_CLASSES:
            (target_raw_dir / cls).mkdir(parents=True, exist_ok=True)

    for source_label_dir in sorted(source_dir.iterdir()):
        if not source_label_dir.is_dir():
            continue

        source_label = source_label_dir.name

        try:
            canonical, exclusion_reason = map_label(source_label, source_dataset_name)
        except ValueError as exc:
            logger.error("Label mapping error: %s", exc)
            # Record every file under this unknown label as an error
            for img_file in source_label_dir.glob("*"):
                if img_file.is_file() and not img_file.name.startswith("."):
                    exclusion_records.append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "source_dataset": source_dataset_name,
                        "source_label": source_label,
                        "filename": img_file.name,
                        "reason": EXCLUSION_REASONS["_unknown_class"] + f" Detail: {exc}",
                    })
                    counts["errors"] += 1
            continue

        if canonical is None:
            # Excluded by policy — record every image
            for img_file in sorted(source_label_dir.glob("*")):
                if img_file.is_file() and not img_file.name.startswith("."):
                    exclusion_records.append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "source_dataset": source_dataset_name,
                        "source_label": source_label,
                        "filename": img_file.name,
                        "reason": exclusion_reason,
                    })
                    counts["excluded"] += 1
            logger.info(
                "Excluded all %d images with label '%s': %s",
                counts["excluded"], source_label, exclusion_reason,
            )
            continue

        # Accepted — copy to target
        image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}
        for img_file in sorted(source_label_dir.glob("*")):
            if not img_file.is_file() or img_file.suffix.lower() not in image_extensions:
                continue
            if img_file.name.startswith("."):
                continue

            dest = target_raw_dir / canonical / img_file.name
            # Avoid overwriting (append _1, _2 suffix if name conflicts)
            stem, suffix = img_file.stem, img_file.suffix
            counter = 1
            while dest.exists() and not dry_run:
                dest = target_raw_dir / canonical / f"{stem}_{counter}{suffix}"
                counter += 1

            if not dry_run:
                shutil.copy2(img_file, dest)

            counts["accepted"] += 1
            counts[canonical] += 1
            logger.debug("Copied %s/%s → %s/%s", source_label, img_file.name, canonical, dest.name)

    # Write exclusion log (JSONL, append mode)
    if exclusion_records and not dry_run:
        exclusion_log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(exclusion_log_path, "a", encoding="utf-8") as fh:
            for record in exclusion_records:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        logger.info("Wrote %d exclusion records to %s", len(exclusion_records), exclusion_log_path)

    logger.info(
        "Label mapping complete for '%s': accepted=%d, excluded=%d, errors=%d",
        source_dataset_name, counts["accepted"], counts["excluded"], counts["errors"],
    )
    return counts
