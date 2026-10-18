import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from backend.models.livability import (
    LivabilityDataRequest,
    LivabilityLocationDataResponse,
    LivabilityInfrastructureData,
    LivabilityFacilityItem,
    LivabilityAirQualityData,
    LivabilityHazardData,
    LivabilityChatRequest,
    LivabilityChatResponse,
)
from backend.models.score import InfrastructureSummary
from backend.services.location import fetch_overpass_infrastructure
from backend.services.air_quality import fetch_real_aqi_with_status
from backend.services.livability_advisor import generate_advisor_response
from backend.models.safety import LocalitySafetyResponse
from backend.services.crime_data import get_locality_safety_data

logger = logging.getLogger("nivas.api.livability")

router = APIRouter(prefix="/api/livability", tags=["livability"])


async def retrieve_livability_data(
    latitude: float,
    longitude: float,
    address: Optional[str] = None,
    radius: int = 1200,
) -> LivabilityLocationDataResponse:
    """
    Fetch verifiable, structured location and environmental data for the given coordinates.
    Reuses existing real OpenStreetMap Overpass and Air Quality services.
    Never fabricates amenities, air quality, or hazard scores.
    """
    if latitude < -90.0 or latitude > 90.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid latitude {latitude}. Must be between -90.0 and 90.0.",
        )
    if longitude < -180.0 or longitude > 180.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid longitude {longitude}. Must be between -180.0 and 180.0.",
        )
    if radius < 0 or radius > 10000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid radius {radius}. Must be between 0 and 10000 meters.",
        )

    locality = address.split(",")[0].strip() if address else None

    # When radius is 0, pinpoint-only exploration: return empty infrastructure immediately without querying Overpass
    if radius == 0:
        infra_result = InfrastructureSummary(
            schools_count=0,
            hospitals_count=0,
            clinics_count=0,
            pharmacies_count=0,
            police_stations_count=0,
            fire_stations_count=0,
            public_transport_count=0,
            railway_stations_count=0,
            major_roads_count=0,
            nearby_places=[],
            facilities=[],
        )
        aqi_result = await fetch_real_aqi_with_status(latitude, longitude)
    else:
        # Fetch infrastructure and air quality concurrently
        infra_task = fetch_overpass_infrastructure(latitude, longitude, radius=radius)
        aqi_task = fetch_real_aqi_with_status(latitude, longitude)

        infra_result, aqi_result = await asyncio.gather(
            infra_task, aqi_task, return_exceptions=True
        )

    # 1. Process Infrastructure Summary
    if isinstance(infra_result, Exception):
        logger.warning("Overpass query failed with exception: %s", infra_result)
        infra_data = LivabilityInfrastructureData(
            status="fetch_failed",
            error_message="Overpass API query failed due to network or service error",
        )
    elif infra_result is None:
        infra_data = LivabilityInfrastructureData(
            status="fetch_failed",
            error_message="OpenStreetMap Overpass API mirrors were unreachable or timed out",
        )
    else:
        total = (
            infra_result.schools_count
            + infra_result.hospitals_count
            + infra_result.clinics_count
            + infra_result.pharmacies_count
            + infra_result.police_stations_count
            + infra_result.fire_stations_count
            + infra_result.public_transport_count
            + infra_result.railway_stations_count
            + infra_result.major_roads_count
        )
        raw_facilities = getattr(infra_result, "facilities", []) or []
        parsed_facilities = []
        for fac in raw_facilities:
            if isinstance(fac, dict):
                parsed_facilities.append(LivabilityFacilityItem(**fac))
            elif isinstance(fac, LivabilityFacilityItem):
                parsed_facilities.append(fac)

        infra_status = "empty" if total == 0 and not infra_result.nearby_places else "active"
        infra_data = LivabilityInfrastructureData(
            status=infra_status,
            source="OpenStreetMap Overpass API",
            schools_count=infra_result.schools_count,
            hospitals_count=infra_result.hospitals_count,
            clinics_count=infra_result.clinics_count,
            pharmacies_count=infra_result.pharmacies_count,
            police_stations_count=infra_result.police_stations_count,
            fire_stations_count=infra_result.fire_stations_count,
            public_transport_count=infra_result.public_transport_count,
            railway_stations_count=infra_result.railway_stations_count,
            major_roads_count=infra_result.major_roads_count,
            nearby_places=infra_result.nearby_places or [],
            facilities=parsed_facilities,
            total_facilities=total,
            search_radius_meters=radius,
            railway_search_radius_meters=min(10000, radius + 800) if radius > 0 else 0,
            error_message=None,
        )

    # 2. Process Air Quality
    if isinstance(aqi_result, Exception):
        logger.warning("AQI fetch failed with exception: %s", aqi_result)
        aqi_data = LivabilityAirQualityData(
            status="fetch_failed",
            error_message="Air quality telemetry fetch encountered an unexpected error",
        )
    else:
        aqi_obj, aqi_status, aqi_err = aqi_result
        if aqi_obj is not None:
            aqi_data = LivabilityAirQualityData(
                status=aqi_status,
                source=aqi_obj.source,
                scale=aqi_obj.scale,
                aqi_value=aqi_obj.aqi_value,
                category=aqi_obj.category,
                station_name=aqi_obj.station_name,
                components=aqi_obj.components,
                environmental_score=aqi_obj.environmental_score,
                error_message=None,
            )
        else:
            aqi_data = LivabilityAirQualityData(
                status=aqi_status,
                error_message=aqi_err,
            )

    # 3. Environmental Hazards (unconfigured telemetry)
    hazard_data = LivabilityHazardData(
        status="data_not_configured",
        source=None,
        message="Real-time environmental hazard sensor network not configured for this region",
    )

    return LivabilityLocationDataResponse(
        latitude=latitude,
        longitude=longitude,
        address=address,
        locality=locality,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        infrastructure=infra_data,
        air_quality=aqi_data,
        environmental_hazards=hazard_data,
    )


