import asyncio
import logging
from typing import Any
from fastapi import APIRouter, HTTPException, status

from backend.models.score import ScoreRequest, ScoreResponse, CompareRequest, CompareResponse, PriceBenchmarkResult, AQIResult
from backend.services.location import fetch_location
from backend.services.aqi import fetch_aqi
from backend.services.price import fetch_price_benchmark_with_status
from backend.services.cv_model import run_cv_analysis
from backend.services.thermal import run_thermal_analysis
from backend.services.scoring import calculate_overall_score
from backend.services.report import generate_report
from backend.services.decision import generate_decision_insights
from backend.services.compare import compare_inspection_results

router = APIRouter(prefix="/api", tags=["scoring"])
logger = logging.getLogger("nivas.api.score")


def safe_result(res: Any) -> Any:
    """Safely return None if task raised an exception."""
    if isinstance(res, Exception):
        logger.warning("Module task raised exception: %s", str(res))
        return None
    return res


async def evaluate_single_property(request: ScoreRequest) -> ScoreResponse:
    """Helper function to execute full inspection scoring pipeline for a single property."""
    # 1. Geocode location first to get coordinates
    location_res = await fetch_location(request.address)

    # 2. Run remaining independent service calls in parallel
    lat = location_res.latitude if location_res else None
    lon = location_res.longitude if location_res else None

    aqi_task = fetch_aqi(request.address, lat=lat, lon=lon)
    price_task = fetch_price_benchmark_with_status(request.address, request.property_type)
    cv_task = run_cv_analysis(request.image_info)
    thermal_task = run_thermal_analysis(request.image_info)

    raw_results = await asyncio.gather(
        aqi_task,
        price_task,
        cv_task,
        thermal_task,
        return_exceptions=True,
    )

    aqi_raw = safe_result(raw_results[0])
    price_raw = safe_result(raw_results[1])
    cv_res = safe_result(raw_results[2])
    thermal_res = safe_result(raw_results[3])

    if isinstance(aqi_raw, tuple) and len(aqi_raw) == 3:
        aqi_res, aqi_status, aqi_err = aqi_raw
    elif isinstance(aqi_raw, AQIResult):
        aqi_res = aqi_raw
        aqi_status = "active" if aqi_res.environmental_score is not None else "data_unavailable"
        aqi_err = None
    else:
        aqi_res = None
        aqi_status = "provider_not_configured"
        aqi_err = "AQI provider not configured in environment"

    if isinstance(price_raw, tuple) and len(price_raw) == 3:
        price_res, price_status, price_err = price_raw
    elif isinstance(price_raw, PriceBenchmarkResult):
        price_res = price_raw
        price_status = "active" if price_res.fairness_score is not None else "data_unavailable"
        price_err = None
    else:
        price_res = None
        price_status = "data_unavailable"
        price_err = "Price benchmark data unavailable"

    # Compute composite score & report asynchronously based on module outputs
    overall_score, is_provisional, active_count, coverage_pct = await calculate_overall_score(
        location=location_res,
        aqi=aqi_res,
        price=price_res,
        cv=cv_res,
        thermal=thermal_res,
    )

    report_res = await generate_report(
        address=request.address,
        property_type=request.property_type,
        overall_score=overall_score,
        is_provisional=is_provisional,
        active_modules_count=active_count,
        score_weight_coverage=coverage_pct,
        location=location_res,
        aqi=aqi_res,
        price=price_res,
        cv=cv_res,
        thermal=thermal_res,
    )

    decision_res = generate_decision_insights(
        address=request.address,
        property_type=request.property_type,
        overall_score=overall_score,
        is_provisional=is_provisional,
        active_modules_count=active_count,
        score_weight_coverage=coverage_pct,
        location=location_res,
        aqi=aqi_res,
        price=price_res,
        cv=cv_res,
        thermal=thermal_res,
    )

    return ScoreResponse(
        location=location_res,
        aqi=aqi_res,
        aqi_status=aqi_status,
        aqi_error=aqi_err,
        price=price_res,
        price_status=price_status,
        price_error=price_err,
        cv=cv_res,
        thermal=thermal_res,
        overall_score=overall_score,
        is_provisional=is_provisional,
        active_modules_count=active_count,
        score_weight_coverage=coverage_pct,
        decision_insights=decision_res,
        report=report_res,
    )


@router.post(
    "/score",
    response_model=ScoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Compute property score and inspection report",
)
async def compute_score(request: ScoreRequest) -> ScoreResponse:
    try:
        return await evaluate_single_property(request)
    except Exception as e:
        logger.error("Error processing score request: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing score request: {str(e)}",
        )


@router.post(
    "/score/compare",
    response_model=CompareResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare two properties using the scoring engine",
)
async def compare_properties(request: CompareRequest) -> CompareResponse:
    try:
        # Run inspection pipelines for Property A and Property B in parallel
        results = await asyncio.gather(
            evaluate_single_property(request.property_a),
            evaluate_single_property(request.property_b),
            return_exceptions=True,
        )

        res_a = safe_result(results[0])
        res_b = safe_result(results[1])

        if not res_a or not res_b:
            raise ValueError("Failed to evaluate one or both properties in comparison request")

        return compare_inspection_results(
            resp_a=res_a,
            resp_b=res_b,
            req_a=request.property_a,
            req_b=request.property_b,
        )
    except Exception as e:
        logger.error("Error processing property comparison request: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing property comparison request: {str(e)}",
        )
