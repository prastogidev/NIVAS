import asyncio
import base64
import io
import unittest
from unittest.mock import patch, MagicMock
import numpy as np
from PIL import Image
import torch

from backend.models.score import ImageInfo, CVModelResult
from backend.services.cv_model import (
    run_cv_analysis,
    _extract_image_candidates,
    _image_signature,
    _result_from_probabilities,
    WALL_CONDITION_CLASSES,
)


def create_test_image_b64(noise_seed: int = 42) -> str:
    """Create a non-blurry test image in base64 format."""
    rng = np.random.RandomState(noise_seed)
    arr = (rng.rand(120, 120, 3) * 255).astype(np.uint8)
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


class MultiImageCVAnalysisTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.img1_b64 = create_test_image_b64(101)
        self.img2_b64 = create_test_image_b64(102)
        self.img3_b64 = create_test_image_b64(103)
        self.thermal_b64 = create_test_image_b64(999)

    def test_extract_image_candidates_deduplication(self):
        """Test 5: Primary image_base64 is not duplicated when also present in images[]."""
        image_info = ImageInfo(
            image_base64=self.img1_b64,
            file_name="living_room.jpg",
            image_type="RGB",
            images=[
                {"image_base64": self.img1_b64, "file_name": "living_room.jpg", "image_type": "RGB"},
                {"image_base64": self.img2_b64, "file_name": "balcony.jpg", "image_type": "RGB"},
            ]
        )
        candidates = _extract_image_candidates(image_info)
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]["file_name"], "living_room.jpg")
        self.assertEqual(candidates[1]["file_name"], "balcony.jpg")

    def test_extract_image_candidates_thermal_filtering(self):
        """Test 4: Thermal images are excluded from RGB CV candidate list."""
        image_info = ImageInfo(
            thermal_base64=self.thermal_b64,
            images=[
                {"image_base64": self.img1_b64, "file_name": "living_room.jpg", "image_type": "RGB"},
                {"image_base64": self.thermal_b64, "file_name": "thermal_scan.jpg", "image_type": "Thermal"},
                {"image_base64": self.img2_b64, "file_name": "balcony.jpg", "image_type": "RGB"},
            ]
        )
        candidates = _extract_image_candidates(image_info)
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]["file_name"], "living_room.jpg")
        self.assertEqual(candidates[1]["file_name"], "balcony.jpg")

    @patch("backend.services.cv_model.build_efficientnet_b0")
    async def test_single_image_cv_analysis(self, mock_build_model):
        """Test 1: Single image generates exactly 1 inference and 1 visual evidence item."""
        mock_model = MagicMock()
        clean_logits = torch.tensor([[5.0, 0.0, 0.0, 0.0, 0.0]])
        mock_model.return_value = clean_logits
        mock_build_model.return_value = mock_model

        image_info = ImageInfo(
            image_base64=self.img1_b64,
            file_name="living_room.jpg",
            image_type="RGB"
        )
        result = await run_cv_analysis(image_info)

        self.assertIsNotNone(result)
        self.assertEqual(mock_model.call_count, 1)
        self.assertEqual(len(result.visual_evidence), 1)
        self.assertEqual(result.visual_evidence[0].file_name, "living_room.jpg")
        self.assertEqual(result.visual_evidence[0].predicted_class, "clean")
        self.assertFalse(result.visual_evidence[0].is_video_frame)

    @patch("backend.services.cv_model.build_efficientnet_b0")
    async def test_three_rgb_images_cv_analysis(self, mock_build_model):
        """Test 2: Three RGB images generate 3 inferences and 3 visual evidence items in order."""
        mock_model = MagicMock()
        mock_model.return_value = torch.tensor([[5.0, 0.0, 0.0, 0.0, 0.0]])
        mock_build_model.return_value = mock_model

        image_info = ImageInfo(
            images=[
                {"image_base64": self.img1_b64, "file_name": "room1.jpg", "image_type": "RGB"},
                {"image_base64": self.img2_b64, "file_name": "room2.jpg", "image_type": "RGB"},
                {"image_base64": self.img3_b64, "file_name": "room3.jpg", "image_type": "RGB"},
            ]
        )
        result = await run_cv_analysis(image_info)

        self.assertIsNotNone(result)
        self.assertEqual(mock_model.call_count, 3)
        self.assertEqual(len(result.visual_evidence), 3)
        self.assertEqual(result.visual_evidence[0].file_name, "room1.jpg")
        self.assertEqual(result.visual_evidence[1].file_name, "room2.jpg")
        self.assertEqual(result.visual_evidence[2].file_name, "room3.jpg")

    @patch("backend.services.cv_model.build_efficientnet_b0")
    async def test_multiple_images_different_classes_and_aggregation(self, mock_build_model):
        """Test 3: Multiple images with different predicted classes (clean, algae, mold).
        Verifies that each appears in visual_evidence with correct class/confidence
        and aggregate condition score is calculated according to the scoring formula.
        """
        mock_model = MagicMock()
        logits_img1 = torch.tensor([[10.0, 0.0, 0.0, 0.0, 0.0]])  # clean ~1.0
        logits_img2 = torch.tensor([[0.0, 0.0, 10.0, 0.0, 0.0]])  # algae ~1.0
        logits_img3 = torch.tensor([[0.0, 0.0, 0.0, 10.0, 0.0]])  # mold ~1.0
        mock_model.side_effect = [logits_img1, logits_img2, logits_img3]
        mock_build_model.return_value = mock_model

        image_info = ImageInfo(
            images=[
                {"image_base64": self.img1_b64, "file_name": "living_room.jpg", "image_type": "RGB"},
                {"image_base64": self.img2_b64, "file_name": "balcony_wall.jpg", "image_type": "RGB"},
                {"image_base64": self.img3_b64, "file_name": "ceiling_damp.jpg", "image_type": "RGB"},
            ]
        )
        result = await run_cv_analysis(image_info)

        self.assertIsNotNone(result)
        self.assertEqual(len(result.visual_evidence), 3)

        # Check visual evidence items
        ev1 = result.visual_evidence[0]
        self.assertEqual(ev1.file_name, "living_room.jpg")
        self.assertEqual(ev1.predicted_class, "clean")
        self.assertGreater(ev1.confidence, 0.9)

        ev2 = result.visual_evidence[1]
        self.assertEqual(ev2.file_name, "balcony_wall.jpg")
        self.assertEqual(ev2.predicted_class, "algae")
        self.assertGreater(ev2.confidence, 0.9)

        ev3 = result.visual_evidence[2]
        self.assertEqual(ev3.file_name, "ceiling_damp.jpg")
        self.assertEqual(ev3.predicted_class, "mold")
        self.assertGreater(ev3.confidence, 0.9)

        # Check aggregate calculations:
        # Probabilities average to ~1/3 clean, ~1/3 algae, ~1/3 mold
        # Both algae (0.33 >= 0.25) and mold (0.33 >= 0.25) are detected defects
        self.assertIn("algae", result.defects_detected)
        self.assertIn("mold", result.defects_detected)
        # Expected structural score ~ (100 * 1/3) + (50 * 1/3) + (30 * 1/3) = (100 + 50 + 30)/3 = 60.0
        self.assertAlmostEqual(result.structural_score, 60.0, delta=1.0)

    @patch("backend.services.cv_model.build_efficientnet_b0")
    async def test_thermal_image_does_not_enter_rgb_cv(self, mock_build_model):
        """Test 4: Pure thermal request or thermal item inside images does not enter CV."""
        mock_model = MagicMock()
        mock_build_model.return_value = mock_model

        image_info = ImageInfo(
            thermal_base64=self.thermal_b64,
            image_base64=self.thermal_b64,
            image_type="Thermal",
            file_name="thermal_ir.jpg"
        )
        result = await run_cv_analysis(image_info)
        self.assertIsNone(result)
        mock_model.assert_not_called()

    @patch("backend.services.cv_model.build_efficientnet_b0")
    async def test_duplicate_primary_image_does_not_cause_duplicate_inference(self, mock_build_model):
        """Test 5: image_base64 duplicated from images[0] runs inference once per unique image."""
        mock_model = MagicMock()
        mock_model.return_value = torch.tensor([[5.0, 0.0, 0.0, 0.0, 0.0]])
        mock_build_model.return_value = mock_model

        image_info = ImageInfo(
            image_base64=self.img1_b64,
            file_name="img1.jpg",
            image_type="RGB",
            images=[
                {"image_base64": self.img1_b64, "file_name": "img1.jpg", "image_type": "RGB"},
                {"image_base64": self.img2_b64, "file_name": "img2.jpg", "image_type": "RGB"},
            ]
        )
        result = await run_cv_analysis(image_info)
        self.assertIsNotNone(result)
        # Exactly 2 inferences, not 3
        self.assertEqual(mock_model.call_count, 2)
        self.assertEqual(len(result.visual_evidence), 2)

    @patch("backend.services.cv_model.build_efficientnet_b0")
    async def test_legacy_single_image_backward_compatibility(self, mock_build_model):
        """Test 6: Legacy request with only image_base64 (no images field) works 100% as before."""
        mock_model = MagicMock()
        mock_model.return_value = torch.tensor([[10.0, 0.0, 0.0, 0.0, 0.0]])
        mock_build_model.return_value = mock_model

        legacy_info = ImageInfo(
            image_base64=self.img1_b64,
            file_name="single_wall.jpg",
            image_type="RGB"
        )
        result = await run_cv_analysis(legacy_info)
        self.assertIsNotNone(result)
        self.assertEqual(mock_model.call_count, 1)
        self.assertEqual(result.predicted_class, "clean")
        self.assertAlmostEqual(result.structural_score, 100.0, delta=0.1)
        self.assertEqual(len(result.visual_evidence), 1)
        self.assertEqual(result.visual_evidence[0].file_name, "single_wall.jpg")

    @patch("backend.services.cv_model.build_efficientnet_b0")
    async def test_corrupted_image_handling(self, mock_build_model):
        """Test: Corrupted image is gracefully skipped while valid image is analyzed."""
        mock_model = MagicMock()
        mock_model.return_value = torch.tensor([[10.0, 0.0, 0.0, 0.0, 0.0]])
        mock_build_model.return_value = mock_model

        image_info = ImageInfo(
            images=[
                {"image_base64": "corrupt_base64_data", "file_name": "corrupt.jpg", "image_type": "RGB"},
                {"image_base64": self.img1_b64, "file_name": "valid.jpg", "image_type": "RGB"},
            ]
        )
        result = await run_cv_analysis(image_info)
        self.assertIsNotNone(result)
        self.assertEqual(mock_model.call_count, 1)
        self.assertEqual(len(result.visual_evidence), 1)
        self.assertEqual(result.visual_evidence[0].file_name, "valid.jpg")


if __name__ == "__main__":
    unittest.main()
