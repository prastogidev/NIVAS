import asyncio
import sys
import os

from backend.models.score import (
    LocationResult,
    AQIResult,
    PriceBenchmarkResult,
    CVModelResult,
    ThermalModuleResult,
    InfrastructureSummary
)
from backend.services.scoring import calculate_overall_score, MODULE_WEIGHTS

async def main():
    print("Testing calculate_overall_score logic...")
    print(f"Base Weights: {MODULE_WEIGHTS}")
    print("-" * 50)

    # Test 1: All modules available
    print("\nTest 1: All modules available")
    location = LocationResult(risk_score=85.0)
    aqi = AQIResult(environmental_score=75.0) # Note: AQI is not in MODULE_WEIGHTS in scoring.py
    price = PriceBenchmarkResult(fairness_score=90.0)
    cv = CVModelResult(structural_score=70.0)
    thermal = ThermalModuleResult(insulation_score=80.0)

    score, is_prov, count, cov = await calculate_overall_score(location, aqi, price, cv, thermal)
    print(f"Score: {score}, Provisional: {is_prov}, Count: {count}, Coverage: {cov}%")
    expected = (85*0.25 + 90*0.25 + 70*0.30 + 80*0.20) / (0.25+0.25+0.30+0.20)
    print(f"Expected Score: {expected}")

    # Test 2: Missing Thermal
    print("\nTest 2: Missing Thermal")
    thermal_none = ThermalModuleResult(insulation_score=None)
    score, is_prov, count, cov = await calculate_overall_score(location, aqi, price, cv, None)
    print(f"Without instance -> Score: {score}, Provisional: {is_prov}, Count: {count}, Coverage: {cov}%")
    score2, is_prov2, count2, cov2 = await calculate_overall_score(location, aqi, price, cv, thermal_none)
    print(f"With None score -> Score: {score2}, Provisional: {is_prov2}, Count: {count2}, Coverage: {cov2}%")
    expected_prov = (85*0.25 + 90*0.25 + 70*0.30) / (0.25+0.25+0.30)
    print(f"Expected Provisional Score: {expected_prov}")

    # Test 3: Total failure (all missing)
    print("\nTest 3: All missing")
    score, is_prov, count, cov = await calculate_overall_score(None, None, None, None, None)
    print(f"Score: {score}, Provisional: {is_prov}, Count: {count}, Coverage: {cov}%")

if __name__ == "__main__":
    asyncio.run(main())