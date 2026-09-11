#!/usr/bin/env python3
"""Comprehensive test suite for scoring.py module"""
import asyncio
from backend.models.score import (
    LocationResult, AQIResult, PriceBenchmarkResult,
    CVModelResult, ThermalModuleResult
)
from backend.services.scoring import calculate_overall_score, MODULE_WEIGHTS

async def test_all_modules_active():
    """Test with all 4 weighted modules providing scores"""
    print("\n✓ Test 1: All 4 modules active")
    result = await calculate_overall_score(
        location=LocationResult(risk_score=85.0),
        aqi=AQIResult(environmental_score=95.0),  # AQI passed but not weighted
        price=PriceBenchmarkResult(fairness_score=90.0),
        cv=CVModelResult(structural_score=70.0),
        thermal=ThermalModuleResult(insulation_score=80.0)
    )
    score, is_prov, count, cov = result
    expected = (85*0.25 + 90*0.25 + 70*0.30 + 80*0.20)
    assert score == round(expected, 2), f"Expected {expected}, got {score}"
    assert is_prov == False, "Should not be provisional"
    assert count == 4, f"Expected 4 active modules, got {count}"
    assert cov == 100.0, f"Expected 100% coverage, got {cov}"
    print(f"  Score: {score}, Provisional: {is_prov}, Count: {count}, Coverage: {cov}%")

async def test_missing_one_module():
    """Test with one module missing (thermal)"""
    print("\n✓ Test 2: Missing thermal module")
    result = await calculate_overall_score(
        location=LocationResult(risk_score=85.0),
        aqi=AQIResult(environmental_score=95.0),
        price=PriceBenchmarkResult(fairness_score=90.0),
        cv=CVModelResult(structural_score=70.0),
        thermal=None
    )
    score, is_prov, count, cov = result
    expected = (85*0.25 + 90*0.25 + 70*0.30) / (0.25 + 0.25 + 0.30)
    assert score == round(expected, 2), f"Expected {round(expected, 2)}, got {score}"
    assert is_prov == True, "Should be provisional"
    assert count == 3, f"Expected 3 active modules, got {count}"
    assert cov == 80.0, f"Expected 80% coverage, got {cov}"
    print(f"  Score: {score}, Provisional: {is_prov}, Count: {count}, Coverage: {cov}%")

async def test_only_location():
    """Test with only location module"""
    print("\n✓ Test 3: Only location module active")
    result = await calculate_overall_score(
        location=LocationResult(risk_score=85.0),
        aqi=None,
        price=None,
        cv=None,
        thermal=None
    )
    score, is_prov, count, cov = result
    assert score == 85.0, f"Expected 85.0, got {score}"
    assert is_prov == True, "Should be provisional"
    assert count == 1, f"Expected 1 active module, got {count}"
    assert cov == 25.0, f"Expected 25% coverage, got {cov}"
    print(f"  Score: {score}, Provisional: {is_prov}, Count: {count}, Coverage: {cov}%")

async def test_all_missing():
    """Test with all modules missing"""
    print("\n✓ Test 4: All modules missing")
    result = await calculate_overall_score(None, None, None, None, None)
    score, is_prov, count, cov = result
    assert score is None, f"Expected None, got {score}"
    assert is_prov is None, f"Expected None, got {is_prov}"
    assert count == 0, f"Expected 0, got {count}"
    assert cov == 0.0, f"Expected 0.0, got {cov}"
    print(f"  Score: {score}, Provisional: {is_prov}, Count: {count}, Coverage: {cov}%")

async def test_aqi_not_weighted():
    """Verify AQI doesn't affect scoring"""
    print("\n✓ Test 5: AQI is informational only (not weighted)")
    result_with_aqi = await calculate_overall_score(
        location=LocationResult(risk_score=85.0),
        aqi=AQIResult(environmental_score=100.0),
        price=PriceBenchmarkResult(fairness_score=90.0),
        cv=CVModelResult(structural_score=70.0),
        thermal=ThermalModuleResult(insulation_score=80.0)
    )
    result_without_aqi = await calculate_overall_score(
        location=LocationResult(risk_score=85.0),
        aqi=None,
        price=PriceBenchmarkResult(fairness_score=90.0),
        cv=CVModelResult(structural_score=70.0),
        thermal=ThermalModuleResult(insulation_score=80.0)
    )
    assert result_with_aqi[0] == result_without_aqi[0], "AQI should not affect score"
    print(f"  With AQI: {result_with_aqi[0]}, Without AQI: {result_without_aqi[0]} ✓ Equal")

async def test_none_vs_null_score():
    """Test None instance vs instance with None score"""
    print("\n✓ Test 6: None instance vs instance with null score field")
    result_none = await calculate_overall_score(
        location=LocationResult(risk_score=85.0),
        aqi=None,
        price=None,
        cv=None,
        thermal=None
    )
    result_null_score = await calculate_overall_score(
        location=LocationResult(risk_score=85.0),
        aqi=AQIResult(environmental_score=None),
        price=PriceBenchmarkResult(fairness_score=None),
        cv=CVModelResult(structural_score=None),
        thermal=ThermalModuleResult(insulation_score=None)
    )
    assert result_none == result_null_score, "None instance should equal null score"
    print(f"  Both produce: {result_none}")

async def main():
    print("=" * 60)
    print("SCORING.PY COMPREHENSIVE TEST SUITE")
    print("=" * 60)
    print(f"\nModule Weights: {MODULE_WEIGHTS}")
    print(f"Total Weight: {sum(MODULE_WEIGHTS.values())}")

    try:
        await test_all_modules_active()
        await test_missing_one_module()
        await test_only_location()
        await test_all_missing()
        await test_aqi_not_weighted()
        await test_none_vs_null_score()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
