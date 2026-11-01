"""
Regression tests for NIVAS CV pipeline — P1, P2, P3 patches and new infrastructure.

P1: cv_model.py returns None (untrained state) when no checkpoint exists.
P2: compute_blur_variance downscales before computing Laplacian (no false blur rejection).
P3: WALL_CONDITION_CLASSES is in alphabetical order (matches ImageFolder); class-order
    assertion fires when dataset has wrong class ordering.

Also covers:
- dataset_check.py class-order validation
- label_map.py approved mappings and exclusion recording
- field_eval.py field set isolation
- train.py _assert_class_order_matches guard
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
from PIL import Image


# ---------------------------------------------------------------------------
# P3: WALL_CONDITION_CLASSES exact order regression test
# clean, damp, algae, mold, broken
# ---------------------------------------------------------------------------
class TestP3ClassOrder(unittest.TestCase):

    def test_wall_condition_classes_exact_order(self):
        """P3: WALL_CONDITION_CLASSES must be clean, damp, algae, mold, broken."""
        from backend.cv.model import WALL_CONDITION_CLASSES
        expected = ["clean", "damp", "algae", "mold", "broken"]
        self.assertEqual(
            WALL_CONDITION_CLASSES,
            expected,
            msg=f"WALL_CONDITION_CLASSES {WALL_CONDITION_CLASSES} != {expected}",
        )

    def test_wall_condition_classes_are_exactly_five(self):
        """P3: Exactly 5 classes, no more, no less."""
        from backend.cv.model import WALL_CONDITION_CLASSES
        self.assertEqual(len(WALL_CONDITION_CLASSES), 5)

    def test_wall_condition_classes_exact_values(self):
        """P3: Exact class names and indices."""
        from backend.cv.model import WALL_CONDITION_CLASSES
        self.assertEqual(WALL_CONDITION_CLASSES[0], "clean")
        self.assertEqual(WALL_CONDITION_CLASSES[1], "damp")
        self.assertEqual(WALL_CONDITION_CLASSES[2], "algae")
        self.assertEqual(WALL_CONDITION_CLASSES[3], "mold")
        self.assertEqual(WALL_CONDITION_CLASSES[4], "broken")

    def test_train_class_order_assertion_detects_mismatch(self):
        """P3: _assert_class_order_matches raises ValueError if dataset order differs."""
        from backend.cv import train as train_module
        from torchvision.datasets import ImageFolder

        mock_dataset = MagicMock(spec=ImageFolder)
        mock_dataset.class_to_idx = {"algae": 0, "broken": 1, "clean": 2, "damp": 3, "mold": 4}
        mock_dataset.classes = ["algae", "broken", "clean", "damp", "mold"]

        with self.assertRaises(ValueError) as ctx:
            train_module._assert_class_order_matches(mock_dataset)
        self.assertIn("P3 CLASS-ORDER MISMATCH", str(ctx.exception))

    def test_train_class_order_assertion_passes_for_correct_order(self):
        """P3: _assert_class_order_matches does NOT raise when orders match."""
        from backend.cv import train as train_module
        from torchvision.datasets import ImageFolder

        mock_dataset = MagicMock(spec=ImageFolder)
        expected_classes = ["clean", "damp", "algae", "mold", "broken"]
        mock_dataset.classes = list(expected_classes)
        mock_dataset.class_to_idx = {c: i for i, c in enumerate(expected_classes)}

        # Should not raise
        train_module._assert_class_order_matches(mock_dataset)

    def test_class_weights_use_correct_order(self):
        """P3: compute_class_weights uses WALL_CONDITION_CLASSES order; broken is index 4."""
        import torch
        from backend.cv.train import compute_class_weights
        from backend.cv.model import WALL_CONDITION_CLASSES

        # Give broken=1 image, clean=100 images -> broken must have highest weight
        class_counts = {cls: 100 for cls in WALL_CONDITION_CLASSES}
        class_counts["broken"] = 1
        weights = compute_class_weights(class_counts, torch.device("cpu"))

        self.assertIsNotNone(weights)
        broken_idx = WALL_CONDITION_CLASSES.index("broken")  # must be 4
        self.assertEqual(broken_idx, 4)
        for i, cls in enumerate(WALL_CONDITION_CLASSES):
            if cls != "broken":
                self.assertGreater(
                    weights[broken_idx].item(),
                    weights[i].item(),
                    msg=f"broken weight should be highest; failed vs {cls}",
                )

    def test_result_from_probabilities_uses_exact_class_order(self):
        """P3: _result_from_probabilities treats index 4 as 'broken'."""
        from backend.services.cv_model import _result_from_probabilities

        # Probabilities: [clean=0.05, damp=0.05, algae=0.05, mold=0.05, broken=0.80]
        # Index 4 (broken) has highest prob -> predicted_class must be 'broken'
        probs = [0.05, 0.05, 0.05, 0.05, 0.80]
        result = _result_from_probabilities(probs)
        self.assertEqual(result.predicted_class, "broken")
        self.assertEqual(result.confidence, 0.80)
        self.assertIn("broken", result.defects_detected)

    def test_result_from_probabilities_clean_at_index_0(self):
        """P3: clean is at index 0; clean result must produce high structural_score."""
        from backend.services.cv_model import _result_from_probabilities

        probs = [0.96, 0.01, 0.01, 0.01, 0.01]
        result = _result_from_probabilities(probs)
        self.assertEqual(result.predicted_class, "clean")
        self.assertGreater(result.structural_score, 90.0)


# ---------------------------------------------------------------------------
# P1: Untrained state regression test
# ---------------------------------------------------------------------------
class TestP1UntrainedState(unittest.IsolatedAsyncioTestCase):

    async def test_run_cv_analysis_returns_none_when_no_checkpoint(self):
        """P1: run_cv_analysis must return None when no trained checkpoint exists."""
        from backend.services.cv_model import run_cv_analysis
        from backend.models.score import ImageInfo

        # Create a tiny valid test image as base64
        import io, base64
        img = Image.new("RGB", (100, 100), color=(128, 128, 128))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        image_info = ImageInfo(image_base64=b64)

        # Patch MODEL_WEIGHTS_PATH to point to a non-existent path
        with patch("backend.services.cv_model.MODEL_WEIGHTS_PATH", Path("/tmp/nonexistent_weights.pth")):
            result = await run_cv_analysis(image_info)

        self.assertIsNone(
            result,
            msg=(
                "P1 FAIL: run_cv_analysis returned a non-None result despite no checkpoint. "
                "It must return None (untrained) instead of generating random predictions."
            ),
        )

    async def test_run_cv_analysis_returns_none_when_torch_unavailable(self):
        """run_cv_analysis must return None when PyTorch is not importable."""
        from backend.services import cv_model as cv_model_module
        from backend.models.score import ImageInfo
        import io, base64

        img = Image.new("RGB", (50, 50), color=(200, 100, 50))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        image_info = ImageInfo(image_base64=b64)

        with patch.object(cv_model_module, "TORCH_AVAILABLE", False):
            result = await cv_model_module.run_cv_analysis(image_info)

        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# P2: Blur detection downscaling regression test
# ---------------------------------------------------------------------------
class TestP2BlurDetection(unittest.TestCase):

    def _make_sharp_image(self, width: int, height: int) -> Image.Image:
        """Create a sharp synthetic image (high-frequency checkerboard)."""
        import numpy as np
        arr = np.zeros((height, width, 3), dtype=np.uint8)
        # Checkerboard pattern — lots of high-frequency edges
        for y in range(height):
            for x in range(width):
                if (x // 8 + y // 8) % 2 == 0:
                    arr[y, x] = [255, 255, 255]
                else:
                    arr[y, x] = [0, 0, 0]
        return Image.fromarray(arr)

    def _make_blurry_image(self, width: int, height: int) -> Image.Image:
        """Create a genuinely blurry image (uniform flat color — zero variance)."""
        return Image.new("RGB", (width, height), color=(128, 128, 128))

    def test_sharp_high_res_image_is_not_rejected(self):
        """P2: A sharp 1600×1200 image must produce variance ABOVE threshold (50.0)."""
        from backend.services.cv_model import compute_blur_variance, BLUR_VARIANCE_THRESHOLD

        img = self._make_sharp_image(1600, 1200)
        variance = compute_blur_variance(img)
        self.assertGreater(
            variance,
            BLUR_VARIANCE_THRESHOLD,
            msg=(
                f"P2 FAIL: Sharp high-res image has blur_variance={variance:.2f} which is "
                f"BELOW threshold {BLUR_VARIANCE_THRESHOLD}. Downscaling fix not working."
            ),
        )

    def test_sharp_standard_res_image_is_not_rejected(self):
        """P2: A sharp 224×224 image must also pass the blur check."""
        from backend.services.cv_model import compute_blur_variance, BLUR_VARIANCE_THRESHOLD

        img = self._make_sharp_image(224, 224)
        variance = compute_blur_variance(img)
        self.assertGreater(variance, BLUR_VARIANCE_THRESHOLD)

    def test_genuinely_blurry_image_is_rejected(self):
        """P2: A flat/blurry image (zero variance) must still be rejected."""
        from backend.services.cv_model import compute_blur_variance, BLUR_VARIANCE_THRESHOLD

        img = self._make_blurry_image(800, 600)
        variance = compute_blur_variance(img)
        self.assertLessEqual(
            variance,
            BLUR_VARIANCE_THRESHOLD,
            msg=f"Expected flat image to be below threshold; got variance={variance:.2f}",
        )

    def test_downscaling_is_applied_to_large_images(self):
        """P2: compute_blur_variance downscales large images before Laplacian."""
        from backend.services.cv_model import compute_blur_variance, _BLUR_EVAL_MAX_DIM

        # Create 2000×2000 checkerboard and 224×224 equivalent
        # Both should give similar variance (within an order of magnitude)
        large = self._make_sharp_image(2000, 2000)
        small = self._make_sharp_image(224, 224)

        var_large = compute_blur_variance(large)
        var_small = compute_blur_variance(small)

        # Without downscaling, var_large >> var_small (scales with resolution^2)
        # With downscaling both should be in the same ballpark
        ratio = max(var_large, var_small) / max(min(var_large, var_small), 1e-6)
        self.assertLess(
            ratio,
            50.0,
            msg=(
                f"P2 FAIL: variance ratio between 2000px and 224px image is {ratio:.1f}x "
                f"(var_large={var_large:.1f}, var_small={var_small:.1f}). "
                f"This suggests downscaling is NOT applied (without fix the ratio would be ~{(2000/224)**2:.0f}x)."
            ),
        )


# ---------------------------------------------------------------------------
# Label mapping regression tests
# ---------------------------------------------------------------------------
class TestLabelMapping(unittest.TestCase):

    def test_approved_mappings(self):
        """Label map correctly translates all approved source labels."""
        from cv_pipeline.label_map import map_label

        self.assertEqual(map_label("wall_crack")[0], "broken")
        self.assertEqual(map_label("spalling")[0], "broken")
        self.assertEqual(map_label("algae")[0], "algae")
        self.assertEqual(map_label("damp")[0], "damp")
        self.assertEqual(map_label("efflorescence")[0], "damp")
        self.assertEqual(map_label("fungus")[0], "mold")
        self.assertEqual(map_label("clean")[0], "clean")

    def test_excluded_labels_return_none_canonical(self):
        """Excluded labels return (None, reason) not a canonical class."""
        from cv_pipeline.label_map import map_label

        cls, reason = map_label("peeling")
        self.assertIsNone(cls)
        self.assertIsNotNone(reason)
        self.assertIn("ambiguous", reason.lower())  # peeling reason mentions ambiguous

        cls2, reason2 = map_label("electrical_fault")
        self.assertIsNone(cls2)
        self.assertIsNotNone(reason2)
        self.assertIn("out of scope", reason2.lower())
        self.assertIn("out of scope", reason2.lower())

    def test_unknown_class_raises_value_error(self):
        """Unknown labels must raise ValueError — no silent mapping."""
        from cv_pipeline.label_map import map_label

        with self.assertRaises(ValueError) as ctx:
            map_label("paint_stain", "some_dataset")
        self.assertIn("paint_stain", str(ctx.exception))
        self.assertIn("Silent mapping is prohibited", str(ctx.exception))

    def test_mendeley_dataset_excluded_regardless_of_label(self):
        """All Mendeley images must be excluded regardless of label."""
        from cv_pipeline.label_map import map_label

        cls, reason = map_label("clean", "mendeley_concrete_dataset")
        self.assertIsNone(cls)
        self.assertIn("mendeley", reason.lower())

    def test_apply_label_mapping_dry_run(self):
        """apply_label_mapping in dry_run mode counts correctly without creating files."""
        from cv_pipeline.label_map import apply_label_mapping

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            target = Path(tmp) / "target"
            log_path = Path(tmp) / "exclusions.jsonl"

            # Create source structure with known labels
            (source / "algae").mkdir(parents=True)
            (source / "peeling").mkdir(parents=True)  # excluded
            (source / "wall_crack").mkdir(parents=True)  # → broken

            # Write dummy images
            for label_dir in [source / "algae", source / "peeling", source / "wall_crack"]:
                for i in range(3):
                    img = Image.new("RGB", (50, 50), color=(i * 80, i * 80, i * 80))
                    img.save(label_dir / f"img_{i}.jpg")

            counts = apply_label_mapping(
                source_dir=source,
                target_raw_dir=target,
                exclusion_log_path=log_path,
                source_dataset_name="test_dataset",
                dry_run=True,
            )

            # algae: 3 accepted, wall_crack→broken: 3 accepted, peeling: 3 excluded
            self.assertEqual(counts["accepted"], 6)
            self.assertEqual(counts["excluded"], 3)
            # No files should exist in target (dry run)
            self.assertFalse(target.exists())

    def test_apply_label_mapping_creates_exclusion_log(self):
        """apply_label_mapping writes JSONL exclusion log for excluded images."""
        from cv_pipeline.label_map import apply_label_mapping

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            target = Path(tmp) / "target"
            log_path = Path(tmp) / "exclusions.jsonl"

            (source / "electrical_fault").mkdir(parents=True)
            img = Image.new("RGB", (50, 50), color=(100, 100, 100))
            img.save(source / "electrical_fault" / "fault_001.jpg")

            apply_label_mapping(
                source_dir=source,
                target_raw_dir=target,
                exclusion_log_path=log_path,
                source_dataset_name="test_source",
                dry_run=False,
            )

            self.assertTrue(log_path.exists())
            with open(log_path) as f:
                records = [json.loads(line) for line in f if line.strip()]

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["filename"], "fault_001.jpg")
            self.assertEqual(records[0]["source_label"], "electrical_fault")
            self.assertIn("out of scope", records[0]["reason"].lower())


# ---------------------------------------------------------------------------
# Dataset integrity check tests
# ---------------------------------------------------------------------------
class TestDatasetCheck(unittest.TestCase):

    def _make_dataset_dir(self, tmp: str, splits: dict) -> Path:
        """
        Helper to create a dataset dir structure.
        splits = {"train": {"algae": 5, "broken": 10, ...}, "val": {...}}
        """
        base = Path(tmp) / "dataset"
        for split, classes in splits.items():
            for cls, n in classes.items():
                cls_dir = base / split / cls
                cls_dir.mkdir(parents=True)
                for i in range(n):
                    img = Image.new("RGB", (20, 20), color=(i * 10, i * 5, 0))
                    img.save(cls_dir / f"{cls}_{i}.jpg")
        return base

    def test_ready_dataset_passes(self):
        """A correctly structured dataset with all classes is marked ready."""
        from cv_pipeline.dataset_check import check_dataset_integrity, CANONICAL_CLASSES

        classes = {cls: 5 for cls in CANONICAL_CLASSES}
        with tempfile.TemporaryDirectory() as tmp:
            dataset_dir = self._make_dataset_dir(tmp, {"train": classes, "val": classes})
            report = check_dataset_integrity(dataset_dir)

        self.assertTrue(report["is_ready_for_training"])
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["class_order_ok"])

    def test_missing_class_dir_reports_error(self):
        """Dataset with extra non-CANONICAL class dir triggers P3 error."""
        from cv_pipeline.dataset_check import check_dataset_integrity, CANONICAL_CLASSES

        classes = {cls: 3 for cls in CANONICAL_CLASSES}
        with tempfile.TemporaryDirectory() as tmp:
            dataset_dir = self._make_dataset_dir(tmp, {"train": classes, "val": classes})
            # Add a rogue class directory
            (dataset_dir / "train" / "unknown_class").mkdir()
            report = check_dataset_integrity(dataset_dir)

        # Should have a P3 error about class order mismatch
        self.assertTrue(any("P3" in e for e in report["errors"]))
        self.assertFalse(report["is_ready_for_training"])

    def test_majority_class_baseline_reported(self):
        """Majority-class baseline accuracy is reported for train split."""
        from cv_pipeline.dataset_check import check_dataset_integrity, CANONICAL_CLASSES

        # Give "broken" 50 samples, rest 10 each
        classes = {cls: 10 for cls in CANONICAL_CLASSES}
        classes["broken"] = 50
        with tempfile.TemporaryDirectory() as tmp:
            dataset_dir = self._make_dataset_dir(tmp, {"train": classes, "val": {cls: 5 for cls in CANONICAL_CLASSES}})
            report = check_dataset_integrity(dataset_dir)

        total = 10 * 4 + 50  # 90
        expected_baseline = round(50 / total, 4)
        actual_baseline = report["splits"]["train"]["majority_class_baseline_accuracy"]
        self.assertAlmostEqual(actual_baseline, expected_baseline, places=3)


# ---------------------------------------------------------------------------
# Field eval isolation tests
# ---------------------------------------------------------------------------
class TestFieldEval(unittest.TestCase):

    def test_field_eval_labels_total_25(self):
        """FIELD_EVAL_LABELS must have exactly 25 entries (the 25 human-reviewed images)."""
        from cv_pipeline.field_eval import FIELD_EVAL_LABELS
        self.assertEqual(len(FIELD_EVAL_LABELS), 25)

    def test_field_eval_labels_only_canonical_classes(self):
        """All FIELD_EVAL_LABELS values must be canonical class names."""
        from cv_pipeline.field_eval import FIELD_EVAL_LABELS, CANONICAL_CLASSES
        for filename, label in FIELD_EVAL_LABELS.items():
            self.assertIn(label, CANONICAL_CLASSES, msg=f"'{filename}' has invalid label '{label}'")

    def test_field_eval_labels_class_distribution(self):
        """Verify known class distribution in FIELD_EVAL_LABELS."""
        from cv_pipeline.field_eval import FIELD_EVAL_LABELS
        from collections import Counter
        dist = Counter(FIELD_EVAL_LABELS.values())
        self.assertEqual(dist["algae"], 3)
        self.assertEqual(dist["broken"], 8)
        self.assertEqual(dist["clean"], 7)
        self.assertEqual(dist["damp"], 6)
        self.assertEqual(dist["mold"], 1)

    def test_build_field_eval_dry_run_no_files_written(self):
        """build_field_eval_set in dry_run must not create any directories or files."""
        from cv_pipeline.field_eval import build_field_eval_set

        with tempfile.TemporaryDirectory() as tmp:
            # Create mock source with 1 known image
            source = Path(tmp) / "unsorted_images"
            source.mkdir()

            # Write one known field image
            img = Image.new("RGB", (100, 100), color=(10, 20, 30))
            fname = "WhatsApp Image 2026-09-11 at 15.56.32.jpeg"
            img.save(source / fname)

            field_eval_dir = Path(tmp) / "field_eval"
            result = build_field_eval_set(source, field_eval_dir, dry_run=True)

            # In dry_run: field_eval_dir must NOT be created
            self.assertFalse(field_eval_dir.exists())
            # But the result should show 1 image would be copied
            self.assertEqual(result["total_copied"], 1)
            self.assertEqual(result["per_class"]["broken"], 1)

    def test_build_field_eval_set_creates_correct_structure(self):
        """build_field_eval_set creates per-class subdirs and copies images."""
        from cv_pipeline.field_eval import build_field_eval_set, CANONICAL_CLASSES

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "unsorted_images"
            source.mkdir()

            # Write 2 known field images (one broken, one clean)
            for fname in [
                "WhatsApp Image 2026-09-11 at 15.56.32.jpeg",   # → broken
                "WhatsApp Image 2026-09-11 at 15.56.44.jpeg",   # → clean
            ]:
                img = Image.new("RGB", (80, 80), color=(50, 50, 50))
                img.save(source / fname)

            field_eval_dir = Path(tmp) / "field_eval"
            result = build_field_eval_set(source, field_eval_dir, dry_run=False)

            self.assertEqual(result["total_copied"], 2)
            self.assertEqual(result["per_class"]["broken"], 1)
            self.assertEqual(result["per_class"]["clean"], 1)
            self.assertTrue((field_eval_dir / "broken").exists())
            self.assertTrue((field_eval_dir / "clean").exists())


# ---------------------------------------------------------------------------
# Existing CV training pipeline tests (preserved)
# ---------------------------------------------------------------------------
class TestExistingCVPipelineStillPasses(unittest.TestCase):
    """Ensure existing CV pipeline tests are still green after our changes."""

    def test_class_names_and_indices_clean_damp_algae_mold_broken(self):
        """P3 fix: WALL_CONDITION_CLASSES order is clean, damp, algae, mold, broken."""
        from backend.cv.model import WALL_CONDITION_CLASSES
        expected = ["clean", "damp", "algae", "mold", "broken"]
        self.assertEqual(WALL_CONDITION_CLASSES, expected)

    def test_model_output_dimension_is_5(self):
        """build_efficientnet_b0 still outputs exactly 5 classes."""
        import torch
        from backend.cv.model import build_efficientnet_b0
        model = build_efficientnet_b0(pretrained=False)
        self.assertEqual(model.classifier[1].out_features, 5)
        dummy = torch.randn(2, 3, 224, 224)
        with torch.no_grad():
            out = model(dummy)
        self.assertEqual(out.shape, (2, 5))

    def test_checkpoint_compatibility_with_inference_service(self):
        """A saved state_dict with 5 classes is directly loadable."""
        import torch
        from backend.cv.model import build_efficientnet_b0
        model = build_efficientnet_b0(num_classes=5, pretrained=False)
        with tempfile.NamedTemporaryFile(suffix=".pth") as f:
            torch.save(model.state_dict(), f.name)
            loaded = build_efficientnet_b0(num_classes=5, pretrained=False)
            state_dict = torch.load(f.name, map_location="cpu")
            loaded.load_state_dict(state_dict)
            loaded.eval()
            dummy = torch.randn(1, 3, 224, 224)
            with torch.no_grad():
                out = loaded(dummy)
            self.assertEqual(out.shape, (1, 5))

    def test_broken_scoring_uses_index_4(self):
        """broken is at index 4 (clean, damp, algae, mold, broken). Scoring must still work."""
        from backend.services.cv_model import _result_from_probabilities

        # [clean=0.10, damp=0.10, algae=0.10, mold=0.10, broken=0.60]
        # broken >= 0.25 -> defect
        # score = 100*0.10 + 70*0.10 + 50*0.10 + 30*0.10 + 20*0.60
        #       = 10 + 7 + 5 + 3 + 12 = 37.0
        result = _result_from_probabilities([0.10, 0.10, 0.10, 0.10, 0.60])
        self.assertEqual(result.predicted_class, "broken")
        self.assertEqual(result.confidence, 0.60)
        self.assertIn("broken", result.defects_detected)
        self.assertAlmostEqual(result.structural_score, 37.0, places=1)

    def test_empty_dataset_training_safety_still_works(self):
        """Training pipeline still safely halts on empty dataset."""
        from backend.cv.train import train_wall_condition_model
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result = train_wall_condition_model(
                data_dir=str(tmp_path),
                output_model_path=str(tmp_path / "model.pth"),
                output_metrics_path=str(tmp_path / "metrics.json"),
                epochs=1,
            )
        self.assertEqual(result["status"], "cancelled_no_dataset")
        self.assertEqual(result["valid_samples_count"], 0)


if __name__ == "__main__":
    unittest.main()
