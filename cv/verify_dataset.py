import sys
import logging
from pathlib import Path
from typing import Dict, Any, List
from backend.cv.preprocess import validate_and_load_image
from backend.cv.model import WALL_CONDITION_CLASSES

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("nivas.cv.verify_dataset")

DATASET_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "wall_condition_dataset"


def verify_wall_condition_dataset(dataset_dir: Path = DATASET_ROOT) -> Dict[str, Any]:
    """
    Scans the wall condition dataset directory across train, val, and test splits.
    Identifies corrupted images, verifies class counts, and reports class imbalance metrics.
    Does NOT generate synthetic/fake images.
    """
    logger.info("Scanning dataset directory: %s", dataset_dir)
    results = {
        "splits": {},
        "corrupted_files": [],
        "imbalance_warnings": [],
    }

    if not dataset_dir.exists():
        logger.error("Dataset root directory '%s' does not exist.", dataset_dir)
        return results

    splits = ["train", "val", "test"]

    for split in splits:
        split_dir = dataset_dir / split
        if not split_dir.exists():
            logger.warning("Split directory '%s' missing.", split)
            continue

        class_counts = {cls: 0 for cls in WALL_CONDITION_CLASSES}
        corrupted_in_split = 0

        for cls in WALL_CONDITION_CLASSES:
            cls_dir = split_dir / cls
            if not cls_dir.exists():
                continue

            for file_path in cls_dir.glob("*"):
                if file_path.is_file() and not file_path.name.startswith("."):
                    valid, err_msg, _ = validate_and_load_image(file_path)
                    if valid:
                        class_counts[cls] += 1
                    else:
                        corrupted_in_split += 1
                        results["corrupted_files"].append({
                            "split": split,
                            "class": cls,
                            "filename": file_path.name,
                            "error": err_msg,
                        })

        total_valid = sum(class_counts.values())
        results["splits"][split] = {
            "class_counts": class_counts,
            "total_valid": total_valid,
            "corrupted_count": corrupted_in_split,
        }

        logger.info("=== Split: %s ===", split.upper())
        logger.info("Total Valid Images: %d | Corrupted Images Detected: %d", total_valid, corrupted_in_split)
        for cls, cnt in class_counts.items():
            pct = (cnt / total_valid * 100.0) if total_valid > 0 else 0.0
            logger.info("  - Class '%s': %d images (%.1f%%)", cls, cnt, pct)

        # Class imbalance check
        if total_valid > 0:
            counts_list = list(class_counts.values())
            non_zero_counts = [c for c in counts_list if c > 0]
            if len(non_zero_counts) > 1:
                max_cnt = max(non_zero_counts)
                min_cnt = min(non_zero_counts)
                ratio = max_cnt / min_cnt
                if ratio > 3.0:
                    warn_msg = f"Split '{split}' has severe class imbalance (Ratio max/min = {ratio:.2f}x: max={max_cnt}, min={min_cnt})."
                    logger.warning(warn_msg)
                    results["imbalance_warnings"].append(warn_msg)
            elif len(non_zero_counts) < len(WALL_CONDITION_CLASSES):
                empty_classes = [cls for cls, cnt in class_counts.items() if cnt == 0]
                warn_msg = f"Split '{split}' has missing class data for: {', '.join(empty_classes)}."
                logger.warning(warn_msg)
                results["imbalance_warnings"].append(warn_msg)

    return results


if __name__ == "__main__":
    dir_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else DATASET_ROOT
    verify_wall_condition_dataset(dir_arg)
