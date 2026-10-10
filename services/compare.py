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

def _resolve_advantage(score_a: Optional[float], score_b: Optional[float]) -> Tuple[str, Optional[float], str]:
    """Return (advantage_label, abs_delta, coverage_status)."""
    if score_a is not None and score_b is not None:
        delta = round(abs(score_a - score_b), 1)
        if score_a > score_b:
            return "Property A", delta, "both_active"
        elif score_b > score_a:
            return "Property B", delta, "both_active"
        return "Tie", delta, "both_active"
    elif score_a is not None:
        return "Property A", None, "only_a_active"
    elif score_b is not None:
        return "Property B", None, "only_b_active"
    return "Incomparable", None, "both_null"


# ── Per-module comparison functions ──────────────────────────────────────────

def _compare_location(loc_a, loc_b, label_a: str, label_b: str) -> ModuleDifference:
    score_a = loc_a.risk_score if loc_a else None
    score_b = loc_b.risk_score if loc_b else None
    adv, delta, cov_status = _resolve_advantage(score_a, score_b)

    status_a = getattr(loc_a, "fetch_status", "active") if loc_a else "unassessed"
    status_b = getattr(loc_b, "fetch_status", "active") if loc_b else "unassessed"
    failed_a = status_a in ("fetch_failed", "timeout", "invalid_address")
    failed_b = status_b in ("fetch_failed", "timeout", "invalid_address")
    err_a = getattr(loc_a, "error_message", None) if loc_a else None
    err_b = getattr(loc_b, "error_message", None) if loc_b else None

    infra_a = loc_a.infrastructure if loc_a else None
    infra_b = loc_b.infrastructure if loc_b else None
    hosp_a = infra_a.hospitals_count if infra_a else 0
    hosp_b = infra_b.hospitals_count if infra_b else 0
    school_a = infra_a.schools_count if infra_a else 0
    school_b = infra_b.schools_count if infra_b else 0
    rail_a = infra_a.railway_stations_count if infra_a else 0
    rail_b = infra_b.railway_stations_count if infra_b else 0
    roads_a = infra_a.major_roads_count if infra_a else 0
    roads_b = infra_b.major_roads_count if infra_b else 0

    if loc_a and loc_a.latitude and not failed_a:
        prov_a = f"OpenStreetMap Overpass API ({loc_a.latitude:.4f}, {loc_a.longitude:.4f})"
    elif failed_a:
        prov_a = f"OpenStreetMap Overpass API (Fetch Failed: {loc_a.locality or 'Unknown'})"
    else:
        prov_a = "Not assessed"

    if loc_b and loc_b.latitude and not failed_b:
        prov_b = f"OpenStreetMap Overpass API ({loc_b.latitude:.4f}, {loc_b.longitude:.4f})"
    elif failed_b:
        prov_b = f"OpenStreetMap Overpass API (Fetch Failed: {loc_b.locality or 'Unknown'})"
    else:
        prov_b = "Not assessed"

    if score_a is not None and score_b is not None:
        reason = (
            f"Location score: Property A ({score_a:.0f}/100) vs Property B ({score_b:.0f}/100), Delta: {delta} pts. "
            f"Advantage {adv}. Property A amenities: {hosp_a} hospital(s), {school_a} school(s), {rail_a} transit station(s), {roads_a} road(s) vs "
            f"Property B amenities: {hosp_b} hospital(s), {school_b} school(s), {rail_b} transit station(s), {roads_b} road(s)."
        )
        if score_a > score_b:
            explanation = (
                f"Property A exhibits stronger civic connectivity (+{delta} pts) due to higher density of emergency healthcare "
                f"({hosp_a} vs {hosp_b}), education ({school_a} vs {school_b}), and transit access ({rail_a} vs {rail_b} stations) within 1.2km."
            )
        elif score_b > score_a:
            explanation = (
                f"Property B exhibits stronger civic connectivity (+{delta} pts) due to higher density of emergency healthcare "
                f"({hosp_b} vs {hosp_a}), education ({school_b} vs {school_a}), and transit access ({rail_b} vs {rail_a} stations) within 1.2km."
            )
        else:
            explanation = "Both properties provide equivalent local infrastructure access within their respective 1.2km evaluation zones."
    elif score_a is not None:
        if failed_b:
            reason = f"Property A location active ({score_a:.0f}/100). Property B live infrastructure fetch failed ({err_b or 'API timeout'})."
            explanation = f"Property A has verified OpenStreetMap infrastructure data ({hosp_a} hospitals, {rail_a} transit stations). Property B's coordinates were resolved, but live civic amenities could not be retrieved from Overpass mirrors."
        else:
            reason = f"Property A location active ({score_a:.0f}/100) for '{loc_a.locality if loc_a else 'A'}'. Property B location data unavailable."
            explanation = f"Property A has verified OpenStreetMap infrastructure data ({hosp_a} hospitals, {rail_a} stations), whereas Property B's location infrastructure is unassessed."
    elif score_b is not None:
        if failed_a:
            reason = f"Property B location active ({score_b:.0f}/100). Property A live infrastructure fetch failed ({err_a or 'API timeout'})."
            explanation = f"Property B has verified OpenStreetMap infrastructure data ({hosp_b} hospitals, {rail_b} transit stations). Property A's coordinates were resolved, but live civic amenities could not be retrieved from Overpass mirrors."
        else:
            reason = f"Property B location active ({score_b:.0f}/100) for '{loc_b.locality if loc_b else 'B'}'. Property A location data unavailable."
            explanation = f"Property B has verified OpenStreetMap infrastructure data ({hosp_b} hospitals, {rail_b} stations), whereas Property A's location infrastructure is unassessed."
    else:
        if failed_a or failed_b:
            reason = f"Location infrastructure fetch failed due to API mirror timeouts (Property A: {status_a}, Property B: {status_b})."
            explanation = "Live civic amenities could not be retrieved from OpenStreetMap mirrors for one or both properties."
        else:
            reason = "Location infrastructure data unavailable (null) for both properties."
            explanation = "Neither property could be evaluated for civic infrastructure due to unfulfilled geocoding/Overpass queries."

    return ModuleDifference(
        module_key="location",
        module_label="Location & Infrastructure Risk",
        weight_pct="25%",
        score_a=score_a,
        score_b=score_b,
        score_delta=delta,
        advantage=adv,
        reason=reason,
        explanation=explanation,
        provenance_a=prov_a,
        provenance_b=prov_b,
        coverage_status=cov_status,
        fetch_failed_a=failed_a,
        fetch_failed_b=failed_b,
        status_a=status_a,
        status_b=status_b,
        error_message_a=err_a,
        error_message_b=err_b,
    )


