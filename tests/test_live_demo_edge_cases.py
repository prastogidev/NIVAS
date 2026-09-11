import asyncio
import logging
import httpx
from PIL import Image
import numpy as np

from backend.services.cv_model import compute_blur_variance
from backend.services.scoring import calculate_overall_score
from backend.services.air_quality import fetch_real_aqi, haversine_distance_km, MAX_AQI_STATION_DISTANCE_KM
from backend.models.score import LocationResult, PriceBenchmarkResult, CVModelResult, ThermalModuleResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nivas.test_live_demo")

API_BASE_URL = "http://127.0.0.1:8000"

# Global timeout used by all HTTP-facing tests — must exceed worst-case backend
# pipeline time: geocoding (~5s) + Overpass (~3.5s × up to 4 mirrors = 14s) = ~19s
TEST_HTTP_TIMEOUT = 30.0


async def test_1_invalid_address():
    """Test 1: Invalid address lookup returns clear null state without fake coordinates."""
    logger.info("--- TEST 1: Invalid Address Geocoding ---")
    async with httpx.AsyncClient(timeout=TEST_HTTP_TIMEOUT) as client:
        resp = await client.post(
            f"{API_BASE_URL}/api/score",
            json={"address": "xyz123invalidaddressnonexistentlocality999", "property_type": "Apartment"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        logger.info("Response for invalid address: location=%s", data.get("location"))
        assert data.get("location") is None or data["location"].get("risk_score") is None
        logger.info("Test 1 PASSED: Invalid address returned clear null location state.")


async def test_2_unavailable_price_source():
    """Test 2: Locality with missing price benchmark returns null price state without fake numbers."""
    logger.info("--- TEST 2: Unavailable Price Source ---")
    async with httpx.AsyncClient(timeout=TEST_HTTP_TIMEOUT) as client:
        resp = await client.post(
            f"{API_BASE_URL}/api/score",
            json={"address": "Kodaikanal Remote Hilltop", "property_type": "Apartment"}
        )
        assert resp.status_code == 200
        data = resp.json()
        logger.info("Price result for remote location: %s", data.get("price"))
        assert data.get("price") is None or data["price"].get("fairness_score") is None
        logger.info("Test 2 PASSED: Missing price benchmark returned explicit null state.")


async def test_3_invalid_image_url():
    """Test 3: Invalid/404 image URL returns null CV result without fake predictions."""
    logger.info("--- TEST 3: Invalid Image URL (404) ---")
    async with httpx.AsyncClient(timeout=TEST_HTTP_TIMEOUT) as client:
        resp = await client.post(
            f"{API_BASE_URL}/api/score",
            json={
                "address": "Dwarka Sector 12, New Delhi",
                "property_type": "Apartment",
                "image_info": {
                    "image_url": "https://invalid-nonexistent-domain-999.org/fake.jpg",
                    "image_type": "RGB"
                }
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        logger.info("CV result for invalid image URL: %s", data.get("cv"))
        assert data.get("cv") is None or data["cv"].get("structural_score") is None
        logger.info("Test 3 PASSED: Invalid image URL handled safely with explicit null CV state.")


def test_4_blurry_image_detection():
    """Test 4: Low-sharpness image triggers blurriness detection threshold (Laplacian variance < 50.0)."""
    logger.info("--- TEST 4: Blurry Image Quality Safeguard ---")
    # Create solid gray image (zero sharpness variance)
    blur_img = Image.fromarray(np.full((100, 100, 3), 128, dtype=np.uint8))
    var = compute_blur_variance(blur_img)
    logger.info("Computed Laplacian variance for uniform gray image: %.2f", var)
    assert var < 50.0, f"Expected variance < 50.0, got {var}"
    logger.info("Test 4 PASSED: Blurry image variance %.2f correctly triggers blur safeguard.", var)


async def test_5_missing_thermal_hardware():
    """Test 5: Unattached thermal hardware sensor returns null insulation score without fake readings."""
    logger.info("--- TEST 5: Missing Thermal Hardware Sensor ---")
    async with httpx.AsyncClient(timeout=TEST_HTTP_TIMEOUT) as client:
        resp = await client.post(
            f"{API_BASE_URL}/api/score",
            json={"address": "Dwarka Sector 12, New Delhi", "property_type": "Apartment"}
        )
        assert resp.status_code == 200
        data = resp.json()
        logger.info("Thermal result without sensor hardware: %s", data.get("thermal"))
        thermal = data.get("thermal")
        assert thermal is None or thermal.get("insulation_score") is None
        logger.info("Test 5 PASSED: Missing thermal sensor hardware returned explicit null state.")


async def test_6_provisional_scoring_formula():
    """Test 6: Non-zeroing composite scoring formula correctly reweights partial modules."""
    logger.info("--- TEST 6: Non-Zeroing Provisional Scoring Engine ---")
    # 2 active modules out of 4 (Location: 80.0, Price: 90.0)
    loc = LocationResult(risk_score=80.0)
    price = PriceBenchmarkResult(fairness_score=90.0)

    score, is_prov, count, coverage = await calculate_overall_score(
        location=loc, aqi=None, price=price, cv=None, thermal=None
    )

    # Active weight sum = 25% (loc) + 25% (price) = 50%
    # Expected weighted score = (0.25*80 + 0.25*90) / 0.50 = 85.0
    logger.info("Provisional output: overall_score=%.2f, is_provisional=%s, active_count=%d, coverage=%.1f%%",
                score, is_prov, count, coverage)
    assert score == 85.0, f"Expected 85.0, got {score}"
    assert is_prov is True, "Expected is_provisional=True"
    assert count == 2, f"Expected 2 active modules, got {count}"
    assert coverage == 50.0, f"Expected 50.0% coverage, got {coverage}"
    logger.info("Test 6 PASSED: Provisional score correctly re-weighted to 85.0 with 50%% coverage.")


async def test_7_dual_property_comparison_edge_cases():
    """Test 7: Dual property compare handles partial module data cleanly."""
    logger.info("--- TEST 7: Dual Property Comparison Edge Cases ---")
    async with httpx.AsyncClient(timeout=TEST_HTTP_TIMEOUT) as client:
        resp = await client.post(
            f"{API_BASE_URL}/api/score/compare",
            json={
                "property_a": {"address": "Dwarka Sector 12, New Delhi", "property_type": "Apartment"},
                "property_b": {"address": "xyz123invalidaddressnonexistentlocality999", "property_type": "Villa"}
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        logger.info("Compare winner: %s, delta: %s", data.get("overall_winner"), data.get("overall_delta"))
        assert "Property A" in data.get("overall_winner", "")
        assert len(data.get("module_differences", [])) == 5
        logger.info("Test 7 PASSED: Compare mode cleanly handled property with invalid address.")


async def test_8_aqi_geographic_relevance_safeguard():
    """Test 8: AQI module rejects unrelated fallback stations (e.g. Shanghai for Delhi) and returns None."""
    logger.info("--- TEST 8: AQI Geographic Relevance Safeguard ---")
    # 1. Haversine distance from Delhi (28.59, 77.04) to Shanghai (31.20, 121.45)
    delhi_lat, delhi_lon = 28.5975, 77.0424
    shanghai_lat, shanghai_lon = 31.2047, 121.4489
    dist_km = haversine_distance_km(delhi_lat, delhi_lon, shanghai_lat, shanghai_lon)
    logger.info("Calculated distance from Delhi to Shanghai: %.1f km (Max allowed: %.1f km)", dist_km, MAX_AQI_STATION_DISTANCE_KM)
    assert dist_km > 4000.0, f"Expected distance > 4000 km, got {dist_km}"
    assert dist_km > MAX_AQI_STATION_DISTANCE_KM

    # 2. fetch_real_aqi with unconfigured/demo token returns None (never falls back to Shanghai)
    aqi_res = await fetch_real_aqi(latitude=delhi_lat, longitude=delhi_lon)
    logger.info("fetch_real_aqi result without valid AQICN token: %s", aqi_res)
    assert aqi_res is None, "Expected AQI result to be None when no valid nearby station is available"

    logger.info("Test 8 PASSED: AQI module strictly enforces geographic relevance and rejects unrelated fallback stations.")


async def run_all_tests():
    logger.info("=== RUNNING LIVE DEMO EDGE CASE VERIFICATION SUITE ===")
    await test_1_invalid_address()
    await test_2_unavailable_price_source()
    await test_3_invalid_image_url()
    test_4_blurry_image_detection()
    await test_5_missing_thermal_hardware()
    await test_6_provisional_scoring_formula()
    await test_7_dual_property_comparison_edge_cases()
    await test_8_aqi_geographic_relevance_safeguard()
    logger.info("=== ALL 8 LIVE DEMO EDGE CASE TESTS PASSED SUCCESSFULLY ===")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
