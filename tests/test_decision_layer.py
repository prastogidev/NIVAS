import unittest
from backend.models.score import (
    LocationResult,
    InfrastructureSummary,
    PriceBenchmarkResult,
    CVModelResult,
    ThermalModuleResult,
    AQIResult,
    ScoreRequest,
)
from backend.services.decision import generate_decision_insights
from backend.api.score import evaluate_single_property


class TestExplainableDecisionLayer(unittest.TestCase):
    def test_full_coverage_clean_property(self):
        """Test decision layer with 100% module coverage and clean property signals."""
        loc = LocationResult(
            locality="Dwarka Sector 12, New Delhi",
            latitude=28.5921,
            longitude=77.0460,
            risk_score=85.0,
            infrastructure=InfrastructureSummary(
                hospitals_count=3,
                schools_count=4,
                railway_stations_count=2,
                major_roads_count=10,
            ),
        )
        price = PriceBenchmarkResult(
            estimated_price_per_sqft=8500.0,
            fairness_score=90.0,
            source="Demo Benchmark Dataset",
            sample_count=15,
        )
        cv = CVModelResult(
            predicted_class="clean",
            confidence=0.96,
            structural_score=95.0,
            defects_detected=[],
            defect_coverage_ratio=0.0,
            is_blurry=False,
        )
        thermal = ThermalModuleResult(
            mean_temp=26.4,
            min_temp=25.0,
            max_temp=28.0,
            thermal_anomaly_delta=3.0,
            anomalies_detected_count=0,
            insulation_score=92.0,
            sensor_status="Connected (MLX90640)",
        )
        aqi = AQIResult(
            aqi_value=75.0,
            category="Moderate",
            station_name="Dwarka Sector 8 Station",
            environmental_score=80.0,
        )

        insights = generate_decision_insights(
            address="Dwarka Sector 12, New Delhi",
            property_type="Apartment",
            overall_score=90.0,
            is_provisional=False,
            active_modules_count=4,
            score_weight_coverage=100.0,
            location=loc,
            aqi=aqi,
            price=price,
            cv=cv,
            thermal=thermal,
        )

        self.assertIsNotNone(insights)
        self.assertEqual(insights.confidence_level, "High")
        self.assertEqual(insights.verdict, "Strong Investment / Acquisition Contender")
        self.assertIn("100.0% weight coverage", insights.coverage_summary)

        # Check positive factors
        categories = [f.category for f in insights.positive_factors]
        self.assertIn("location", categories)
        self.assertIn("price", categories)
        self.assertIn("cv", categories)
        self.assertIn("thermal", categories)
        self.assertIn("aqi", categories)

        # Check evidence integrity
        cv_factor = next(f for f in insights.positive_factors if f.category == "cv")
        self.assertEqual(cv_factor.evidence["predicted_class"], "clean")
        self.assertEqual(cv_factor.evidence["structural_score"], 95.0)

        # Ensure legal check is present
        check_categories = [c.category for c in insights.recommended_checks]
        self.assertIn("legal", check_categories)

    def test_defect_and_overpricing_risks(self):
        """Test decision layer correctly flags dampness defect, thermal leaks, and price premium."""
        loc = LocationResult(
            locality="Lajpat Nagar",
            latitude=28.57,
            longitude=77.24,
            risk_score=50.0,
            infrastructure=InfrastructureSummary(hospitals_count=0, schools_count=0),
        )
        price = PriceBenchmarkResult(
            estimated_price_per_sqft=35000.0,
            fairness_score=45.0,
            source="Market Asking Rate",
        )
        cv = CVModelResult(
            predicted_class="damp",
            confidence=0.88,
            structural_score=50.0,
            defects_detected=["damp", "efflorescence"],
            defect_coverage_ratio=0.35,
        )
        thermal = ThermalModuleResult(
            mean_temp=29.0,
            thermal_anomaly_delta=7.5,
            anomalies_detected_count=14,
            insulation_score=40.0,
        )

        insights = generate_decision_insights(
            address="Lajpat Nagar",
            property_type="Commercial Space",
            overall_score=46.5,
            is_provisional=False,
            active_modules_count=4,
            score_weight_coverage=100.0,
            location=loc,
            price=price,
            cv=cv,
            thermal=thermal,
        )

        self.assertIsNotNone(insights)
        self.assertEqual(insights.verdict, "High Risk Property (Substantial Defects / Overpriced)")

        # Verify flagged risks
        risk_categories = [r.category for r in insights.key_risks]
        self.assertIn("cv", risk_categories)
        self.assertIn("thermal", risk_categories)
        self.assertIn("price", risk_categories)
        self.assertIn("location", risk_categories)

        # Verify moisture check is high priority
        structural_checks = [c for c in insights.recommended_checks if c.category == "structural"]
        self.assertTrue(any(c.priority == "high" and "moisture" in c.action.lower() for c in structural_checks))

    def test_provisional_incomplete_assessment(self):
        """Test decision layer with partial signals (only Location and Price active)."""
        loc = LocationResult(
            locality="Rohini Sector 8",
            latitude=28.71,
            longitude=77.06,
            risk_score=80.0,
        )
        price = PriceBenchmarkResult(
            estimated_price_per_sqft=7200.0,
            fairness_score=85.0,
        )

        insights = generate_decision_insights(
            address="Rohini Sector 8, New Delhi",
            property_type="Apartment",
            overall_score=82.5,
            is_provisional=True,
            active_modules_count=2,
            score_weight_coverage=50.0,
            location=loc,
            price=price,
            cv=None,
            thermal=None,
        )

        self.assertIsNotNone(insights)
        self.assertEqual(insights.confidence_level, "Medium")
        self.assertIn("Provisional Favorable Candidate", insights.verdict)

        # Verify provisional risk is flagged
        provisional_risks = [r for r in insights.key_risks if r.category == "composite"]
        self.assertTrue(len(provisional_risks) > 0)
        self.assertEqual(provisional_risks[0].evidence["score_weight_coverage"], 50.0)

        # Verify missing module fallback checks
        check_categories = [c.category for c in insights.recommended_checks]
        self.assertIn("structural", check_categories)
        self.assertIn("thermal", check_categories)

    def test_determinism_and_reproducibility(self):
        """Verify identical inputs produce identical deterministic insights across iterations."""
        loc = LocationResult(risk_score=75.0, locality="Dwarka")
        price = PriceBenchmarkResult(fairness_score=85.0, estimated_price_per_sqft=8000.0)

        runs = [
            generate_decision_insights(
                address="Dwarka",
                property_type="Apartment",
                overall_score=80.0,
                is_provisional=True,
                active_modules_count=2,
                score_weight_coverage=50.0,
                location=loc,
                price=price,
            )
            for _ in range(5)
        ]

        first = runs[0].model_dump()
        for r in runs[1:]:
            self.assertEqual(first, r.model_dump())


if __name__ == "__main__":
    unittest.main()