def _compare_price(
    price_a,
    price_b,
    label_a: str,
    label_b: str,
    status_a: Optional[str] = None,
    status_b: Optional[str] = None,
    err_a: Optional[str] = None,
    err_b: Optional[str] = None,
) -> ModuleDifference:
    score_a = price_a.fairness_score if price_a else None
    score_b = price_b.fairness_score if price_b else None
    adv, delta, cov_status = _resolve_advantage(score_a, score_b)

    val_a = price_a.estimated_price_per_sqft if price_a else None
    val_b = price_b.estimated_price_per_sqft if price_b else None
    rate_a_str = f"₹{val_a:,.0f}/sq.ft." if val_a else "N/A"
    rate_b_str = f"₹{val_b:,.0f}/sq.ft." if val_b else "N/A"
    samples_a = price_a.sample_count if price_a else 0
    samples_b = price_b.sample_count if price_b else 0

    st_a = status_a or ("active" if score_a is not None else "not_assessed")
    st_b = status_b or ("active" if score_b is not None else "not_assessed")

    failed_a = (st_a == "fetch_failed")
    failed_b = (st_b == "fetch_failed")

    def _provenance_for_price(score, price_obj, samples, status):
        if score is not None and price_obj and price_obj.source:
            return f"{price_obj.source} ({samples} samples)"
        if status == "provider_not_configured":
            return "Provider not configured"
        if status == "fetch_failed":
            return "Fetch Failed (API Error / Timeout)"
        if status == "data_unavailable":
            return "Data unavailable (No benchmark for locality)"
        return "Not assessed"

    prov_a = _provenance_for_price(score_a, price_a, samples_a, st_a)
    prov_b = _provenance_for_price(score_b, price_b, samples_b, st_b)

    if score_a is not None and score_b is not None:
        reason = (
            f"Price fairness: Property A ({score_a:.0f}/100 at {rate_a_str}) vs Property B ({score_b:.0f}/100 at {rate_b_str}), "
            f"Delta: {delta} pts. Advantage {adv} based on regional valuation benchmark alignment."
        )
        if score_a > score_b:
            explanation = (
                f"Property A offers better price alignment (+{delta} pts fairness at {rate_a_str}) compared to Property B "
                f"({rate_b_str}), which trades at a higher premium relative to its locality reference baseline."
            )
        elif score_b > score_a:
            explanation = (
                f"Property B offers better price alignment (+{delta} pts fairness at {rate_b_str}) compared to Property A "
                f"({rate_a_str}), which trades at a higher premium relative to its locality reference baseline."
            )
        else:
            explanation = f"Both properties demonstrate identical valuation fairness relative to their locality benchmarks ({rate_a_str} vs {rate_b_str})."
    elif score_a is not None:
        if st_b == "provider_not_configured":
            reason = f"Property A price benchmark active ({score_a:.0f}/100 at {rate_a_str}). Property B price provider not configured."
            explanation = f"Property A has verified pricing data ({rate_a_str} from {prov_a}), whereas Property B could not be evaluated because no price API or local benchmark dataset is configured."
        elif st_b == "fetch_failed":
            reason = f"Property A price benchmark active ({score_a:.0f}/100 at {rate_a_str}). Property B price fetch failed."
            explanation = f"Property A has verified pricing data ({rate_a_str} from {prov_a}), whereas Property B price benchmark fetch failed ({err_b or 'API error'})."
        elif st_b == "data_unavailable":
            reason = f"Property A price benchmark active ({score_a:.0f}/100 at {rate_a_str}). Property B price data unavailable."
            explanation = f"Property A has verified pricing data ({rate_a_str} from {prov_a}), whereas Property B has no benchmark data available for its locality."
        else:
            reason = f"Property A price benchmark active ({score_a:.0f}/100 at {rate_a_str}). Property B price not assessed."
            explanation = f"Property A has verified pricing data ({rate_a_str} from {prov_a}), whereas Property B price was not assessed."
    elif score_b is not None:
        if st_a == "provider_not_configured":
            reason = f"Property B price benchmark active ({score_b:.0f}/100 at {rate_b_str}). Property A price provider not configured."
            explanation = f"Property B has verified pricing data ({rate_b_str} from {prov_b}), whereas Property A could not be evaluated because no price API or local benchmark dataset is configured."
        elif st_a == "fetch_failed":
            reason = f"Property B price benchmark active ({score_b:.0f}/100 at {rate_b_str}). Property A price fetch failed."
            explanation = f"Property B has verified pricing data ({rate_b_str} from {prov_b}), whereas Property A price benchmark fetch failed ({err_a or 'API error'})."
        elif st_a == "data_unavailable":
            reason = f"Property B price benchmark active ({score_b:.0f}/100 at {rate_b_str}). Property A price data unavailable."
            explanation = f"Property B has verified pricing data ({rate_b_str} from {prov_b}), whereas Property A has no benchmark data available for its locality."
        else:
            reason = f"Property B price benchmark active ({score_b:.0f}/100 at {rate_b_str}). Property A price not assessed."
            explanation = f"Property B has verified pricing data ({rate_b_str} from {prov_b}), whereas Property A price was not assessed."
    else:
        # Both null
        if st_a == "provider_not_configured" and st_b == "provider_not_configured":
            reason = "Price provider not configured (no Propstack API key and no local benchmark dataset)."
            explanation = "Neither property could evaluate price fairness because no pricing API or local benchmark dataset is configured."
        elif failed_a or failed_b:
            reason = "Price benchmark fetch failed due to API connection error or timeout."
            explanation = f"Price benchmark data could not be retrieved for one or both properties (Property A: {st_a}, Property B: {st_b})."
        elif st_a == "data_unavailable" and st_b == "data_unavailable":
            reason = "Price benchmark data unavailable for both properties (no benchmark for either locality)."
            explanation = "Neither property resolved a valid price benchmark from configured data sources."
        else:
            reason = "Price benchmark not assessed for both properties."
            explanation = "Neither property could be evaluated against local circle rates or market valuation benchmarks."

    return ModuleDifference(
        module_key="price",
        module_label="Price Valuation Benchmark",
        weight_pct="25%",
        score_a=score_a,
        score_b=score_b,
        score_delta=delta,
        advantage=adv,
        reason=reason,
        explanation=explanation,
        provenance_a=prov_a,
        provenance_b=prov_b,
        coverage_status=cov_status,
        fetch_failed_a=failed_a,
        fetch_failed_b=failed_b,
        status_a=st_a,
        status_b=st_b,
        error_message_a=err_a,
        error_message_b=err_b,
    )


