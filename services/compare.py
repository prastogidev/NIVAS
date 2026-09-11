import logging
from typing import List, Tuple, Optional, Any

from backend.models.score import (
    ScoreRequest,
    ScoreResponse,
    CompareResponse,
    ModuleDifference,
)

logger = logging.getLogger("nivas.services.compare")


# ── Shared module comparison helper ──────────────────────────────────────────

def _resolve_advantage(score_a: Optional[float], score_b: Optional[float]) -> tuple[str, Optional[float]]:
    """Return (advantage_label, abs_delta) for two nullable module scores."""
    if score_a is not None and score_b is not None:
        delta = round(abs(score_a - score_b), 1)
        if score_a > score_b:
            return "Property A", delta
        elif score_b > score_a:
            return "Property B", delta
        return "Tie", delta
    elif score_a is not None:
        return "Property A", None
    elif score_b is not None:
        return "Property B", None
    return "Incomparable", None


def _compare_module(
    *,
    module_key: str,
    module_label: str,
    weight_pct: str,
    score_a: Optional[float],
    score_b: Optional[float],
    reason_both: str,
    reason_only_a: str,
    reason_only_b: str,
    reason_neither: str,
) -> ModuleDifference:
    """
    Generic module-level comparison builder.
    Accepts pre-formatted reason strings for each branch to keep per-module
    functions focused purely on metric extraction.
    """
    adv, delta = _resolve_advantage(score_a, score_b)

    if score_a is not None and score_b is not None:
        reason = reason_both
    elif score_a is not None:
        reason = reason_only_a
    elif score_b is not None:
        reason = reason_only_b
    else:
        reason = reason_neither

    return ModuleDifference(
        module_key=module_key,
        module_label=module_label,
        weight_pct=weight_pct,
        score_a=score_a,
        score_b=score_b,
        score_delta=delta,
        advantage=adv,
        reason=reason,
    )


# ── Per-module comparison functions ──────────────────────────────────────────

def _compare_location(loc_a, loc_b, label_a: str, label_b: str) -> ModuleDifference:
    score_a = loc_a.risk_score if loc_a else None
    score_b = loc_b.risk_score if loc_b else None

    infra_a = loc_a.infrastructure if loc_a else None
    infra_b = loc_b.infrastructure if loc_b else None
    hosp_a  = infra_a.hospitals_count          if infra_a else 0
    hosp_b  = infra_b.hospitals_count          if infra_b else 0
    rail_a  = infra_a.railway_stations_count   if infra_a else 0
    rail_b  = infra_b.railway_stations_count   if infra_b else 0

    adv, delta = _resolve_advantage(score_a, score_b)

    return _compare_module(
        module_key="location",
        module_label="Location & Infrastructure Risk",
        weight_pct="25%",
        score_a=score_a,
        score_b=score_b,
        reason_both=(
            f"Location score: Property A ({score_a}/100) vs Property B ({score_b}/100), Delta: {delta} pts. "
            f"Advantage {adv}. Property A: {hosp_a} hospital(s), {rail_a} transit station(s) vs "
            f"Property B: {hosp_b} hospital(s), {rail_b} transit station(s)."
        ),
        reason_only_a=f"Property A location active ({score_a}/100) for locality '{loc_a.locality if loc_a else 'A'}'. Property B unavailable.",
        reason_only_b=f"Property B location active ({score_b}/100) for locality '{loc_b.locality if loc_b else 'B'}'. Property A unavailable.",
        reason_neither="Location risk modules disconnected (null) for both properties.",
    )


def _compare_price(price_a, price_b, label_a: str, label_b: str) -> ModuleDifference:
    score_a = price_a.fairness_score if price_a else None
    score_b = price_b.fairness_score if price_b else None

    rate_a = f"₹{price_a.estimated_price_per_sqft:,.0f}/sq.ft." if price_a and price_a.estimated_price_per_sqft else "N/A"
    rate_b = f"₹{price_b.estimated_price_per_sqft:,.0f}/sq.ft." if price_b and price_b.estimated_price_per_sqft else "N/A"
    adv, delta = _resolve_advantage(score_a, score_b)

    return _compare_module(
        module_key="price",
        module_label="Price Valuation Benchmark",
        weight_pct="25%",
        score_a=score_a,
        score_b=score_b,
        reason_both=(
            f"Price fairness: Property A ({score_a}/100 at {rate_a}) vs Property B ({score_b}/100 at {rate_b}), "
            f"Delta: {delta} pts. Advantage {adv} based on regional benchmark alignment."
        ),
        reason_only_a=f"Property A price benchmark active ({score_a}/100). Property B price benchmark unavailable.",
        reason_only_b=f"Property B price benchmark active ({score_b}/100). Property A price benchmark unavailable.",
        reason_neither="Price benchmark modules disconnected (null) for both properties.",
    )


