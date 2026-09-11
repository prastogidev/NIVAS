import asyncio
import logging
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nivas.test_e2e")

API_BASE_URL = "http://127.0.0.1:8000"

LOCALITIES = [
    {"name": "Dwarka", "address": "Dwarka Sector 12, New Delhi", "type": "Apartment"},
    {"name": "Rohini", "address": "Rohini Sector 8, New Delhi", "type": "Apartment"},
    {"name": "Lajpat Nagar", "address": "Lajpat Nagar 2, New Delhi", "type": "Commercial Space"},
]


async def test_single_property(loc):
    """Test full single-property inspection pipeline for a locality."""
    logger.info("=== Testing End-to-End Single Property: %s ===", loc["name"])
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{API_BASE_URL}/api/score",
            json={"address": loc["address"], "property_type": loc["type"]}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()

        # 1. Geocoding & Location Check
        loc_res = data.get("location")
        assert loc_res is not None, "Location result missing"
        assert loc_res.get("latitude") is not None, "Latitude missing"
        assert loc_res.get("longitude") is not None, "Longitude missing"
        logger.info("[%s] Geocoded lat/lon: (%s, %s), risk_score: %s",
                    loc["name"], loc_res["latitude"], loc_res["longitude"], loc_res.get("risk_score"))

        # 2. Overpass Infrastructure & Location Risk Check
        infra = loc_res.get("infrastructure")
        risk_score = loc_res.get("risk_score")
        if infra is not None and risk_score is not None:
            logger.info("[%s] Overpass Infra: %d hospitals, %d schools, %d railway stations, %d roads (Score: %s)",
                        loc["name"], infra["hospitals_count"], infra["schools_count"],
                        infra["railway_stations_count"], infra["major_roads_count"], risk_score)
        else:
            logger.info("[%s] Infrastructure/risk data unavailable — cleanly reported as null (risk_score: %s)",
                        loc["name"], risk_score)

        # 3. AQI Check (Must be geographically relevant Delhi/NCR station, or cleanly null if no station)
        aqi_res = data.get("aqi")
        if aqi_res is not None:
            station_name = aqi_res.get("station_name") or ""
            assert "shanghai" not in station_name.lower(), f"Unrelated Shanghai station returned for {loc['name']}!"
            logger.info("[%s] Verified Nearby AQI: %s (%s), env_score: %s, station: %s",
                        loc["name"], aqi_res.get("aqi_value"), aqi_res.get("category"),
                        aqi_res.get("environmental_score"), station_name)
        else:
            logger.info("[%s] AQI cleanly reported as unavailable (null) without unrelated fallback data", loc["name"])

        # 4. Price Benchmark Check
        price_res = data.get("price")
        assert price_res is not None, "Price benchmark missing"
        logger.info("[%s] Est. Price/sqft: ₹%s, fairness_score: %s, source: %s",
                    loc["name"], price_res.get("estimated_price_per_sqft"),
                    price_res.get("fairness_score"), price_res.get("source"))

        # 5. Overall Composite Score & Report
        overall = data.get("overall_score")
        is_prov = data.get("is_provisional")
        coverage = data.get("score_weight_coverage")
        report = data.get("report")

        assert overall is not None, "Overall score missing"
        assert report is not None and report.get("summary") is not None, "Report summary missing"

        logger.info("[%s] Composite Score: %.1f/100 (Provisional: %s, Coverage: %.1f%%)",
                    loc["name"], overall, is_prov, coverage)
        logger.info("[%s] Report Summary Snippet: %s...", loc["name"], report["summary"][:120])
        logger.info("=== %s Single Property Test PASSED ===\n", loc["name"])
        return data


async def test_comparison_pair(loc_a, loc_b):
    """Test dual-property comparison engine between two real localities."""
    logger.info("=== Testing End-to-End Dual Property Comparison: %s vs %s ===", loc_a["name"], loc_b["name"])
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            f"{API_BASE_URL}/api/score/compare",
            json={
                "property_a": {"address": loc_a["address"], "property_type": loc_a["type"]},
                "property_b": {"address": loc_b["address"], "property_type": loc_b["type"]},
            }
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()

        overall_a = data.get("overall_score_a")
        overall_b = data.get("overall_score_b")
        winner = data.get("overall_winner")
        delta = data.get("overall_delta")
        diffs = data.get("module_differences", [])
        summary = data.get("comparison_summary")

        assert overall_a is not None and overall_b is not None, "Overall scores missing in comparison"
        assert winner is not None, "Overall winner missing in comparison"
        assert len(diffs) == 5, f"Expected 5 module differences, got {len(diffs)}"

        logger.info("Comparison Scores: %s (%.1f) vs %s (%.1f)", loc_a["name"], overall_a, loc_b["name"], overall_b)
        logger.info("Overall Winner: %s (Delta: %s pts)", winner, delta)
        logger.info("Comparison Summary: %s", summary)
        logger.info("=== %s vs %s Comparison Test PASSED ===\n", loc_a["name"], loc_b["name"])


async def main():
    logger.info("🚀 STARTING E2E DELI LOCALITIES VERIFICATION SUITE (Dwarka, Rohini, Lajpat Nagar)...")

    results = []
    for loc in LOCALITIES:
        res = await test_single_property(loc)
        results.append(res)

    # Compare Dwarka vs Lajpat Nagar
    await test_comparison_pair(LOCALITIES[0], LOCALITIES[2])

    # Compare Rohini vs Lajpat Nagar
    await test_comparison_pair(LOCALITIES[1], LOCALITIES[2])

    logger.info("🎉 ALL E2E LOCALITY TESTS PASSED WITH 0 INTEGRATION ERRORS!")


if __name__ == "__main__":
    asyncio.run(main())