def _compare_cv(cv_a, cv_b, label_a: str, label_b: str) -> ModuleDifference:
    score_a = cv_a.structural_score if cv_a else None
    score_b = cv_b.structural_score if cv_b else None
    adv, delta, cov_status = _resolve_advantage(score_a, score_b)

    class_a = cv_a.predicted_class if cv_a else "N/A"
    class_b = cv_b.predicted_class if cv_b else "N/A"
    conf_a = f"{cv_a.confidence * 100:.1f}%" if (cv_a and cv_a.confidence is not None) else "N/A"
    conf_b = f"{cv_b.confidence * 100:.1f}%" if (cv_b and cv_b.confidence is not None) else "N/A"
    cov_ratio_a = f"{(cv_a.defect_coverage_ratio * 100):.1f}%" if (cv_a and cv_a.defect_coverage_ratio is not None) else "0%"
    cov_ratio_b = f"{(cv_b.defect_coverage_ratio * 100):.1f}%" if (cv_b and cv_b.defect_coverage_ratio is not None) else "0%"

    prov_a = f"EfficientNet-B0 Visual Model ({class_a}, {conf_a} conf)" if cv_a else "Not assessed (No Image)"
    prov_b = f"EfficientNet-B0 Visual Model ({class_b}, {conf_b} conf)" if cv_b else "Not assessed (No Image)"

    status_a = "active" if score_a is not None else "unassessed"
    status_b = "active" if score_b is not None else "unassessed"

    if score_a is not None and score_b is not None:
        reason = (
            f"CV structural score: Property A ({score_a:.0f}/100, '{class_a}' at {conf_a}) vs "
            f"Property B ({score_b:.0f}/100, '{class_b}' at {conf_b}), Delta: {delta} pts. Advantage {adv}."
        )
        if score_a > score_b:
            explanation = (
                f"Property A exhibits superior wall condition (+{delta} pts). Property A was evaluated as '{class_a}' "
                f"with {conf_a} confidence, whereas Property B was flagged for '{class_b}' ({cov_ratio_b} surface defect coverage)."
            )
        elif score_b > score_a:
            explanation = (
                f"Property B exhibits superior wall condition (+{delta} pts). Property B was evaluated as '{class_b}' "
                f"with {conf_b} confidence, whereas Property A was flagged for '{class_a}' ({cov_ratio_a} surface defect coverage)."
            )
        else:
            explanation = f"Both properties exhibit equivalent visual wall surface structural integrity ({class_a} at {score_a:.0f}/100)."
    elif score_a is not None:
        reason = f"Property A wall image evaluated as '{class_a}' ({score_a:.0f}/100). Property B image not provided."
        explanation = f"Property A has verified visual wall scan data ('{class_a}'), whereas Property B has no uploaded images for automated defect screening."
    elif score_b is not None:
        reason = f"Property B wall image evaluated as '{class_b}' ({score_b:.0f}/100). Property A image not provided."
        explanation = f"Property B has verified visual wall scan data ('{class_b}'), whereas Property A has no uploaded images for automated defect screening."
    else:
        reason = "Computer vision defect scan not assessed for both properties (no images provided)."
        explanation = "Neither property provided wall facade images for computer vision defect analysis."

    return ModuleDifference(
        module_key="cv",
        module_label="Computer Vision Wall Defect",
        weight_pct="30%",
        score_a=score_a,
        score_b=score_b,
        score_delta=delta,
        advantage=adv,
        reason=reason,
        explanation=explanation,
        provenance_a=prov_a,
        provenance_b=prov_b,
        coverage_status=cov_status,
        status_a=status_a,
        status_b=status_b,
    )


