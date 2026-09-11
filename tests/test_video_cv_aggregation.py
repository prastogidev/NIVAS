import unittest

from backend.services.cv_model import _result_from_probabilities


class VideoCVAggregationTests(unittest.TestCase):
    def test_aggregated_frame_probabilities_use_existing_cv_score_mapping(self):
        # These represent the averaged outputs of valid sampled frames, not
        # fabricated model output. The helper applies the existing score rules.
        result = _result_from_probabilities([0.60, 0.25, 0.10, 0.05])

        self.assertEqual(result.predicted_class, "clean")
        self.assertEqual(result.confidence, 0.6)
        self.assertEqual(result.defects_detected, ["damp"])
        self.assertEqual(result.defect_coverage_ratio, 0.25)
        self.assertEqual(result.structural_score, 84.0)
        self.assertFalse(result.is_blurry)

    def test_aggregated_frame_probabilities_with_broken_class(self):
        # 5 probabilities: clean=0.40, damp=0.20, algae=0.05, mold=0.05, broken=0.30
        # broken >= 0.25 -> defects_detected includes 'broken'
        # score = 100*0.40 + 70*0.20 + 50*0.05 + 30*0.05 + 20*0.30 = 40 + 14 + 2.5 + 1.5 + 6 = 64.0
        result = _result_from_probabilities([0.40, 0.20, 0.05, 0.05, 0.30])

        self.assertEqual(result.predicted_class, "clean")
        self.assertEqual(result.confidence, 0.40)
        self.assertIn("broken", result.defects_detected)
        self.assertEqual(result.defect_coverage_ratio, 0.30)
        self.assertEqual(result.structural_score, 64.0)
        self.assertFalse(result.is_blurry)