def _compare_cv(cv_a, cv_b, label_a: str, label_b: str) -> ModuleDifference:
    score_a = cv_a.structural_score if cv_a else None
    score_b = cv_b.structural_score if cv_b else None

    class_a = (cv_a.predicted_class or "clean") if cv_a else ""
    class_b = (cv_b.predicted_class or "clean") if cv_b else ""
    conf_a  = f"{cv_a.confidence * 100:.1f}%" if cv_a and cv_a.confidence else "N/A"
    conf_b  = f"{cv_b.confidence * 100:.1f}%" if cv_b and cv_b.confidence else "N/A"
    adv, delta = _resolve_advantage(score_a, score_b)

    return _compare_module(
        module_key="cv",
        module_label="Computer Vision Wall Defect",
        weight_pct="30%",
        score_a=score_a,
        score_b=score_b,
        reason_both=(
            f"CV structural score: Property A ({score_a}/100, '{class_a}' at {conf_a}) vs "
            f"Property B ({score_b}/100, '{class_b}' at {conf_b}), Delta: {delta} pts. Advantage {adv}."
        ),
        reason_only_a=f"Property A wall image evaluated as '{class_a}' ({score_a}/100). Property B image disconnected (null).",
        reason_only_b=f"Property B wall image evaluated as '{class_b}' ({score_b}/100). Property A image disconnected (null).",
        reason_neither="Computer vision defect scan disconnected (null) for both properties (no images provided).",
    )


def _compare_thermal(thermal_a, thermal_b, label_a: str, label_b: str) -> ModuleDifference:
    score_a = thermal_a.insulation_score if thermal_a else None
    score_b = thermal_b.insulation_score if thermal_b else None

    anom_a = (thermal_a.anomalies_detected_count or 0) if thermal_a else 0
    anom_b = (thermal_b.anomalies_detected_count or 0) if thermal_b else 0
    adv, delta = _resolve_advantage(score_a, score_b)

    return _compare_module(
        module_key="thermal",
        module_label="Thermal Insulation & Sensor",
        weight_pct="20%",
        score_a=score_a,
        score_b=score_b,
        reason_both=(
            f"Thermal score: Property A ({score_a}/100, {anom_a} anomaly spots) vs "
            f"Property B ({score_b}/100, {anom_b} anomaly spots), Delta: {delta} pts. Advantage {adv}."
        ),
        reason_only_a=f"Property A thermal scan active ({score_a}/100). Property B thermal hardware disconnected (null).",
        reason_only_b=f"Property B thermal scan active ({score_b}/100). Property A thermal hardware disconnected (null).",
        reason_neither="Thermal insulation modules disconnected (null) for both properties.",
    )


def _compare_aqi(aqi_a, aqi_b, label_a: str, label_b: str) -> ModuleDifference:
    score_a = aqi_a.environmental_score if aqi_a else None
    score_b = aqi_b.environmental_score if aqi_b else None

    val_a = aqi_a.aqi_value if aqi_a else "N/A"
    val_b = aqi_b.aqi_value if aqi_b else "N/A"
    cat_a = (aqi_a.category or "") if aqi_a else ""
    cat_b = (aqi_b.category or "") if aqi_b else ""
    adv, delta = _resolve_advantage(score_a, score_b)

    return _compare_module(
        module_key="aqi",
        module_label="Air Quality (AQI) Indicator",
        weight_pct="Supplemental",
        score_a=score_a,
        score_b=score_b,
        reason_both=(
            f"Air quality: Property A ({score_a}/100, AQI {val_a} {cat_a}) vs "
            f"Property B ({score_b}/100, AQI {val_b} {cat_b}), Delta: {delta} pts. Advantage {adv}."
        ),
        reason_only_a=f"Property A AQI active ({score_a}/100, AQI {val_a}). Property B AQI station unavailable.",
        reason_only_b=f"Property B AQI active ({score_b}/100, AQI {val_b}). Property A AQI station unavailable.",
        reason_neither="AQI air quality modules disconnected (null) for both properties.",
    )


# ── Narrative builder ─────────────────────────────────────────────────────────

