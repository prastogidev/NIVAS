from typing import Optional, List
from backend.models.score import (
    ReportResult,
    LocationResult,
    AQIResult,
    PriceBenchmarkResult,
    CVModelResult,
    ThermalModuleResult,
)


async def generate_report(
    address: str,
    property_type: str,
    overall_score: Optional[float],
    is_provisional: Optional[bool] = None,
    active_modules_count: Optional[int] = None,
    score_weight_coverage: Optional[float] = None,
    location: Optional[LocationResult] = None,
    aqi: Optional[AQIResult] = None,
    price: Optional[PriceBenchmarkResult] = None,
    cv: Optional[CVModelResult] = None,
    thermal: Optional[ThermalModuleResult] = None,
) -> Optional[ReportResult]:
    """
    Generate a plain-language property inspection report based strictly on real scores
    and empirical data returned by active modules.

    Guarantees:
    - Provisional scores are never described as a definitive 'Excellent' valuation when assessment modules are missing.
    - Clearly shows the score, active module count, and weight coverage.
    - Never invents unverified facts about the property.
    """
    if overall_score is None:
        return None

    # Determine qualitative composite rating from score range
    # When modules are missing (provisional), use non-definitive indicator phrasing.
    if is_provisional:
        if overall_score >= 80.0:
            rating_category = "Provisional Favorable Trend (Incomplete Assessment)"
        elif overall_score >= 60.0:
            rating_category = "Provisional Moderate Trend (Incomplete Assessment)"
        else:
            rating_category = "Provisional Elevated Risk (Incomplete Assessment)"
        status_str = "PROVISIONAL Composite Rating"
    else:
        if overall_score >= 80.0:
            rating_category = "Excellent / High Prime Value"
        elif overall_score >= 60.0:
            rating_category = "Moderate / Fair Market Value"
        else:
            rating_category = "Sub-optimal / High Inspection Risk"
        status_str = "Final Composite Rating"

    # Keep the composite inputs visible alongside every reported score.  These
    # fields describe how much evidence contributed to the score; they do not
    # affect its calculation.
    active_modules_display = (
        f"{active_modules_count} / 4" if active_modules_count is not None else "not available"
    )
    weight_coverage_display = (
        f"{score_weight_coverage}%" if score_weight_coverage is not None else "not available"
    )

    # 1. Plain-Language Executive Summary Paragraphs
    summary_parts = [
        f"NIVAS Property Assessment Report for {address} ({property_type}).",
        f"{status_str}: Score {overall_score}/100 ({rating_category}). "
        f"Active modules: {active_modules_display}. "
        f"Weight coverage: {weight_coverage_display}.",
    ]

    # Location Module Section
    if location and location.risk_score is not None:
        loc_score = location.risk_score
        loc_desc = (
            "Highly Accessible" if loc_score >= 80.0
            else "Moderate Accessibility" if loc_score >= 60.0
            else "Limited Nearby Infrastructure"
        )
        summary_parts.append(
            f"Location & Infrastructure (Score: {loc_score}/100 - {loc_desc}): "
            f"OpenStreetMap Overpass analysis at ({location.latitude:.4f}, {location.longitude:.4f}) detected "
        )
        if location.infrastructure:
            inf = location.infrastructure
            counts_str = (
                f"{inf.hospitals_count} hospital(s), {inf.schools_count} school(s), "
                f"{inf.clinics_count} clinic(s), {inf.railway_stations_count} railway/metro station(s), "
                f"and {inf.major_roads_count} major arterial road(s)."
            )
            summary_parts[-1] += counts_str
            if inf.nearby_places:
                places_sample = ", ".join(inf.nearby_places[:4])
                summary_parts.append(f"Notable nearby landmarks include: {places_sample}.")
    elif location:
        summary_parts.append("Location Infrastructure: Coordinates resolved, but detailed infrastructure query was unavailable.")
    else:
        summary_parts.append("Location Infrastructure: Location module was disconnected.")

    # AQI Module Section
    if aqi and aqi.environmental_score is not None:
        aqi_val = aqi.aqi_value
        aqi_cat = aqi.category or "Moderate"
        station = aqi.station_name or "Local Station"
        env_score = aqi.environmental_score
        summary_parts.append(
            f"Air Quality & Environment (Score: {env_score}/100): "
            f"AQICN monitoring station '{station}' reports an AQI of {aqi_val} ({aqi_cat})."
        )

    # Price Benchmark Section
    if price and price.fairness_score is not None:
        p_val = price.estimated_price_per_sqft or 0.0
        p_score = price.fairness_score
        source_name = price.source or "Locality Benchmark Datasets"
        p_desc = (
            "Fair Market Value" if p_score >= 85.0
            else "Fair to Slight Premium" if p_score >= 60.0
            else "High Market Premium"
        )
        summary_parts.append(
            f"Property Valuation (Fairness Score: {p_score}/100 - {p_desc}): "
            f"Estimated price of ₹{p_val:,.0f}/sq. ft. anchored against {source_name}"
        )
        if price.sample_count:
            summary_parts[-1] += f" ({price.sample_count} benchmark sample records)."
        else:
            summary_parts[-1] += "."
    else:
        summary_parts.append("Property Valuation: Local price benchmark data was unavailable for this locality.")

    # CV & Thermal Image Scans Section
    if cv and cv.structural_score is not None:
        summary_parts.append(f"Visual Scan: Structural integrity score of {cv.structural_score}/100 from surface defect scan.")
    else:
        summary_parts.append("Visual Scan: No RGB facade images were uploaded for computer vision defect analysis.")

    if thermal and thermal.insulation_score is not None:
        summary_parts.append(f"Thermal Scan: Insulation score of {thermal.insulation_score}/100.")
    else:
        summary_parts.append("Thermal Scan: No thermal infrared scans were uploaded for insulation inspection.")

    full_summary = " ".join(summary_parts)

    # 2. Score-Driven Actionable Recommendations List
    recommendations: List[str] = []

    if is_provisional:
        recommendations.append(
            f"PROVISIONAL ASSESSMENT NOTICE: Score {overall_score}/100 uses {active_modules_display} active core modules "
            f"and {weight_coverage_display} weight coverage. This score represents a preliminary partial evaluation and "
            "must not be treated as a definitive overall valuation. "
            "Upload property visual/thermal scans or missing module data to receive a full 100% composite score."
        )

    # Location recommendations
    if location and location.infrastructure:
        inf = location.infrastructure
        if inf.hospitals_count == 0 or inf.schools_count == 0:
            recommendations.append(
                "Social Infrastructure Due Diligence: Verify access to nearest emergency hospitals and schools, "
                "as OpenStreetMap returned zero direct listings within a 1.2km radius."
            )
        elif location.risk_score and location.risk_score >= 70.0:
            recommendations.append("Location Advantage: Excellent transit and social infrastructure connectivity detected within 1.2km.")

    # Price recommendations
    if price and price.fairness_score is not None:
        if price.fairness_score < 80.0 and price.estimated_price_per_sqft:
            recommendations.append(
                f"Price Negotiation: Asking rate of ₹{price.estimated_price_per_sqft:,.0f}/sq. ft. carries a market premium. "
                f"Reference government circle rates and locality benchmark data ({price.source or 'Locality Reference'}) during price negotiations."
            )
        elif price.fairness_score >= 85.0 and price.estimated_price_per_sqft:
            recommendations.append(
                f"Valuation Alignment: Estimated rate of ₹{price.estimated_price_per_sqft:,.0f}/sq. ft. is aligned with the locality benchmark median ({price.source or 'Locality Benchmark'})."
            )

    # AQI recommendations
    if aqi and aqi.aqi_value is not None:
        if aqi.aqi_value > 100.0:
            recommendations.append(
                f"Environmental Caution: Local AQI is {aqi.aqi_value} ({aqi.category}). Recommend installing indoor HEPA air filtration."
            )
        else:
            recommendations.append(f"Air Quality Verification: AQI is {aqi.aqi_value} ({aqi.category}), indicating acceptable ambient air.")

    # General legal and structural due diligence
    recommendations.append(
        "Standard Legal Audit: Inspect non-encumbrance certificates, municipal building plan sanctions, and land title deeds."
    )

    return ReportResult(
        summary=full_summary,
        recommendations=recommendations,
    )
