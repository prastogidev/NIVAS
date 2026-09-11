from typing import Optional, List, Dict, Any
from backend.models.score import (
    DecisionInsights,
    DecisionRisk,
    DecisionFactor,
    RecommendedCheck,
    LocationResult,
    AQIResult,
    PriceBenchmarkResult,
    CVModelResult,
    ThermalModuleResult,
)


def generate_decision_insights(
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
) -> Optional[DecisionInsights]:
    """
    Generate an explainable, deterministic buyer decision layer on top of module outputs.

    Guarantees:
    - Purely deterministic and explainable (zero hallucinated facts or black-box neural layers).
    - Every positive factor, risk, and check cites empirical evidence from active module fields.
    - Accurately conveys provisional confidence when assessment modules are missing.
    """
    if overall_score is None:
        return None

    active_count = active_modules_count if active_modules_count is not None else 0
    coverage = score_weight_coverage if score_weight_coverage is not None else 0.0

    # 1. Confidence Level Determination
    if coverage >= 100.0 and active_count == 4:
        confidence_level = "High"
    elif coverage >= 50.0:
        confidence_level = "Medium"
    else:
        confidence_level = "Low"

    # 2. Coverage Summary
    evaluated_modules = []
    missing_modules = []

    if location and location.risk_score is not None:
        evaluated_modules.append("Location & Infrastructure (25%)")
    else:
        missing_modules.append("Location & Infrastructure (25%)")

    if price and price.fairness_score is not None:
        evaluated_modules.append("Price Benchmark (25%)")
    else:
        missing_modules.append("Price Benchmark (25%)")

    if cv and cv.structural_score is not None:
        evaluated_modules.append("Computer Vision Wall Defect (30%)")
    else:
        missing_modules.append("Computer Vision Wall Defect (30%)")

    if thermal and thermal.insulation_score is not None:
        evaluated_modules.append("Thermal Insulation (20%)")
    else:
        missing_modules.append("Thermal Insulation (20%)")

    if missing_modules:
        coverage_summary = (
            f"Evaluated {active_count} of 4 core modules ({coverage}% weight coverage: {', '.join(evaluated_modules)}). "
            f"Missing inputs: {', '.join(missing_modules)}."
        )
    else:
        coverage_summary = (
            f"Comprehensive evaluation: all 4 core modules active with 100.0% weight coverage."
        )

    # 3. Positive Factors (Strengths)
    positive_factors: List[DecisionFactor] = []

    if location and location.risk_score is not None and location.risk_score >= 70.0:
        inf = location.infrastructure
        counts_desc = (
            f"{inf.hospitals_count} hospital(s), {inf.schools_count} school(s), "
            f"{inf.railway_stations_count} metro/rail station(s), and {inf.major_roads_count} arterial road(s)"
            if inf else "verified transit and social amenities"
        )
        positive_factors.append(
            DecisionFactor(
                category="location",
                title="Strong Transit & Civic Infrastructure",
                description=(
                    f"Overpass infrastructure query scored {location.risk_score:.0f}/100 with {counts_desc} "
                    f"within a 1.2km radius of {location.locality or address}."
                ),
                evidence={
                    "risk_score": location.risk_score,
                    "locality": location.locality,
                    "hospitals_count": inf.hospitals_count if inf else 0,
                    "schools_count": inf.schools_count if inf else 0,
                    "railway_stations_count": inf.railway_stations_count if inf else 0,
                    "major_roads_count": inf.major_roads_count if inf else 0,
                },
            )
        )

    if price and price.fairness_score is not None and price.fairness_score >= 80.0:
        p_val = price.estimated_price_per_sqft or 0.0
        p_source = price.source or "Locality Benchmark Reference"
        sample_txt = f" across {price.sample_count} samples" if price.sample_count else ""
        positive_factors.append(
            DecisionFactor(
                category="price",
                title="Favorable Benchmark Price Alignment",
                description=(
                    f"Estimated rate of ₹{p_val:,.0f}/sq.ft is aligned with median market metrics (Fairness score: {price.fairness_score:.0f}/100) "
                    f"benchmarked against {p_source}{sample_txt}."
                ),
                evidence={
                    "estimated_price_per_sqft": p_val,
                    "fairness_score": price.fairness_score,
                    "source": p_source,
                    "sample_count": price.sample_count,
                },
            )
        )

    if cv and cv.structural_score is not None and (cv.structural_score >= 80.0 or cv.predicted_class == "clean"):
        conf_pct = (cv.confidence * 100.0) if cv.confidence is not None else 0.0
        positive_factors.append(
            DecisionFactor(
                category="cv",
                title="Sound Wall Surface Condition",
                description=(
                    f"Visual defect inspection confirmed clean wall condition (Structural score: {cv.structural_score:.0f}/100, "
                    f"confidence: {conf_pct:.1f}%) with no detected dampness, algae, or mold."
                ),
                evidence={
                    "structural_score": cv.structural_score,
                    "predicted_class": cv.predicted_class,
                    "confidence": cv.confidence,
                },
            )
        )

    if thermal and thermal.insulation_score is not None and (thermal.insulation_score >= 80.0 or (thermal.anomalies_detected_count or 0) <= 2):
        mean_t = thermal.mean_temp or 0.0
        anom_cnt = thermal.anomalies_detected_count or 0
        positive_factors.append(
            DecisionFactor(
                category="thermal",
                title="Consistent Thermal Profile & Insulation",
                description=(
                    f"Thermal matrix scan indicated uniform temperature distribution (mean: {mean_t:.1f}°C, "
                    f"insulation score: {thermal.insulation_score:.0f}/100) with only {anom_cnt} localized thermal anomaly pixels."
                ),
                evidence={
                    "insulation_score": thermal.insulation_score,
                    "mean_temp": thermal.mean_temp,
                    "anomalies_detected_count": anom_cnt,
                    "thermal_anomaly_delta": thermal.thermal_anomaly_delta,
                },
            )
        )

    if aqi and aqi.aqi_value is not None and aqi.aqi_value <= 100.0:
        positive_factors.append(
            DecisionFactor(
                category="aqi",
                title="Acceptable Local Air Quality",
                description=(
                    f"Geographically verified AQICN station '{aqi.station_name}' reported an ambient AQI of {aqi.aqi_value:.0f} "
                    f"({aqi.category or 'Satisfactory'}), indicating acceptable environmental conditions."
                ),
                evidence={
                    "aqi_value": aqi.aqi_value,
                    "category": aqi.category,
                    "station_name": aqi.station_name,
                },
            )
        )

    # 4. Key Risks (Caveats & Deficits)
    key_risks: List[DecisionRisk] = []

    if is_provisional or coverage < 100.0:
        risk_sev = "high" if coverage < 50.0 else "medium"
        key_risks.append(
            DecisionRisk(
                category="composite",
                severity=risk_sev,
                title="Provisional Assessment Coverage Gap",
                description=(
                    f"Evaluation currently covers {coverage}% of total module weight ({active_count}/4 core modules). "
                    f"Missing signals ({', '.join(missing_modules)}) present unassessed structural, thermal, or pricing risks."
                ),
                evidence={
                    "active_modules_count": active_count,
                    "score_weight_coverage": coverage,
                    "missing_modules": missing_modules,
                },
            )
        )

    if location and location.risk_score is not None and location.risk_score < 60.0:
        key_risks.append(
            DecisionRisk(
                category="location",
                severity="medium",
                title="Limited Nearby Infrastructure Access",
                description=(
                    f"Location accessibility score of {location.risk_score:.0f}/100 indicates sparse emergency healthcare "
                    f"or rapid mass transit connectivity within the 1.2km evaluation perimeter."
                ),
                evidence={
                    "risk_score": location.risk_score,
                    "locality": location.locality,
                },
            )
        )

    if price and price.fairness_score is not None and price.fairness_score < 70.0:
        p_sev = "high" if price.fairness_score < 50.0 else "medium"
        p_val = price.estimated_price_per_sqft or 0.0
        key_risks.append(
            DecisionRisk(
                category="price",
                severity=p_sev,
                title="Price Valuation Premium / Overpricing Risk",
                description=(
                    f"Estimated rate of ₹{p_val:,.0f}/sq.ft reflects a price premium (Fairness score: {price.fairness_score:.0f}/100) "
                    f"compared to locality circle rates and benchmark references."
                ),
                evidence={
                    "estimated_price_per_sqft": p_val,
                    "fairness_score": price.fairness_score,
                },
            )
        )

    if cv and cv.structural_score is not None and cv.predicted_class in ["damp", "mold", "algae"]:
        defect_sev = "critical" if cv.predicted_class == "mold" else "high"
        cov_pct = ((cv.defect_coverage_ratio or 0.0) * 100.0)
        key_risks.append(
            DecisionRisk(
                category="cv",
                severity=defect_sev,
                title=f"Surface Wall Defect Detected ({cv.predicted_class.capitalize()})",
                description=(
                    f"Computer vision model detected active '{cv.predicted_class}' covering approximately {cov_pct:.1f}% "
                    f"of the analyzed surface (Structural score: {cv.structural_score:.0f}/100)."
                ),
                evidence={
                    "predicted_class": cv.predicted_class,
                    "defects_detected": cv.defects_detected,
                    "defect_coverage_ratio": cv.defect_coverage_ratio,
                    "structural_score": cv.structural_score,
                },
            )
        )
    elif cv and cv.is_blurry:
        key_risks.append(
            DecisionRisk(
                category="cv",
                severity="low",
                title="Visual Scan Blur Degradation",
                description=(
                    "Uploaded wall image exhibits high blurriness (low Laplacian variance), which reduces defect detection sensitivity."
                ),
                evidence={"is_blurry": True},
            )
        )

    if thermal and thermal.insulation_score is not None and (thermal.insulation_score < 70.0 or (thermal.anomalies_detected_count or 0) > 5):
        t_sev = "high" if (thermal.insulation_score or 100) < 50.0 else "medium"
        anom_cnt = thermal.anomalies_detected_count or 0
        delta_t = thermal.thermal_anomaly_delta or 0.0
        key_risks.append(
            DecisionRisk(
                category="thermal",
                severity=t_sev,
                title="Thermal Bridging / Localized Heat Leakage",
                description=(
                    f"Thermal matrix analysis identified {anom_cnt} anomalous pixels with a temperature variation span of {delta_t:.1f}°C "
                    f"(Insulation score: {thermal.insulation_score:.0f}/100)."
                ),
                evidence={
                    "insulation_score": thermal.insulation_score,
                    "anomalies_detected_count": anom_cnt,
                    "thermal_anomaly_delta": delta_t,
                },
            )
        )

    if aqi and aqi.aqi_value is not None and aqi.aqi_value > 200.0:
        key_risks.append(
            DecisionRisk(
                category="aqi",
                severity="high",
                title="Elevated Environmental Particulate Pollution",
                description=(
                    f"Local monitoring station '{aqi.station_name}' reported severe AQI of {aqi.aqi_value:.0f} "
                    f"({aqi.category or 'Poor/Severe'}), indicating potential indoor air quality challenges."
                ),
                evidence={
                    "aqi_value": aqi.aqi_value,
                    "category": aqi.category,
                    "station_name": aqi.station_name,
                },
            )
        )

    # 5. Targeted Recommended Checks (Due Diligence)
    recommended_checks: List[RecommendedCheck] = []

    # Check for missing visual or thermal scans
    if cv is None or cv.structural_score is None:
        recommended_checks.append(
            RecommendedCheck(
                category="structural",
                priority="medium",
                action="Upload wall facade photos or perform on-site visual inspection for hairline cracks and efflorescence.",
                rationale="No RGB image was uploaded for automated computer vision defect screening.",
            )
        )

    if thermal is None or thermal.insulation_score is None:
        recommended_checks.append(
            RecommendedCheck(
                category="thermal",
                priority="standard",
                action="Inspect window seals, door weatherstripping, and air conditioning ducting for air infiltration.",
                rationale="Thermal infrared sensor (MLX90640) data was not provided.",
            )
        )

    # Specific defect-driven checks
    if cv and cv.predicted_class in ["damp", "mold", "algae"]:
        recommended_checks.append(
            RecommendedCheck(
                category="structural",
                priority="high",
                action=f"Commission a moisture meter scan and plumbing seepage inspection to isolate the source of {cv.predicted_class}.",
                rationale=f"Automated computer vision scan flagged {cv.predicted_class} with {cv.structural_score:.0f}/100 structural score.",
            )
        )

    if thermal and thermal.insulation_score is not None and thermal.insulation_score < 75.0:
        recommended_checks.append(
            RecommendedCheck(
                category="thermal",
                priority="high",
                action="Conduct a professional thermography audit to identify wall thermal bridging and insulation voids.",
                rationale=f"Thermal insulation score of {thermal.insulation_score:.0f}/100 indicated localized temperature anomalies.",
            )
        )

    if price and price.fairness_score is not None and price.fairness_score < 75.0:
        p_val = price.estimated_price_per_sqft or 0.0
        recommended_checks.append(
            RecommendedCheck(
                category="financial",
                priority="high",
                action="Review recent sub-registrar registered sale deeds in this specific wing/sector and negotiate asking price.",
                rationale=f"Current valuation of ₹{p_val:,.0f}/sq.ft carries a premium relative to locality reference datasets.",
            )
        )

    if location and location.infrastructure:
        inf = location.infrastructure
        if inf.hospitals_count == 0 or inf.schools_count == 0:
            recommended_checks.append(
                RecommendedCheck(
                    category="location",
                    priority="medium",
                    action="Check physical road commute times to the nearest multispecialty emergency hospital and schools.",
                    rationale="OpenStreetMap Overpass query identified 0 direct hospitals or schools within 1.2km radius.",
                )
            )

    if aqi and aqi.aqi_value is not None and aqi.aqi_value > 150.0:
        recommended_checks.append(
            RecommendedCheck(
                category="environmental",
                priority="medium",
                action="Budget for indoor air filtration (HEPA purifiers) and inspect door/window sealing.",
                rationale=f"Ambient AQI in this locality is {aqi.aqi_value:.0f} ({aqi.category}).",
            )
        )

    # Universal Legal Due Diligence
    recommended_checks.append(
        RecommendedCheck(
            category="legal",
            priority="high",
            action="Verify Title Deeds (30-year search), Encumbrance Certificate (EC), Sanctioned Building Plan, and Occupancy Certificate (OC).",
            rationale="Essential statutory due diligence required for every Indian real estate transaction.",
        )
    )

    # 6. Executive Verdict & Synthesis Narrative
    if is_provisional:
        if overall_score >= 80.0:
            verdict = "Provisional Favorable Candidate (Verification Recommended)"
        elif overall_score >= 60.0:
            verdict = "Provisional Moderate Alignment (Due Diligence Required)"
        else:
            verdict = "Provisional Elevated Risk (Requires Strict Caution)"
    else:
        if overall_score >= 80.0:
            verdict = "Strong Investment / Acquisition Contender"
        elif overall_score >= 60.0:
            verdict = "Fair Market Contender (Negotiation Advised)"
        else:
            verdict = "High Risk Property (Substantial Defects / Overpriced)"

    # Synthesize plain-language overall interpretation
    synth_parts = [
        f"NIVAS Decision Analysis for {address} ({property_type}) yields an overall rating of {overall_score:.1f}/100.",
    ]
    if is_provisional:
        synth_parts.append(
            f"This evaluation is PROVISIONAL with {confidence_level} confidence ({coverage}% weight coverage across {active_count} active modules)."
        )
    else:
        synth_parts.append(
            f"This evaluation is FINAL with {confidence_level} confidence across all 4 weighted assessment modules."
        )

    if positive_factors:
        strengths_summary = "; ".join([f.title for f in positive_factors[:3]])
        synth_parts.append(f"Key property strengths include: {strengths_summary}.")

    if key_risks:
        risks_summary = "; ".join([r.title for r in key_risks if r.severity in ["critical", "high"]][:2])
        if risks_summary:
            synth_parts.append(f"Primary risk considerations to address: {risks_summary}.")
        elif len(key_risks) > 0:
            synth_parts.append(f"Notable risk factor: {key_risks[0].title}.")

    synth_parts.append(
        f"Recommended next step: Execute the {len(recommended_checks)} prioritized due-diligence checks before finalizing transaction terms."
    )

    overall_interpretation = " ".join(synth_parts)

    return DecisionInsights(
        verdict=verdict,
        overall_interpretation=overall_interpretation,
        confidence_level=confidence_level,
        key_risks=key_risks,
        positive_factors=positive_factors,
        recommended_checks=recommended_checks,
        coverage_summary=coverage_summary,
    )
