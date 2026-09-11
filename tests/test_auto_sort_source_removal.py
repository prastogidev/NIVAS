"""
Unit tests for the NIVAS auto-sort source image removal workflow and safety guards.

Verifies:
1. Successful sort deletes source image from unsorted_images.
2. Failed copy preserves source image.
3. Failed manifest write preserves source image.
4. Invalid/corrupted image preserves source image.
5. Duplicate image preserves source image.
6. --keep-source flag preserves source image.
7. Reviewer works when original source file no longer exists (uses sorted_path).
8. Corrected labels still move correctly when original source was deleted.
9. Manifest retains original filename and original path information after source removal.
"""

import os
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from PIL import Image

from backend.cv.auto_sort import auto_sort_images
from backend.cv.review_sort import interactive_review, load_manifest, _resolve_image_path
from backend.cv.model import WALL_CONDITION_CLASSES


def _create_dummy_image(path: Path, color=(128, 128, 128)) -> None:
    """Helper to create a small valid JPEG image."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (32, 32), color=color)
    img.save(str(path), format="JPEG")


class TestAutoSortSourceRemoval(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.input_dir = self.test_path / "unsorted_images"
        self.output_dir = self.test_path / "raw"
        self.manifest_path = self.test_path / "sort_manifest.json"
        self.input_dir.mkdir(parents=True)
        self.output_dir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_successful_sort_deletes_source(self):
        """Verify that successfully sorted image is deleted from unsorted_images."""
        src_img = self.input_dir / "wall_sample.jpg"
        _create_dummy_image(src_img, color=(200, 100, 50))
        self.assertTrue(src_img.exists())

        summary = auto_sort_images(
            input_dir=str(self.input_dir),
            output_dir=str(self.output_dir),
            manifest_path=str(self.manifest_path),
            keep_source=False,
            device_name="cpu",
        )

        self.assertEqual(summary["sorted_count"], 1)
        self.assertEqual(summary["source_images_removed"], 1)

        # Source file must be removed
        self.assertFalse(src_img.exists(), "Source image should be deleted from unsorted_images after successful sort.")

        # Copied destination file must exist and be valid
        entry = summary["entries"][0]
        dest_file = Path(entry["sorted_path"])
        self.assertTrue(dest_file.exists(), "Destination file must exist in raw class folder.")
        self.assertTrue(entry["source_removed"])
        self.assertEqual(entry["review_status"], "pending")

    def test_failed_copy_preserves_source(self):
        """Verify that if shutil.copy2 fails, source file is NOT deleted."""
        src_img = self.input_dir / "wall_sample.jpg"
        _create_dummy_image(src_img)

        with patch("backend.cv.auto_sort.shutil.copy2", side_effect=IOError("Simulated disk write error")):
            summary = auto_sort_images(
                input_dir=str(self.input_dir),
                output_dir=str(self.output_dir),
                manifest_path=str(self.manifest_path),
                keep_source=False,
                device_name="cpu",
            )

        # Source file must be preserved
        self.assertTrue(src_img.exists(), "Source image must be preserved if copy fails.")
        self.assertEqual(summary["sorted_count"], 0)
        self.assertEqual(summary["source_images_removed"], 0)
        self.assertGreater(summary["failed_count"], 0)

    def test_failed_manifest_write_preserves_source(self):
        """Verify that if manifest cannot be written, source files are NEVER deleted."""
        src_img = self.input_dir / "wall_sample.jpg"
        _create_dummy_image(src_img)

        # Provide a path inside a non-existent, uncreatable directory or mock open
        with patch("backend.cv.auto_sort.open", side_effect=IOError("Permission denied writing manifest")):
            with self.assertRaises(IOError):
                auto_sort_images(
                    input_dir=str(self.input_dir),
                    output_dir=str(self.output_dir),
                    manifest_path=str(self.manifest_path),
                    keep_source=False,
                    device_name="cpu",
                )

        # Source file must be preserved
        self.assertTrue(src_img.exists(), "Source image must be preserved if manifest write fails.")

    def test_invalid_image_preserves_source(self):
        """Verify that corrupted/invalid images are not deleted from unsorted_images."""
        corrupted_img = self.input_dir / "corrupted.jpg"
        with open(corrupted_img, "wb") as f:
            f.write(b"NOT_A_VALID_IMAGE_BYTES")

        summary = auto_sort_images(
            input_dir=str(self.input_dir),
            output_dir=str(self.output_dir),
            manifest_path=str(self.manifest_path),
            keep_source=False,
            device_name="cpu",
        )

        self.assertTrue(corrupted_img.exists(), "Corrupted source image must NOT be deleted.")
        self.assertEqual(summary["sorted_count"], 0)
        self.assertEqual(summary["source_images_removed"], 0)
        self.assertEqual(summary["failed_count"], 1)

    def test_duplicate_preserves_source(self):
        """Verify that duplicate images are skipped and preserved in unsorted_images."""
        # Create image already in raw/clean/
        existing_raw = self.output_dir / "clean" / "existing.jpg"
        _create_dummy_image(existing_raw, color=(50, 150, 250))

        # Put exact same image in unsorted_images
        duplicate_src = self.input_dir / "duplicate.jpg"
        shutil.copy2(existing_raw, duplicate_src)

        summary = auto_sort_images(
            input_dir=str(self.input_dir),
            output_dir=str(self.output_dir),
            manifest_path=str(self.manifest_path),
            keep_source=False,
            device_name="cpu",
        )

        self.assertTrue(duplicate_src.exists(), "Duplicate source image must be preserved.")
        self.assertEqual(summary["duplicate_count"], 1)
        self.assertEqual(summary["source_images_removed"], 0)

    def test_keep_source_preserves_source(self):
        """Verify that --keep-source preserves original files in unsorted_images."""
        src_img = self.input_dir / "test_keep.jpg"
        _create_dummy_image(src_img)

        summary = auto_sort_images(
            input_dir=str(self.input_dir),
            output_dir=str(self.output_dir),
            manifest_path=str(self.manifest_path),
            keep_source=True,
            device_name="cpu",
        )

        self.assertEqual(summary["sorted_count"], 1)
        self.assertEqual(summary["source_images_removed"], 0)
        self.assertTrue(src_img.exists(), "Source image must be preserved when keep_source=True.")
        self.assertFalse(summary["entries"][0]["source_removed"])

    def test_manifest_retains_original_filename_and_path(self):
        """Verify manifest retains original filename and path even after source removal."""
        src_img = self.input_dir / "sample_origin.jpg"
        _create_dummy_image(src_img)
        orig_path_str = str(src_img.resolve())

        summary = auto_sort_images(
            input_dir=str(self.input_dir),
            output_dir=str(self.output_dir),
            manifest_path=str(self.manifest_path),
            keep_source=False,
            device_name="cpu",
        )

        self.assertFalse(src_img.exists())

        # Load manifest from disk
        with open(self.manifest_path, "r") as f:
            disk_manifest = json.load(f)

        entry = disk_manifest["entries"][0]
        self.assertEqual(entry["original_filename"], "sample_origin.jpg")
        self.assertEqual(entry["original_path"], orig_path_str)
        self.assertTrue(entry["source_removed"])
        self.assertTrue(Path(entry["sorted_path"]).exists())

    def test_reviewer_works_when_original_source_no_longer_exists(self):
        """Verify review_sort opens sorted_path when original_path does not exist."""
        # Sort image with source removal
        src_img = self.input_dir / "wall_for_review.jpg"
        _create_dummy_image(src_img)

        auto_sort_images(
            input_dir=str(self.input_dir),
            output_dir=str(self.output_dir),
            manifest_path=str(self.manifest_path),
            keep_source=False,
            device_name="cpu",
        )

        self.assertFalse(src_img.exists())

        # Verify reviewer path resolution
        manifest = load_manifest(self.manifest_path)
        entry = manifest["entries"][0]
        resolved = _resolve_image_path(entry)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved, Path(entry["sorted_path"]))
        self.assertTrue(resolved.exists())

        # Test running interactive review
        opened_paths = []
        def mock_opener(path):
            opened_paths.append(path)
            return True

        with patch("builtins.input", side_effect=[""]):  # Accept prediction
            actions = interactive_review(
                manifest_path=str(self.manifest_path),
                output_dir=str(self.output_dir),
                _open_image_fn=mock_opener,
            )

        self.assertEqual(actions["approved"], 1)
        self.assertEqual(len(opened_paths), 1)
        self.assertEqual(opened_paths[0], Path(entry["sorted_path"]))

    def test_corrected_labels_still_move_correctly_when_source_deleted(self):
        """Verify correcting label to broken (4) moves sorted_path even if original source was deleted."""
        src_img = self.input_dir / "wall_to_correct.jpg"
        _create_dummy_image(src_img)

        auto_sort_images(
            input_dir=str(self.input_dir),
            output_dir=str(self.output_dir),
            manifest_path=str(self.manifest_path),
            keep_source=False,
            device_name="cpu",
        )

        manifest = load_manifest(self.manifest_path)
        entry = manifest["entries"][0]
        old_sorted_path = Path(entry["sorted_path"])
        self.assertTrue(old_sorted_path.exists())

        # Correct to a class different from predicted
        pred_class = entry["predicted_class"]
        target_idx = "4" if pred_class != "broken" else "0"
        target_class = WALL_CONDITION_CLASSES[int(target_idx)]

        with patch("builtins.input", side_effect=[target_idx]):
            actions = interactive_review(
                manifest_path=str(self.manifest_path),
                output_dir=str(self.output_dir),
                _open_image_fn=lambda p: True,
            )

        self.assertEqual(actions["corrected"], 1)

        # Verify old sorted path is gone and moved to target folder
        self.assertFalse(old_sorted_path.exists())
        target_file = self.output_dir / target_class / src_img.name
        self.assertTrue(target_file.exists(), f"File should be moved to raw/{target_class}/")

        # Verify updated manifest
        updated_manifest = load_manifest(self.manifest_path)
        up_entry = updated_manifest["entries"][0]
        self.assertEqual(up_entry["corrected_class"], target_class)
        self.assertEqual(up_entry["sorted_path"], str(target_file.resolve()))
        self.assertEqual(up_entry["original_filename"], "wall_to_correct.jpg")


if __name__ == "__main__":
    unittest.main()