def _compare_thermal(thermal_a, thermal_b, label_a: str, label_b: str) -> ModuleDifference:
    score_a = thermal_a.insulation_score if thermal_a else None
    score_b = thermal_b.insulation_score if thermal_b else None
    adv, delta, cov_status = _resolve_advantage(score_a, score_b)

    anom_a = thermal_a.anomalies_detected_count if thermal_a else 0
    anom_b = thermal_b.anomalies_detected_count if thermal_b else 0
    mean_a = f"{thermal_a.mean_temp:.1f}°C" if (thermal_a and thermal_a.mean_temp is not None) else "N/A"
    mean_b = f"{thermal_b.mean_temp:.1f}°C" if (thermal_b and thermal_b.mean_temp is not None) else "N/A"
    delta_t_a = f"{thermal_a.thermal_anomaly_delta:.1f}°C" if (thermal_a and thermal_a.thermal_anomaly_delta is not None) else "N/A"
    delta_t_b = f"{thermal_b.thermal_anomaly_delta:.1f}°C" if (thermal_b and thermal_b.thermal_anomaly_delta is not None) else "N/A"

    prov_a = f"MLX90640 Sensor ({thermal_a.sensor_status})" if (thermal_a and thermal_a.sensor_status and thermal_a.insulation_score is not None) else "Not assessed (No Thermal Data)"
    prov_b = f"MLX90640 Sensor ({thermal_b.sensor_status})" if (thermal_b and thermal_b.sensor_status and thermal_b.insulation_score is not None) else "Not assessed (No Thermal Data)"

    status_a = "active" if score_a is not None else "unassessed"
    status_b = "active" if score_b is not None else "unassessed"

    if score_a is not None and score_b is not None:
        reason = (
            f"Thermal score: Property A ({score_a:.0f}/100, {anom_a} anomaly spots, delta {delta_t_a}) vs "
            f"Property B ({score_b:.0f}/100, {anom_b} anomaly spots, delta {delta_t_b}), Delta: {delta} pts. Advantage {adv}."
        )
        if score_a > score_b:
            explanation = (
                f"Property A exhibits better thermal envelope insulation (+{delta} pts) with fewer localized temperature anomalies "
                f"({anom_a} vs {anom_b} anomaly pixels) and lower overall temperature gradient ({delta_t_a} vs {delta_t_b})."
            )
        elif score_b > score_a:
            explanation = (
                f"Property B exhibits better thermal envelope insulation (+{delta} pts) with fewer localized temperature anomalies "
                f"({anom_b} vs {anom_a} anomaly pixels) and lower overall temperature gradient ({delta_t_b} vs {delta_t_a})."
            )
        else:
            explanation = f"Both properties demonstrate equivalent thermal insulation performance ({score_a:.0f}/100)."
    elif score_a is not None:
        reason = f"Property A thermal scan active ({score_a:.0f}/100). Property B thermal data not provided."
        explanation = "Property A provided empirical thermal infrared data, whereas Property B has no hardware sensor readings."
    elif score_b is not None:
        reason = f"Property B thermal scan active ({score_b:.0f}/100). Property A thermal data not provided."
        explanation = "Property B provided empirical thermal infrared data, whereas Property A has no hardware sensor readings."
    else:
        reason = "Thermal insulation not assessed for both properties (no thermal data provided)."
        explanation = "Neither property provided MLX90640 thermal infrared frame matrices or thermal scans."

    return ModuleDifference(
        module_key="thermal",
        module_label="Thermal Insulation & Sensor",
        weight_pct="20%",
        score_a=score_a,
        score_b=score_b,
        score_delta=delta,
        advantage=adv,
        reason=reason,
        explanation=explanation,
        provenance_a=prov_a,
        provenance_b=prov_b,
        coverage_status=cov_status,
        status_a=status_a,
        status_b=status_b,
    )


