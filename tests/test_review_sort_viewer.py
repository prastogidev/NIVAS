"""
Unit tests for the NIVAS review_sort image-opening workflow.

Mocks subprocess.Popen so that tests never actually launch Preview or any
external viewer.  Verifies that:
- open_image_viewer dispatches the correct platform command.
- _resolve_image_path picks the best existing file.
- interactive_review calls the image opener for every pending entry.
- Missing/unopenable images are handled gracefully without crashing.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from PIL import Image

from backend.cv.review_sort import (
    open_image_viewer,
    _resolve_image_path,
    display_entry,
    interactive_review,
    load_manifest,
    get_pending_entries,
)


class TestOpenImageViewer(unittest.TestCase):
    """Tests for the open_image_viewer function."""

    def test_opens_existing_image_on_macos(self):
        """Verify subprocess.Popen is called with 'open' on macOS."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            # Write a minimal valid JPEG-like content so the file is non-empty
            tmp.write(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        try:
            with patch("backend.cv.review_sort.sys") as mock_sys, \
                 patch("backend.cv.review_sort.subprocess") as mock_subprocess:
                mock_sys.platform = "darwin"
                result = open_image_viewer(tmp_path)

            self.assertTrue(result)
            mock_subprocess.Popen.assert_called_once_with(["open", str(tmp_path.resolve())])
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_opens_existing_image_on_linux(self):
        """Verify subprocess.Popen is called with 'xdg-open' on Linux."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(b"\x89PNG" + b"\x00" * 100)

        try:
            with patch("backend.cv.review_sort.sys") as mock_sys, \
                 patch("backend.cv.review_sort.subprocess") as mock_subprocess:
                mock_sys.platform = "linux"
                result = open_image_viewer(tmp_path)

            self.assertTrue(result)
            mock_subprocess.Popen.assert_called_once_with(["xdg-open", str(tmp_path.resolve())])
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_returns_false_for_missing_file(self):
        """Verify that a missing image path returns False without crashing."""
        missing_path = Path("/nonexistent/fake_image.jpg")
        result = open_image_viewer(missing_path)
        self.assertFalse(result)

    def test_returns_false_on_subprocess_error(self):
        """Verify graceful handling when subprocess.Popen raises OSError."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        try:
            with patch("backend.cv.review_sort.sys") as mock_sys, \
                 patch("backend.cv.review_sort.subprocess") as mock_subprocess:
                mock_sys.platform = "darwin"
                mock_subprocess.Popen.side_effect = OSError("open command not found")
                result = open_image_viewer(tmp_path)

            self.assertFalse(result)
        finally:
            tmp_path.unlink(missing_ok=True)


class TestResolveImagePath(unittest.TestCase):
    """Tests for the _resolve_image_path helper."""

    def test_prefers_sorted_path_when_both_exist(self):
        """sorted_path should take priority over original_path."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            sorted_file = Path(tmp_dir) / "sorted.jpg"
            original_file = Path(tmp_dir) / "original.jpg"
            sorted_file.touch()
            original_file.touch()

            entry = {
                "sorted_path": str(sorted_file),
                "original_path": str(original_file),
            }
            result = _resolve_image_path(entry)
            self.assertEqual(result, sorted_file)

    def test_falls_back_to_original_path(self):
        """If sorted_path doesn't exist, fall back to original_path."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            original_file = Path(tmp_dir) / "original.jpg"
            original_file.touch()

            entry = {
                "sorted_path": "/nonexistent/gone.jpg",
                "original_path": str(original_file),
            }
            result = _resolve_image_path(entry)
            self.assertEqual(result, original_file)

    def test_returns_none_when_neither_exists(self):
        """If no file exists on disk, return None."""
        entry = {
            "sorted_path": "/nonexistent/a.jpg",
            "original_path": "/nonexistent/b.jpg",
        }
        result = _resolve_image_path(entry)
        self.assertIsNone(result)

    def test_returns_none_for_empty_entry(self):
        """If neither key is present, return None."""
        entry = {}
        result = _resolve_image_path(entry)
        self.assertIsNone(result)


class TestInteractiveReviewOpensImages(unittest.TestCase):
    """Tests that interactive_review calls the image opener for each pending entry."""

    def _make_manifest_with_images(self, tmp_dir: Path, count: int = 2):
        """Helper: create a manifest JSON and dummy image files."""
        entries = []
        for idx in range(count):
            img_name = f"wall_{idx}.jpg"
            img_path = tmp_dir / img_name
            # Write a minimal file so it exists
            Image.new("RGB", (10, 10), color=(128, 128, 128)).save(str(img_path), "JPEG")

            entries.append({
                "original_filename": img_name,
                "original_path": str(img_path),
                "sorted_path": str(img_path),
                "predicted_class": "clean",
                "confidence": 0.55,
                "class_probabilities": {"clean": 0.55, "damp": 0.20, "algae": 0.15, "mold": 0.10},
                "review_status": "pending",
                "corrected_class": None,
                "status": "sorted",
            })

        manifest = {
            "entries": entries,
            "total_images_found": count,
        }

        manifest_path = tmp_dir / "sort_manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)

        return manifest_path

    def test_opener_called_for_each_pending_image(self):
        """Verify _open_image_fn is called once per pending image."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            manifest_path = self._make_manifest_with_images(tmp_path, count=3)

            mock_opener = MagicMock(return_value=True)

            # Simulate user pressing Enter (approve) for each image
            with patch("builtins.input", side_effect=["", "", ""]):
                actions = interactive_review(
                    manifest_path=str(manifest_path),
                    output_dir=str(tmp_path),
                    _open_image_fn=mock_opener,
                )

            self.assertEqual(mock_opener.call_count, 3)
            self.assertEqual(actions["approved"], 3)

    def test_opener_receives_correct_paths(self):
        """Verify the opener is called with the resolved image paths."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            manifest_path = self._make_manifest_with_images(tmp_path, count=2)

            opened_paths = []
            def capture_opener(path):
                opened_paths.append(path)
                return True

            with patch("builtins.input", side_effect=["", ""]):
                interactive_review(
                    manifest_path=str(manifest_path),
                    output_dir=str(tmp_path),
                    _open_image_fn=capture_opener,
                )

            self.assertEqual(len(opened_paths), 2)
            for p in opened_paths:
                self.assertTrue(p.exists(), f"Opened path should exist: {p}")
                self.assertTrue(p.name.startswith("wall_"))

    def test_handles_missing_image_gracefully(self):
        """Verify review proceeds when image file is missing on disk."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            manifest_path = self._make_manifest_with_images(tmp_path, count=1)

            # Delete the image file so it's missing
            (tmp_path / "wall_0.jpg").unlink()

            mock_opener = MagicMock(return_value=True)

            with patch("builtins.input", side_effect=[""]):
                actions = interactive_review(
                    manifest_path=str(manifest_path),
                    output_dir=str(tmp_path),
                    _open_image_fn=mock_opener,
                )

            # Opener should NOT be called since file is missing
            mock_opener.assert_not_called()
            # But the review should still proceed without crashing
            self.assertEqual(actions["approved"], 1)

    def test_opener_failure_does_not_crash_review(self):
        """Verify review continues when the image viewer fails to launch."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            manifest_path = self._make_manifest_with_images(tmp_path, count=2)

            # Opener always fails
            mock_opener = MagicMock(return_value=False)

            with patch("builtins.input", side_effect=["", ""]):
                actions = interactive_review(
                    manifest_path=str(manifest_path),
                    output_dir=str(tmp_path),
                    _open_image_fn=mock_opener,
                )

            self.assertEqual(mock_opener.call_count, 2)
            self.assertEqual(actions["approved"], 2)

    def test_correct_to_broken_moves_file_and_updates_manifest(self):
        """Verify pressing '4' corrects label to 'broken' and moves file to broken folder."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            raw_dir = tmp_path / "raw"
            clean_dir = raw_dir / "clean"
            broken_dir = raw_dir / "broken"
            clean_dir.mkdir(parents=True)
            broken_dir.mkdir(parents=True)

            img_file = clean_dir / "test_wall.jpg"
            Image.new("RGB", (10, 10), color=(100, 100, 100)).save(str(img_file), "JPEG")

            manifest_path = tmp_path / "sort_manifest.json"
            manifest_data = {
                "entries": [{
                    "original_filename": "test_wall.jpg",
                    "original_path": str(img_file),
                    "sorted_path": str(img_file),
                    "predicted_class": "clean",
                    "confidence": 0.45,
                    "class_probabilities": {"clean": 0.45, "damp": 0.20, "algae": 0.15, "mold": 0.10, "broken": 0.10},
                    "review_status": "pending",
                    "corrected_class": None,
                    "status": "sorted",
                }]
            }
            with open(manifest_path, "w") as f:
                json.dump(manifest_data, f)

            # User enters '4' to correct to broken
            with patch("builtins.input", side_effect=["4"]):
                actions = interactive_review(
                    manifest_path=str(manifest_path),
                    output_dir=str(raw_dir),
                    _open_image_fn=lambda p: True,
                )

            self.assertEqual(actions["corrected"], 1)

            # Check file moved to broken_dir
            dest_file = broken_dir / "test_wall.jpg"
            self.assertTrue(dest_file.exists(), "Image should have moved to raw/broken/")
            self.assertFalse(img_file.exists(), "Original file should no longer be in clean/")

            # Check updated manifest
            updated_manifest = load_manifest(manifest_path)
            entry = updated_manifest["entries"][0]
            self.assertEqual(entry["review_status"], "corrected")
            self.assertEqual(entry["corrected_class"], "broken")
            self.assertEqual(entry["sorted_path"], str(dest_file.resolve()))


if __name__ == "__main__":
    unittest.main()
