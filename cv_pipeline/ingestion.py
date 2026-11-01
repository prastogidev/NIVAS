"""
NIVAS CV Pipeline — Ingestion and Deduplication Engine.

Handles importing external datasets (Classification folders or YOLO annotation formats),
applying strict label mappings, deduplicating images (exact sha256 and perceptual hash),
preventing group/source leak across splits, and preparing the `data/wall_condition_dataset_v2`
split directories while keeping human-reviewed field evaluation images completely untouched.
"""

import hashlib
import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple

import numpy as np
from PIL import Image

from cv_pipeline.label_map import map_label, CANONICAL_CLASSES, EXCLUSION_REASONS
from backend.cv.preprocess import validate_and_load_image

logger = logging.getLogger("nivas.cv_pipeline.ingestion")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def compute_sha256(file_path: Path) -> str:
    """Compute sha256 hash of file content for exact deduplication."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_dhash(image: Image.Image, hash_size: int = 8) -> Optional[int]:
    """
    Compute difference hash (dHash) for perceptual near-duplicate detection.
    Resizes to (hash_size + 1, hash_size) grayscale, compares adjacent columns.
    Returns None for featureless / solid images to avoid false-positive collisions.
    """
    gray = image.convert("L")
    stat = np.array(gray)
    if float(np.std(stat)) < 1.0:
        # Near uniform / blank image — perceptual dhash is meaningless
        return None

    resized = gray.resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
    pixels = np.array(resized)
    diff = pixels[:, 1:] > pixels[:, :-1]
    return sum([bool(val) << i for i, val in enumerate(diff.flatten())])


def hamming_distance(h1: int, h2: int) -> int:
    """Compute Hamming distance between two 64-bit perceptual hashes."""
    return bin(h1 ^ h2).count("1")


class DatasetIngestionManager:
    """
    Orchestrates dataset acquisition ingestion, verification, deduplication,
    exclusion logging, and train/val/test assignment without leakage.
    """

    def __init__(
        self,
        output_dataset_dir: Path = Path("data/wall_condition_dataset_v2"),
        exclusion_log_path: Path = Path("data/wall_condition_dataset_v2/exclusions.jsonl"),
        metadata_log_path: Path = Path("data/wall_condition_dataset_v2/source_attribution.json"),
    ):
        self.output_dataset_dir = output_dataset_dir
        self.raw_dir = output_dataset_dir / "raw"
        self.exclusion_log_path = exclusion_log_path
        self.metadata_log_path = metadata_log_path

        self.exact_hashes: Set[str] = set()
        self.perceptual_hashes: List[Tuple[int, str]] = []  # (hash, filename)
        self.excluded_records: List[Dict[str, Any]] = []
        self.source_metadata: Dict[str, Any] = {}

    def log_exclusion(self, source_name: str, label: str, filename: str, reason: str):
        """Record an excluded image in the structured audit log."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_dataset": source_name,
            "source_label": label,
            "filename": filename,
            "reason": reason,
        }
        self.excluded_records.append(record)

    def is_duplicate(self, file_path: Path, img: Image.Image, threshold_distance: int = 2) -> Tuple[bool, str]:
        """
        Check if an image is an exact or perceptual near-duplicate.
        """
        # Exact hash check
        sha = compute_sha256(file_path)
        if sha in self.exact_hashes:
            return True, f"Exact SHA256 duplicate (hash: {sha[:12]}...)"

        # Perceptual hash check
        try:
            dhash = compute_dhash(img)
            if dhash is not None:
                for existing_hash, existing_name in self.perceptual_hashes:
                    if hamming_distance(dhash, existing_hash) <= threshold_distance:
                        return True, f"Near-duplicate of {existing_name} (hamming distance <= {threshold_distance})"
                self.perceptual_hashes.append((dhash, file_path.name))
        except Exception:
            pass

        self.exact_hashes.add(sha)
        return False, ""

    def save_exclusion_log(self):
        """Append exclusion records to jsonl."""
        if not self.excluded_records:
            return
        self.exclusion_log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.exclusion_log_path, "a", encoding="utf-8") as f:
            for rec in self.excluded_records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.excluded_records.clear()

    def save_source_metadata(self):
        """Save source attribution and license metadata."""
        self.metadata_log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.metadata_log_path, "w", encoding="utf-8") as f:
            json.dump(self.source_metadata, f, indent=2)

    def ingest_classification_folder(
        self,
        source_dir: Path,
        source_dataset_name: str,
        license_info: str,
        citation_info: str = "",
    ) -> Dict[str, int]:
        """
        Ingest an external dataset formatted in classification folders:
        source_dir/<class_label>/<images...>
        """
        stats = {"total_scanned": 0, "accepted": 0, "excluded": 0, "duplicates": 0, "errors": 0}
        self.source_metadata[source_dataset_name] = {
            "source_dir": str(source_dir),
            "format": "classification_folder",
            "license": license_info,
            "citation": citation_info,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }

        if not source_dir.exists():
            logger.error("Source directory %s does not exist.", source_dir)
            return stats

        for label_dir in sorted(source_dir.iterdir()):
            if not label_dir.is_dir() or label_dir.name.startswith("."):
                continue

            raw_label = label_dir.name
            try:
                canonical, exclusion_reason = map_label(raw_label, source_dataset_name)
            except ValueError as e:
                # Unknown class: cannot be silently mapped
                for img_file in label_dir.glob("*"):
                    if img_file.is_file() and not img_file.name.startswith("."):
                        stats["total_scanned"] += 1
                        stats["errors"] += 1
                        self.log_exclusion(source_dataset_name, raw_label, img_file.name, str(e))
                continue

            if canonical is None:
                for img_file in label_dir.glob("*"):
                    if img_file.is_file() and not img_file.name.startswith("."):
                        stats["total_scanned"] += 1
                        stats["excluded"] += 1
                        self.log_exclusion(source_dataset_name, raw_label, img_file.name, exclusion_reason)
                continue

            # Accepted class
            target_class_dir = self.raw_dir / canonical
            target_class_dir.mkdir(parents=True, exist_ok=True)

            for img_file in sorted(label_dir.glob("*")):
                if not img_file.is_file() or img_file.name.startswith(".") or img_file.suffix.lower() not in IMAGE_EXTENSIONS:
                    continue

                stats["total_scanned"] += 1
                valid, err, pil_img = validate_and_load_image(img_file)
                if not valid or pil_img is None:
                    stats["errors"] += 1
                    self.log_exclusion(source_dataset_name, raw_label, img_file.name, f"Corrupted or invalid: {err}")
                    continue

                # Deduplication check
                is_dup, dup_reason = self.is_duplicate(img_file, pil_img)
                if is_dup:
                    stats["duplicates"] += 1
                    self.log_exclusion(source_dataset_name, raw_label, img_file.name, dup_reason)
                    continue

                # Copy with prefix to avoid collision
                dest_filename = f"{source_dataset_name}_{img_file.name}"
                dest_path = target_class_dir / dest_filename
                shutil.copy2(img_file, dest_path)
                stats["accepted"] += 1

        self.save_exclusion_log()
        self.save_source_metadata()
        return stats

    def ingest_yolo_dataset(
        self,
        source_dir: Path,
        source_dataset_name: str,
        license_info: str,
        citation_info: str = "",
    ) -> Dict[str, int]:
        """
        Safely import a YOLO object detection dataset into whole-image classification classes.

        Rules:
        - If an image has annotations of multiple different classes, do not guess -> exclude with reason.
        - If an image has 0 annotations, DO NOT assume clean -> exclude with reason 'empty_annotations_unverified'.
        - If an image has annotations for a single recognized class -> crop or map image to canonical class.
        """
        stats = {"total_scanned": 0, "accepted": 0, "excluded": 0, "duplicates": 0, "errors": 0}
        self.source_metadata[source_dataset_name] = {
            "source_dir": str(source_dir),
            "format": "yolo_object_detection",
            "license": license_info,
            "citation": citation_info,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }

        # Parse data.yaml for class names
        yaml_path = source_dir / "data.yaml"
        if not yaml_path.exists():
            logger.error("Missing data.yaml in YOLO dataset directory %s", source_dir)
            return stats

        import yaml
        with open(yaml_path, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)

        names = yaml_data.get("names", [])
        if isinstance(names, dict):
            class_names = [names[k] for k in sorted(names.keys())]
        else:
            class_names = names

        # Look for images and labels in all subdirectories (train, valid, test)
        for split in ["train", "valid", "val", "test", ""]:
            img_dir = source_dir / split / "images" if split else source_dir / "images"
            lbl_dir = source_dir / split / "labels" if split else source_dir / "labels"

            if not img_dir.exists():
                continue

            for img_file in sorted(img_dir.glob("*")):
                if not img_file.is_file() or img_file.name.startswith(".") or img_file.suffix.lower() not in IMAGE_EXTENSIONS:
                    continue

                stats["total_scanned"] += 1
                txt_file = lbl_dir / f"{img_file.stem}.txt" if lbl_dir.exists() else None

                if not txt_file or not txt_file.exists() or txt_file.stat().st_size == 0:
                    stats["excluded"] += 1
                    self.log_exclusion(
                        source_dataset_name,
                        "unannotated",
                        img_file.name,
                        "Excluded: Image has 0 bounding boxes. Empty annotations cannot be assumed clean.",
                    )
                    continue

                # Read box labels
                with open(txt_file, "r") as f:
                    lines = [l.strip().split() for l in f if l.strip()]

                if not lines:
                    stats["excluded"] += 1
                    self.log_exclusion(
                        source_dataset_name,
                        "unannotated",
                        img_file.name,
                        "Excluded: Image has 0 bounding boxes.",
                    )
                    continue

                class_indices = set(int(l[0]) for l in lines)
                if len(class_indices) > 1:
                    # Multi-label defect: ambiguous single-label classification
                    detected_labels = [class_names[idx] for idx in class_indices if idx < len(class_names)]
                    stats["excluded"] += 1
                    self.log_exclusion(
                        source_dataset_name,
                        "+".join(detected_labels),
                        img_file.name,
                        f"Excluded: Multiple defect classes detected ({detected_labels}). Ambiguous for 5-class single-label classification.",
                    )
                    continue

                single_idx = list(class_indices)[0]
                if single_idx >= len(class_names):
                    stats["errors"] += 1
                    self.log_exclusion(source_dataset_name, f"index_{single_idx}", img_file.name, "Index out of range in data.yaml")
                    continue

                raw_label = class_names[single_idx]
                try:
                    canonical, exclusion_reason = map_label(raw_label, source_dataset_name)
                except ValueError as e:
                    stats["errors"] += 1
                    self.log_exclusion(source_dataset_name, raw_label, img_file.name, str(e))
                    continue

                if canonical is None:
                    stats["excluded"] += 1
                    self.log_exclusion(source_dataset_name, raw_label, img_file.name, exclusion_reason)
                    continue

                valid, err, pil_img = validate_and_load_image(img_file)
                if not valid or pil_img is None:
                    stats["errors"] += 1
                    self.log_exclusion(source_dataset_name, raw_label, img_file.name, f"Corrupted or invalid: {err}")
                    continue

                is_dup, dup_reason = self.is_duplicate(img_file, pil_img)
                if is_dup:
                    stats["duplicates"] += 1
                    self.log_exclusion(source_dataset_name, raw_label, img_file.name, dup_reason)
                    continue

                target_class_dir = self.raw_dir / canonical
                target_class_dir.mkdir(parents=True, exist_ok=True)
                dest_filename = f"{source_dataset_name}_{img_file.name}"
                dest_path = target_class_dir / dest_filename
                shutil.copy2(img_file, dest_path)
                stats["accepted"] += 1

        self.save_exclusion_log()
        self.save_source_metadata()
        return stats