def _compare_aqi(
    aqi_a,
    aqi_b,
    label_a: str,
    label_b: str,
    status_a: Optional[str] = None,
    status_b: Optional[str] = None,
    err_a: Optional[str] = None,
    err_b: Optional[str] = None,
) -> ModuleDifference:
    score_a = aqi_a.environmental_score if (aqi_a and aqi_a.environmental_score is not None) else None
    score_b = aqi_b.environmental_score if (aqi_b and aqi_b.environmental_score is not None) else None
    adv, delta, cov_status = _resolve_advantage(score_a, score_b)

    val_a = f"{aqi_a.aqi_value:.0f}" if (aqi_a and aqi_a.aqi_value is not None) else "N/A"
    val_b = f"{aqi_b.aqi_value:.0f}" if (aqi_b and aqi_b.aqi_value is not None) else "N/A"
    cat_a = (aqi_a.category or "") if aqi_a else ""
    cat_b = (aqi_b.category or "") if aqi_b else ""
    stn_a = aqi_a.station_name if (aqi_a and aqi_a.station_name) else "Local Station"
    stn_b = aqi_b.station_name if (aqi_b and aqi_b.station_name) else "Local Station"

    st_a = status_a or ("active" if score_a is not None else "not_assessed")
    st_b = status_b or ("active" if score_b is not None else "not_assessed")

    failed_a = (st_a == "fetch_failed")
    failed_b = (st_b == "fetch_failed")

    def _provenance_for_aqi(score, aqi_obj, stn, status):
        if score is not None and aqi_obj:
            src = getattr(aqi_obj, "source", None) or "Air Quality API"
            scale_lbl = getattr(aqi_obj, "scale", "")
            scale_str = f" [Scale: {scale_lbl}]" if scale_lbl else ""
            return f"{src} ('{stn}'){scale_str}"
        if status == "provider_not_configured":
            return "Provider not configured"
        if status == "fetch_failed":
            return "Fetch Failed (API Error / Timeout)"
        if status == "data_unavailable":
            return "Data unavailable (No nearby readings)"
        return "Not assessed"

    prov_a = _provenance_for_aqi(score_a, aqi_a, stn_a, st_a)
    prov_b = _provenance_for_aqi(score_b, aqi_b, stn_b, st_b)

    scale_a_str = f" (Scale: {aqi_a.scale})" if (aqi_a and getattr(aqi_a, "scale", None)) else ""
    scale_b_str = f" (Scale: {aqi_b.scale})" if (aqi_b and getattr(aqi_b, "scale", None)) else ""

    if score_a is not None and score_b is not None:
        reason = (
            f"Air quality: Property A ({score_a:.0f}/100, AQI {val_a}{scale_a_str} {cat_a}) vs "
            f"Property B ({score_b:.0f}/100, AQI {val_b}{scale_b_str} {cat_b}), Delta: {delta} pts. Advantage {adv}."
        )
        if score_a > score_b:
            explanation = (
                f"Property A has superior ambient air quality (+{delta} pts environmental score) with an AQI of {val_a} ({cat_a} at {stn_a}) "
                f"compared to Property B's AQI of {val_b} ({cat_b} at {stn_b})."
            )
        elif score_b > score_a:
            explanation = (
                f"Property B has superior ambient air quality (+{delta} pts environmental score) with an AQI of {val_b} ({cat_b} at {stn_b}) "
                f"compared to Property A's AQI of {val_a} ({cat_a} at {stn_a})."
            )
        else:
            explanation = f"Both properties share comparable ambient air quality index levels (AQI {val_a})."
    elif score_a is not None:
        if st_b == "provider_not_configured":
            reason = f"Property A AQI active ({score_a:.0f}/100, AQI {val_a} from {stn_a}). Property B AQI provider not configured."
            explanation = f"Property A resolved verified air quality data ({stn_a}, AQI {val_a}), whereas Property B could not be evaluated because no air pollution API key is configured."
        elif st_b == "fetch_failed":
            reason = f"Property A AQI active ({score_a:.0f}/100, AQI {val_a} from {stn_a}). Property B live AQI fetch failed."
            explanation = f"Property A resolved verified air quality data ({stn_a}, AQI {val_a}), whereas Property B live AQI fetch failed ({err_b or 'API error'})."
        elif st_b == "data_unavailable":
            reason = f"Property A AQI active ({score_a:.0f}/100, AQI {val_a} from {stn_a}). Property B AQI data unavailable."
            explanation = f"Property A resolved verified air quality data ({stn_a}, AQI {val_a}), whereas Property B has no valid air pollution readings."
        else:
            reason = f"Property A AQI active ({score_a:.0f}/100, AQI {val_a} from {stn_a}). Property B AQI not assessed."
            explanation = f"Property A resolved verified air quality data ({stn_a}, AQI {val_a}), whereas Property B AQI was not assessed."
    elif score_b is not None:
        if st_a == "provider_not_configured":
            reason = f"Property B AQI active ({score_b:.0f}/100, AQI {val_b} from {stn_b}). Property A AQI provider not configured."
            explanation = f"Property B resolved verified air quality data ({stn_b}, AQI {val_b}), whereas Property A could not be evaluated because no air pollution API key is configured."
        elif st_a == "fetch_failed":
            reason = f"Property B AQI active ({score_b:.0f}/100, AQI {val_b} from {stn_b}). Property A live AQI fetch failed."
            explanation = f"Property B resolved verified air quality data ({stn_b}, AQI {val_b}), whereas Property A live AQI fetch failed ({err_a or 'API error'})."
        elif st_a == "data_unavailable":
            reason = f"Property B AQI active ({score_b:.0f}/100, AQI {val_b} from {stn_b}). Property A AQI data unavailable."
            explanation = f"Property B resolved verified air quality data ({stn_b}, AQI {val_b}), whereas Property A has no valid air pollution readings."
        else:
            reason = f"Property B AQI active ({score_b:.0f}/100, AQI {val_b} from {stn_b}). Property A AQI not assessed."
            explanation = f"Property B resolved verified air quality data ({stn_b}, AQI {val_b}), whereas Property A AQI was not assessed."
    else:
        # Both null
        if st_a == "provider_not_configured" and st_b == "provider_not_configured":
            reason = "Air quality provider not configured (OPENWEATHER_API_KEY / AQICN_TOKEN missing from backend environment)."
            explanation = "Neither property could evaluate ambient air quality because no valid air pollution API key is configured in the environment."
        elif failed_a or failed_b:
            reason = "Air quality data fetch failed due to API connection error, invalid key, or timeout."
            explanation = f"Live ambient air quality readings could not be retrieved for one or both properties (Property A: {st_a}, Property B: {st_b})."
        elif st_a == "data_unavailable" and st_b == "data_unavailable":
            reason = "AQI data unavailable for both properties."
            explanation = "Neither property resolved valid air pollution readings from configured providers."
        else:
            reason = "Air quality (AQI) not assessed for both properties."
            explanation = "Neither property could be evaluated for ambient air quality."

    return ModuleDifference(
        module_key="aqi",
        module_label="Air Quality (AQI) Indicator",
        weight_pct="Supplemental",
        score_a=score_a,
        score_b=score_b,
        score_delta=delta,
        advantage=adv,
        reason=reason,
        explanation=explanation,
        provenance_a=prov_a,
        provenance_b=prov_b,
        coverage_status=cov_status,
        fetch_failed_a=failed_a,
        fetch_failed_b=failed_b,
        status_a=st_a,
        status_b=st_b,
        error_message_a=err_a,
        error_message_b=err_b,
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
) -> Tuple[str, List[str], str, Optional[str]]:
    cov_a = resp_a.score_weight_coverage or 0.0
    cov_b = resp_b.score_weight_coverage or 0.0
    is_asymmetric = cov_a != cov_b

    # Determine confidence level and asymmetric warning
    if is_asymmetric:
        confidence = "Limited"
        asymmetric_warning = (
            f"Asymmetric assessment coverage: Property A was evaluated with {cov_a}% weight coverage "
            f"({resp_a.active_modules_count or 0}/4 core modules), whereas Property B was evaluated with "
            f"{cov_b}% weight coverage ({resp_b.active_modules_count or 0}/4 core modules). "
            "Direct composite score delta must be interpreted with caution as differing module subsets contribute to each score."
        )
    else:
        asymmetric_warning = None
        if cov_a >= 100.0:
            confidence = "High"
        elif cov_a >= 50.0:
            confidence = "Medium"
        else:
            confidence = "Limited"

    if score_a is not None and score_b is not None:
        if score_a > score_b:
            winner_addr, loser_addr = req_a.address, req_b.address
            winner_score, loser_score = score_a, score_b
            winner_prov = 'PROVISIONAL' if resp_a.is_provisional else 'FINAL'
            loser_prov = 'PROVISIONAL' if resp_b.is_provisional else 'FINAL'
            winner_cov, loser_cov = cov_a, cov_b
        elif score_b > score_a:
            winner_addr, loser_addr = req_b.address, req_a.address
            winner_score, loser_score = score_b, score_a
            winner_prov = 'PROVISIONAL' if resp_b.is_provisional else 'FINAL'
            loser_prov = 'PROVISIONAL' if resp_a.is_provisional else 'FINAL'
            winner_cov, loser_cov = cov_b, cov_a
        else:
            summary = (
                f"Comparative Assessment: Both '{req_a.address}' and '{req_b.address}' "
                f"achieved equal composite scores of {score_a:.1f}/100. "
                f"Comparison Confidence: {confidence} ({cov_a}% vs {cov_b}% coverage)."
            )
            takeaways = [d.explanation or d.reason for d in module_diffs]
            return summary, takeaways, confidence, asymmetric_warning

        asym_note = f" Note: Comparison confidence is {confidence} due to asymmetric data coverage." if is_asymmetric else ""
        summary = (
            f"Comparative Assessment: '{winner_addr}' outperforms '{loser_addr}' "
            f"with a composite score of {winner_score:.1f}/100 vs {loser_score:.1f}/100 "
            f"(margin +{overall_delta:.1f} pts). "
            f"Winner rating: {winner_prov} ({winner_cov}% coverage). "
            f"Runner-up: {loser_prov} ({loser_cov}% coverage).{asym_note}"
        )
    else:
        summary = (
            f"Comparative Assessment: Inspection for '{req_a.address}' and '{req_b.address}' performed. "
            f"One or both composite scores could not be computed due to unassessed core modules."
        )

    takeaways = [d.explanation or d.reason for d in module_diffs]
    return summary, takeaways, confidence, asymmetric_warning


