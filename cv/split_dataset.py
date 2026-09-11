"""
Dataset Splitting Utility for NIVAS Computer Vision Property-Condition Classifier.

Splits verified, non-corrupted raw images into stratified Train / Validation / Test sets.
Classes: clean, damp, algae, mold, broken.

Does NOT generate synthetic images or fabricate labels.
"""

import os
import shutil
import random
import argparse
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from backend.cv.preprocess import validate_and_load_image
from backend.cv.model import WALL_CONDITION_CLASSES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("nivas.cv.split_dataset")


def split_wall_dataset(
    source_dir: str = "data/wall_condition_dataset/raw",
    target_dir: str = "data/wall_condition_dataset",
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> Dict[str, Dict[str, int]]:
    """
    Splits real raw wall-condition images into train, validation, and test sets.
    Performs corruption validation before copying.

    Returns:
        Summary dict of copied files per class and split.
    """
    assert abs((train_ratio + val_ratio + test_ratio) - 1.0) < 1e-4, "Split ratios must sum to 1.0 (e.g. 0.70 + 0.15 + 0.15 = 1.0)"
    random.seed(seed)

    source_path = Path(source_dir)
    target_path = Path(target_dir)

    # Check for nested 'raw' directory if root provided
    if not source_path.exists() and (source_path / "raw").exists():
        source_path = source_path / "raw"

    if not source_path.exists():
        logger.error("Source dataset directory '%s' does not exist. Please place raw class folders in '%s'.", source_dir, source_dir)
        return {}

    splits = ["train", "val", "test"]
    for split in splits:
        for cls in WALL_CONDITION_CLASSES:
            (target_path / split / cls).mkdir(parents=True, exist_ok=True)

    summary: Dict[str, Dict[str, int]] = {
        cls: {"train": 0, "val": 0, "test": 0, "corrupted": 0, "total_valid": 0}
        for cls in WALL_CONDITION_CLASSES
    }

    for cls in WALL_CONDITION_CLASSES:
        cls_dir = source_path / cls
        if not cls_dir.exists():
            logger.warning("Class directory '%s' not found in '%s'.", cls, source_path)
            continue

        image_files = [f for f in cls_dir.glob("*") if f.is_file() and not f.name.startswith(".")]
        random.shuffle(image_files)

        valid_files = []
        for img_p in image_files:
            valid, err, _ = validate_and_load_image(img_p)
            if valid:
                valid_files.append(img_p)
            else:
                summary[cls]["corrupted"] += 1
                logger.warning("Skipping corrupted file %s/%s: %s", cls, img_p.name, err)

        total_valid = len(valid_files)
        summary[cls]["total_valid"] = total_valid

        if total_valid == 0:
            logger.warning("No valid images found for class '%s'.", cls)
            continue

        train_end = int(total_valid * train_ratio)
        val_end = train_end + int(total_valid * val_ratio)

        train_files = valid_files[:train_end]
        val_files = valid_files[train_end:val_end]
        test_files = valid_files[val_end:]

        split_map = {
            "train": train_files,
            "val": val_files,
            "test": test_files,
        }

        for split, files in split_map.items():
            for src_file in files:
                dst_file = target_path / split / cls / src_file.name
                shutil.copy2(src_file, dst_file)
                summary[cls][split] += 1

    logger.info("Dataset split complete. Summary:")
    for cls, counts in summary.items():
        logger.info(
            "  Class '%s': Total Valid=%d -> Train=%d, Val=%d, Test=%d (Corrupted Skipped=%d)",
            cls, counts["total_valid"], counts["train"], counts["val"], counts["test"], counts["corrupted"]
        )

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Split raw wall-condition images into Train/Val/Test splits")
    parser.add_argument("--source_dir", type=str, default="data/wall_condition_dataset/raw", help="Directory containing raw class folders")
    parser.add_argument("--target_dir", type=str, default="data/wall_condition_dataset", help="Target dataset directory")
    parser.add_argument("--train_ratio", type=float, default=0.70, help="Train ratio (default: 0.70)")
    parser.add_argument("--val_ratio", type=float, default=0.15, help="Val ratio (default: 0.15)")
    parser.add_argument("--test_ratio", type=float, default=0.15, help="Test ratio (default: 0.15)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    split_wall_dataset(
        source_dir=args.source_dir,
        target_dir=args.target_dir,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
    )
