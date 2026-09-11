from typing import Dict, Optional, Tuple

from backend.models.score import (
    AQIResult,
    CVModelResult,
    LocationResult,
    PriceBenchmarkResult,
    ThermalModuleResult,
)


# Configured composite-score weights. AQI is a supplemental indicator and is
# intentionally excluded from this weighted composite.
MODULE_WEIGHTS: Dict[str, float] = {
    "location": 0.25,
    "price": 0.25,
    "cv": 0.30,
    "thermal": 0.20,
}


async def calculate_overall_score(
    location: Optional[LocationResult],
    aqi: Optional[AQIResult],
    price: Optional[PriceBenchmarkResult],
    cv: Optional[CVModelResult],
    thermal: Optional[ThermalModuleResult],
) -> Tuple[Optional[float], Optional[bool], int, float]:
    """Return the re-normalized composite score and its input coverage.

    Unavailable modules are excluded rather than treated as zero. The return
    value is ``(score, is_provisional, active_module_count, weight_coverage)``.
    ``aqi`` remains accepted for API compatibility but is not a weighted module.
    """
    del aqi  # Supplemental only; deliberately not part of the score formula.

    available_scores: Dict[str, float] = {}
    if location and location.risk_score is not None:
        available_scores["location"] = float(location.risk_score)
    if price and price.fairness_score is not None:
        available_scores["price"] = float(price.fairness_score)
    if cv and cv.structural_score is not None:
        available_scores["cv"] = float(cv.structural_score)
    if thermal and thermal.insulation_score is not None:
        available_scores["thermal"] = float(thermal.insulation_score)

    if not available_scores:
        return None, None, 0, 0.0

    active_weight = sum(MODULE_WEIGHTS[module] for module in available_scores)
    weighted_total = sum(
        available_scores[module] * MODULE_WEIGHTS[module]
        for module in available_scores
    )
    score = round(weighted_total / active_weight, 2)
    coverage = round(active_weight / sum(MODULE_WEIGHTS.values()) * 100.0, 1)

    return score, coverage < 100.0, len(available_scores), coverage