# ── Public entry point ────────────────────────────────────────────────────────

def compare_inspection_results(
    resp_a: ScoreResponse,
    resp_b: ScoreResponse,
    req_a: ScoreRequest,
    req_b: ScoreRequest,
) -> CompareResponse:
    """Compare two real property inspection responses using grounded metric logic and provenance."""
    label_a = f"{req_a.address} ({req_a.property_type})"
    label_b = f"{req_b.address} ({req_b.property_type})"

    module_diffs: List[ModuleDifference] = [
        _compare_price(
            resp_a.price,
            resp_b.price,
            label_a,
            label_b,
            status_a=getattr(resp_a, "price_status", None),
            status_b=getattr(resp_b, "price_status", None),
            err_a=getattr(resp_a, "price_error", None),
            err_b=getattr(resp_b, "price_error", None),
        ),
        _compare_aqi(
            resp_a.aqi,
            resp_b.aqi,
            label_a,
            label_b,
            status_a=getattr(resp_a, "aqi_status", None),
            status_b=getattr(resp_b, "aqi_status", None),
            err_a=getattr(resp_a, "aqi_error", None),
            err_b=getattr(resp_b, "aqi_error", None),
        ),
        _compare_location(resp_a.location, resp_b.location, label_a, label_b),
        _compare_cv      (resp_a.cv,       resp_b.cv,       label_a, label_b),
        _compare_thermal (resp_a.thermal,  resp_b.thermal,  label_a, label_b),
    ]

    score_a = resp_a.overall_score
    score_b = resp_b.overall_score
    cov_a = float(resp_a.score_weight_coverage or 0.0)
    cov_b = float(resp_b.score_weight_coverage or 0.0)
    active_a = int(resp_a.active_modules_count or 0)
    active_b = int(resp_b.active_modules_count or 0)

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
        overall_winner = "Incomparable (both properties unassessed)"

    summary, takeaways, confidence, asym_warning = _build_comparison_narrative(
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
        coverage_a=cov_a,
        coverage_b=cov_b,
        active_modules_a=active_a,
        active_modules_b=active_b,
        comparison_confidence=confidence,
        asymmetric_warning=asym_warning,
        module_differences=module_diffs,
        comparison_summary=summary,
        key_takeaways=takeaways,
    )
