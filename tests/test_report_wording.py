import unittest

from backend.services.report import generate_report


class ReportWordingTests(unittest.IsolatedAsyncioTestCase):
    async def test_provisional_report_uses_non_definitive_rating_and_discloses_coverage(self):
        report = await generate_report(
            address="Test locality",
            property_type="Apartment",
            overall_score=91.5,
            is_provisional=True,
            active_modules_count=2,
            score_weight_coverage=50.0,
        )

        self.assertIsNotNone(report)
        self.assertIn("Score 91.5/100", report.summary)
        self.assertIn("Provisional Favorable Trend (Incomplete Assessment)", report.summary)
        self.assertNotIn("Excellent / High Prime Value", report.summary)
        self.assertIn("Active modules: 2 / 4", report.summary)
        self.assertIn("Weight coverage: 50.0%", report.summary)
        self.assertIn("must not be treated as a definitive overall valuation", report.recommendations[0])

    async def test_complete_report_can_use_final_rating_and_discloses_coverage(self):
        report = await generate_report(
            address="Test locality",
            property_type="Apartment",
            overall_score=91.5,
            is_provisional=False,
            active_modules_count=4,
            score_weight_coverage=100.0,
        )

        self.assertIsNotNone(report)
        self.assertIn("Final Composite Rating: Score 91.5/100 (Excellent / High Prime Value).", report.summary)
        self.assertIn("Active modules: 4 / 4", report.summary)
        self.assertIn("Weight coverage: 100.0%", report.summary)
