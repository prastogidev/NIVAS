import unittest
from backend.models.score import (
    ScoreRequest,
    ScoreResponse,
    LocationResult,
    InfrastructureSummary,
    PriceBenchmarkResult,
    CVModelResult,
    ThermalModuleResult,
    AQIResult,
)
from backend.services.compare import compare_inspection_results


class TestPropertyCompareAudit(unittest.TestCase):
    def setUp(self):
        self.req_a = ScoreRequest(address="Dwarka Sector 12, New Delhi", property_type="Apartment")
        self.req_b = ScoreRequest(address="Lajpat Nagar 2, New Delhi", property_type="Apartment")

    def test_symmetric_full_coverage_high_confidence(self):
        """Test comparison when both properties have 100% module coverage."""
        resp_a = ScoreResponse(
            location=LocationResult(
                locality="Dwarka Sector 12",
                latitude=28.59,
                longitude=77.04,
                risk_score=85.0,
                infrastructure=InfrastructureSummary(hospitals_count=6, schools_count=5, railway_stations_count=4, major_roads_count=8),
            ),
            price=PriceBenchmarkResult(
                estimated_price_per_sqft=8500.0,
                fairness_score=90.0,
                source="Propstack Registry",
                sample_count=12,
            ),
            cv=CVModelResult(
                predicted_class="clean",
                confidence=0.94,
                structural_score=95.0,
            ),
            thermal=ThermalModuleResult(
                mean_temp=26.0,
                thermal_anomaly_delta=2.5,
                anomalies_detected_count=0,
                insulation_score=90.0,
                sensor_status="Connected (MLX90640)",
            ),
            aqi=AQIResult(
                aqi_value=70.0,
                category="Moderate",
                station_name="Dwarka Station",
                environmental_score=85.0,
            ),
            overall_score=89.5,
            is_provisional=False,
            active_modules_count=4,
            score_weight_coverage=100.0,
        )

        resp_b = ScoreResponse(
            location=LocationResult(
                locality="Lajpat Nagar",
                latitude=28.57,
                longitude=77.24,
                risk_score=75.0,
                infrastructure=InfrastructureSummary(hospitals_count=2, schools_count=2, railway_stations_count=2, major_roads_count=5),
            ),
            price=PriceBenchmarkResult(
                estimated_price_per_sqft=28000.0,
                fairness_score=70.0,
                source="Cached Demo Benchmark Dataset",
                sample_count=4,
            ),
            cv=CVModelResult(
                predicted_class="damp",
                confidence=0.82,
                structural_score=60.0,
                defect_coverage_ratio=0.20,
            ),
            thermal=ThermalModuleResult(
                mean_temp=28.5,
                thermal_anomaly_delta=6.2,
                anomalies_detected_count=8,
                insulation_score=65.0,
                sensor_status="Connected (MLX90640)",
            ),
            aqi=AQIResult(
                aqi_value=175.0,
                category="Unhealthy",
                station_name="Lajpat Nagar Station",
                environmental_score=50.0,
            ),
            overall_score=67.5,
            is_provisional=False,
            active_modules_count=4,
            score_weight_coverage=100.0,
        )

        compare_res = compare_inspection_results(resp_a, resp_b, self.req_a, self.req_b)

        self.assertEqual(compare_res.comparison_confidence, "High")
        self.assertIsNone(compare_res.asymmetric_warning)
        self.assertEqual(compare_res.overall_winner, "Property A: Dwarka Sector 12, New Delhi")
        self.assertEqual(compare_res.overall_delta, 22.0)
        self.assertEqual(compare_res.coverage_a, 100.0)
        self.assertEqual(compare_res.coverage_b, 100.0)

        # Check dimensional explanations and provenances
        for diff in compare_res.module_differences:
            self.assertEqual(diff.coverage_status, "both_active")
            self.assertIsNotNone(diff.provenance_a)
            self.assertIsNotNone(diff.provenance_b)
            self.assertIsNotNone(diff.explanation)
            self.assertTrue(len(diff.explanation) > 10)

        # Check CV explanation specifically flags damp vs clean
        cv_diff = next(d for d in compare_res.module_differences if d.module_key == "cv")
        self.assertEqual(cv_diff.advantage, "Property A")
        self.assertIn("clean", cv_diff.explanation.lower())
        self.assertIn("damp", cv_diff.explanation.lower())

    def test_asymmetric_coverage_limited_confidence(self):
        """Test comparison when Property A has 80% coverage and Property B has 50% coverage."""
        resp_a = ScoreResponse(
            location=LocationResult(risk_score=80.0, locality="Dwarka"),
            price=PriceBenchmarkResult(fairness_score=85.0, estimated_price_per_sqft=8500.0, source="Demo Benchmark", sample_count=4),
            cv=CVModelResult(predicted_class="clean", confidence=0.90, structural_score=90.0),
            thermal=None,
            overall_score=85.0,
            is_provisional=True,
            active_modules_count=3,
            score_weight_coverage=80.0,
        )
        resp_b = ScoreResponse(
            location=LocationResult(risk_score=75.0, locality="Lajpat Nagar"),
            price=PriceBenchmarkResult(fairness_score=75.0, estimated_price_per_sqft=32000.0, source="Demo Benchmark", sample_count=4),
            cv=None,
            thermal=None,
            overall_score=75.0,
            is_provisional=True,
            active_modules_count=2,
            score_weight_coverage=50.0,
        )

        compare_res = compare_inspection_results(resp_a, resp_b, self.req_a, self.req_b)

        self.assertEqual(compare_res.comparison_confidence, "Limited")
        self.assertIsNotNone(compare_res.asymmetric_warning)
        self.assertIn("80.0% weight coverage", compare_res.asymmetric_warning)
        self.assertIn("50.0% weight coverage", compare_res.asymmetric_warning)

        # Check CV module handles asymmetric presence
        cv_diff = next(d for d in compare_res.module_differences if d.module_key == "cv")
        self.assertEqual(cv_diff.coverage_status, "only_a_active")
        self.assertEqual(cv_diff.advantage, "Property A")
        self.assertIn("Property A has verified visual wall scan", cv_diff.explanation)
        self.assertEqual(cv_diff.provenance_b, "Not assessed (No Image)")


if __name__ == "__main__":
    unittest.main()
