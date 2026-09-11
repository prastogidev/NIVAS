"""
Unit tests for the NIVAS Computer Vision Model Training Pipeline.
Verifies metrics computation, transforms, class weights, checkpoint compatibility,
empty-dataset safety, and 5-class support (clean, damp, algae, mold, broken).
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from PIL import Image
import torch
import torch.nn as nn

from backend.cv.model import build_efficientnet_b0, WALL_CONDITION_CLASSES
from backend.cv.metrics import compute_classification_metrics
from backend.cv.train import (
    get_train_transforms,
    get_val_transforms,
    compute_class_weights,
    verify_real_dataset_exists,
    train_wall_condition_model,
)
from backend.cv.verify_dataset import verify_wall_condition_dataset
from backend.cv.split_dataset import split_wall_dataset
from backend.services.cv_model import _result_from_probabilities


class TestCVTrainingPipeline(unittest.TestCase):

    def test_class_names_and_indices(self):
        """Verify the 5 standard classes exist in expected order and indexing."""
        expected_classes = ["clean", "damp", "algae", "mold", "broken"]
        self.assertEqual(WALL_CONDITION_CLASSES, expected_classes)
        self.assertEqual(len(WALL_CONDITION_CLASSES), 5)
        self.assertEqual(WALL_CONDITION_CLASSES[0], "clean")
        self.assertEqual(WALL_CONDITION_CLASSES[1], "damp")
        self.assertEqual(WALL_CONDITION_CLASSES[2], "algae")
        self.assertEqual(WALL_CONDITION_CLASSES[3], "mold")
        self.assertEqual(WALL_CONDITION_CLASSES[4], "broken")

    def test_classification_metrics_computation_5_classes(self):
        """Verify accurate multi-class classification metric calculations and 5x5 confusion matrix."""
        # 5 samples:
        # True:  0 (clean), 1 (damp), 2 (algae), 3 (mold), 4 (broken)
        # Pred:  0 (clean), 1 (damp), 2 (algae), 0 (clean - error!), 4 (broken)
        y_true = [0, 1, 2, 3, 4]
        y_pred = [0, 1, 2, 0, 4]

        metrics = compute_classification_metrics(
            y_true=y_true,
            y_pred=y_pred,
            class_names=WALL_CONDITION_CLASSES,
            loss=0.45,
        )

        self.assertEqual(metrics["total_samples"], 5)
        self.assertEqual(metrics["overall_accuracy"], 0.8)  # 4 out of 5 correct
        self.assertEqual(metrics["loss"], 0.45)

        # Class 0 ('clean'): True=1, Pred=2 (one TP, one FP from class 3)
        clean_m = metrics["per_class"]["clean"]
        self.assertEqual(clean_m["true_positives"], 1)
        self.assertEqual(clean_m["false_positives"], 1)
        self.assertEqual(clean_m["false_negatives"], 0)
        self.assertEqual(clean_m["precision"], 0.5)
        self.assertEqual(clean_m["recall"], 1.0)

        # Class 4 ('broken'): True=1, Pred=1 (one TP)
        broken_m = metrics["per_class"]["broken"]
        self.assertEqual(broken_m["true_positives"], 1)
        self.assertEqual(broken_m["false_positives"], 0)
        self.assertEqual(broken_m["false_negatives"], 0)
        self.assertEqual(broken_m["precision"], 1.0)
        self.assertEqual(broken_m["recall"], 1.0)
        self.assertEqual(broken_m["f1"], 1.0)

        # Class 3 ('mold'): True=1, Pred=0 (zero TP, zero FP, one FN)
        mold_m = metrics["per_class"]["mold"]
        self.assertEqual(mold_m["true_positives"], 0)
        self.assertEqual(mold_m["false_positives"], 0)
        self.assertEqual(mold_m["false_negatives"], 1)
        self.assertEqual(mold_m["precision"], 0.0)
        self.assertEqual(mold_m["recall"], 0.0)
        self.assertEqual(mold_m["f1"], 0.0)

        # Confusion Matrix: 5x5
        cm = metrics["confusion_matrix"]
        self.assertEqual(len(cm), 5)
        for row in cm:
            self.assertEqual(len(row), 5)
        self.assertEqual(cm[0][0], 1)  # clean predicted clean
        self.assertEqual(cm[3][0], 1)  # mold predicted clean
        self.assertEqual(cm[1][1], 1)  # damp predicted damp
        self.assertEqual(cm[2][2], 1)  # algae predicted algae
        self.assertEqual(cm[4][4], 1)  # broken predicted broken

    def test_compute_class_weights_5_classes(self):
        """Verify balanced class weight computation across all 5 classes."""
        class_counts = {"clean": 100, "damp": 50, "algae": 25, "mold": 25, "broken": 10}
        weights = compute_class_weights(class_counts, torch.device("cpu"))

        self.assertIsNotNone(weights)
        self.assertEqual(len(weights), 5)
        # Broken is rarest (10) -> highest weight
        self.assertTrue(weights[4] > weights[0])
        self.assertTrue(weights[4] > weights[1])
        self.assertTrue(weights[4] > weights[2])

    def test_transforms_output_dimensions(self):
        """Verify train and val transforms produce 3x224x224 normalized tensors."""
        img = Image.new("RGB", (300, 300), color=(128, 128, 128))
        train_tf = get_train_transforms()
        val_tf = get_val_transforms()

        train_tensor = train_tf(img)
        val_tensor = val_tf(img)

        self.assertEqual(train_tensor.shape, (3, 224, 224))
        self.assertEqual(val_tensor.shape, (3, 224, 224))

    def test_empty_dataset_training_safety(self):
        """Verify training pipeline safely halts without fabricating metrics if dataset is empty."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            out_model = tmp_path / "model.pth"
            out_metrics = tmp_path / "metrics.json"

            result = train_wall_condition_model(
                data_dir=str(tmp_path),
                output_model_path=str(out_model),
                output_metrics_path=str(out_metrics),
                epochs=1,
            )

            self.assertEqual(result["status"], "cancelled_no_dataset")
            self.assertEqual(result["valid_samples_count"], 0)
            self.assertFalse(out_model.exists())  # No fake model weights created
            self.assertTrue(out_metrics.exists())  # Status report written cleanly

    def test_model_output_dimension_is_5(self):
        """Verify that build_efficientnet_b0 default outputs exactly 5 classes."""
        model = build_efficientnet_b0(pretrained=False)
        self.assertEqual(model.classifier[1].out_features, 5)

        dummy_input = torch.randn(2, 3, 224, 224)
        with torch.no_grad():
            output = model(dummy_input)
        self.assertEqual(output.shape, (2, 5))

    def test_checkpoint_compatibility_with_inference_service(self):
        """Verify that a saved state_dict with 5 classes is directly loadable."""
        model = build_efficientnet_b0(num_classes=5, pretrained=False)
        with tempfile.NamedTemporaryFile(suffix=".pth") as tmp_file:
            torch.save(model.state_dict(), tmp_file.name)

            # Load into a fresh inference model instance
            loaded_model = build_efficientnet_b0(num_classes=5, pretrained=False)
            state_dict = torch.load(tmp_file.name, map_location="cpu")
            loaded_model.load_state_dict(state_dict)
            loaded_model.eval()

            dummy_input = torch.randn(1, 3, 224, 224)
            with torch.no_grad():
                output = loaded_model(dummy_input)

            self.assertEqual(output.shape, (1, 5))

    def test_broken_scoring_and_defect_detection(self):
        """Verify broken class is treated as defect and scored at 20.0."""
        # 5 probabilities: clean=0.10, damp=0.10, algae=0.10, mold=0.10, broken=0.60
        # Defect broken >= 0.25 -> detected_defects = ['broken']
        # Score = 100*0.1 + 70*0.1 + 50*0.1 + 30*0.1 + 20*0.6 = 10 + 7 + 5 + 3 + 12 = 37.0
        result = _result_from_probabilities([0.10, 0.10, 0.10, 0.10, 0.60])

        self.assertEqual(result.predicted_class, "broken")
        self.assertEqual(result.confidence, 0.60)
        self.assertIn("broken", result.defects_detected)
        self.assertEqual(result.defect_coverage_ratio, 0.60)
        self.assertEqual(result.structural_score, 37.0)


if __name__ == "__main__":
    unittest.main()
