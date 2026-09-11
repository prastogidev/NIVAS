import os
import shutil
import random
import argparse
import logging
from pathlib import Path
from backend.cv.preprocess import validate_and_load_image
from backend.cv.model import WALL_CONDITION_CLASSES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nivas.cv.split_dataset")


def split_wall_dataset(
    source_dir: str,
    target_dir: str,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
):
    """
    Splits real raw wall-condition images into train, validation, and test sets.
    Performs corruption validation before copying.
    Does NOT generate synthetic/fake images.
    """
    assert abs((train_ratio + val_ratio + test_ratio) - 1.0) < 1e-4, "Ratios must sum to 1.0"
    random.seed(seed)

    source_path = Path(source_dir)
    target_path = Path(target_dir)

    if not source_path.exists():
        logger.error("Source dataset directory '%s' does not exist.", source_dir)
        return

    splits = ["train", "val", "test"]
    for split in splits:
        for cls in WALL_CONDITION_CLASSES:
            (target_path / split / cls).mkdir(parents=True, exist_ok=True)

    summary = {cls: {"train": 0, "val": 0, "test": 0, "corrupted": 0} for cls in WALL_CONDITION_CLASSES}

    for cls in WALL_CONDITION_CLASSES:
        cls_dir = source_path / cls
        if not cls_dir.exists():
            logger.warning("Class directory '%s' not found in source_dir.", cls_dir)
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
                logger.warning("Skipping corrupted file %s: %s", img_p.name, err)

        total_valid = len(valid_files)
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

    logger.info("Dataset split complete. Split summary:")
    for cls, counts in summary.items():
        logger.info(
            "Class '%s': Train=%d, Val=%d, Test=%d (Corrupted Skipped=%d)",
            cls, counts["train"], counts["val"], counts["test"], counts["corrupted"]
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Split real wall-condition images into Train/Val/Test")
    parser.add_argument("--source_dir", type=str, required=True, help="Directory containing raw class folders")
    parser.add_argument("--target_dir", type=str, default="data/wall_condition_dataset", help="Target dataset directory")
    parser.add_argument("--train_ratio", type=float, default=0.70)
    parser.add_argument("--val_ratio", type=float, default=0.15)
    parser.add_argument("--test_ratio", type=float, default=0.15)
    args = parser.parse_args()

    split_wall_dataset(
        source_dir=args.source_dir,
        target_dir=args.target_dir,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
    )