@router.get("/location-data", response_model=LivabilityLocationDataResponse)
async def get_livability_location_data(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="Latitude coordinate"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="Longitude coordinate"),
    address: Optional[str] = Query(None, description="Optional address or locality name"),
    radius: int = Query(1200, ge=0, le=10000, description="Search radius in meters (0m to 10000m)"),
):
    """Retrieve structured civic infrastructure, air quality, and environmental data for Livability workspace."""
    return await retrieve_livability_data(
        latitude=latitude, longitude=longitude, address=address, radius=radius
    )


@router.post("/location-data", response_model=LivabilityLocationDataResponse)
async def post_livability_location_data(request: LivabilityDataRequest):
    """POST endpoint alternative for retrieving Livability location data."""
    radius_val = request.radius if request.radius is not None else 1200
    return await retrieve_livability_data(
        latitude=request.latitude, longitude=request.longitude, address=request.address, radius=radius_val
    )


@router.post("/chat", response_model=LivabilityChatResponse)
async def post_livability_chat(request: LivabilityChatRequest):
    """
    Grounded Neighborhood AI Advisor chat endpoint.
    Answers inquiries using real location telemetry, identifying sources and acknowledging missing data.
    Reports honestly if no AI provider is configured without simulating fake model generation.
    """
    try:
        return await generate_advisor_response(request)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Unexpected error in livability chat: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to generate neighborhood advisor response at this time. Telemetry and map remain active.",
        )


@router.get("/safety-data", response_model=LocalitySafetyResponse)
async def get_safety_data(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="Latitude coordinate"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="Longitude coordinate"),
    address: Optional[str] = Query(None, description="Optional address or locality name"),
    radius: int = Query(1200, ge=0, le=10000, description="Radius in meters to filter real police stations"),
):
    """
    Retrieve official police district historical crime statistics, rates per lakh,
    multi-year trends, and real verified OpenStreetMap police stations within radius.
    Never fabricates street-level incident coordinates or artificial composite ratings.
    """
    return await get_locality_safety_data(
        latitude=latitude, longitude=longitude, address=address, radius=radius
    )