def _build_comparison_narrative(
    score_a: Optional[float],
    score_b: Optional[float],
    overall_delta: Optional[float],
    overall_winner: str,
    resp_a: ScoreResponse,
    resp_b: ScoreResponse,
    req_a: ScoreRequest,
    req_b: ScoreRequest,
    module_diffs: List[ModuleDifference],
) -> Tuple[str, List[str]]:
    if score_a is not None and score_b is not None:
        if score_a > score_b:
            winner_addr, loser_addr = req_a.address, req_b.address
            winner_score, loser_score = score_a, score_b
            winner_prov = 'PROVISIONAL' if resp_a.is_provisional else 'FINAL'
            loser_prov  = 'PROVISIONAL' if resp_b.is_provisional else 'FINAL'
            winner_cov, loser_cov = resp_a.score_weight_coverage, resp_b.score_weight_coverage
        elif score_b > score_a:
            winner_addr, loser_addr = req_b.address, req_a.address
            winner_score, loser_score = score_b, score_a
            winner_prov = 'PROVISIONAL' if resp_b.is_provisional else 'FINAL'
            loser_prov  = 'PROVISIONAL' if resp_a.is_provisional else 'FINAL'
            winner_cov, loser_cov = resp_b.score_weight_coverage, resp_a.score_weight_coverage
        else:
            summary = (
                f"Comparative Assessment: Both '{req_a.address}' and '{req_b.address}' "
                f"achieved equal composite scores of {score_a:.1f}/100."
            )
            return summary, [d.reason for d in module_diffs]

        summary = (
            f"Comparative Assessment: '{winner_addr}' outperforms '{loser_addr}' "
            f"with a composite score of {winner_score:.1f}/100 vs {loser_score:.1f}/100 "
            f"(margin +{overall_delta:.1f} pts). "
            f"Winner rating: {winner_prov} ({winner_cov}% coverage). "
            f"Runner-up: {loser_prov} ({loser_cov}% coverage)."
        )
    else:
        summary = (
            f"Comparative Assessment: Inspection for '{req_a.address}' and '{req_b.address}' performed. "
            f"One or both composite scores are null due to disconnected modules."
        )

    return summary, [d.reason for d in module_diffs]


# ── Public entry point ────────────────────────────────────────────────────────

def compare_inspection_results(
    resp_a: ScoreResponse,
    resp_b: ScoreResponse,
    req_a: ScoreRequest,
    req_b: ScoreRequest,
) -> CompareResponse:
    """Compare two real property inspection responses using grounded metric logic."""
    label_a = f"{req_a.address} ({req_a.property_type})"
    label_b = f"{req_b.address} ({req_b.property_type})"

    module_diffs: List[ModuleDifference] = [
        _compare_location(resp_a.location,  resp_b.location,  label_a, label_b),
        _compare_price   (resp_a.price,     resp_b.price,     label_a, label_b),
        _compare_cv      (resp_a.cv,        resp_b.cv,        label_a, label_b),
        _compare_thermal (resp_a.thermal,   resp_b.thermal,   label_a, label_b),
        _compare_aqi     (resp_a.aqi,       resp_b.aqi,       label_a, label_b),
    ]

    score_a = resp_a.overall_score
    score_b = resp_b.overall_score

    if score_a is not None and score_b is not None:
        overall_delta = round(abs(score_a - score_b), 1)
        if score_a > score_b:
            overall_winner = f"Property A: {req_a.address}"
        elif score_b > score_a:
            overall_winner = f"Property B: {req_b.address}"
        else:
            overall_winner = "Tie / Equivalent"
    elif score_a is not None:
        overall_delta = None
        overall_winner = f"Property A: {req_a.address} (only Property A has an active composite rating)"
    elif score_b is not None:
        overall_delta = None
        overall_winner = f"Property B: {req_b.address} (only Property B has an active composite rating)"
    else:
        overall_delta = None
        overall_winner = "Incomparable (both properties disconnected)"

    summary, takeaways = _build_comparison_narrative(
        score_a, score_b, overall_delta, overall_winner,
        resp_a, resp_b, req_a, req_b, module_diffs,
    )

    return CompareResponse(
        property_a=resp_a,
        property_b=resp_b,
        label_a=label_a,
        label_b=label_b,
        overall_score_a=score_a,
        overall_score_b=score_b,
        overall_delta=overall_delta,
        overall_winner=overall_winner,
        module_differences=module_diffs,
        comparison_summary=summary,
        key_takeaways=takeaways,
    )
