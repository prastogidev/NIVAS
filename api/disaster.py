import logging
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, status

from backend.models.disaster import (
    DisasterLocationResponse,
    DisasterCompareRequest,
    DisasterCompareResponse,
)
from backend.services.disaster import (
    get_disaster_hazards,
    compare_disaster_hazards,
)

logger = logging.getLogger("nivas.api.disaster")

router = APIRouter(prefix="/api/disaster", tags=["disaster"])


@router.get("/hazard-data", response_model=DisasterLocationResponse)
async def get_disaster_hazard_data(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="Latitude coordinate"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="Longitude coordinate"),
    address: Optional[str] = Query(None, description="Optional address or locality name"),
):
    """
    Retrieve grounded disaster, geological, and climate hazard evidence for given coordinates.
    Grounded in BIS Seismic Zone IV, CWC Yamuna Floodplain, and Delhi PWD drainage reports.
    """
    try:
        return await get_disaster_hazards(latitude=latitude, longitude=longitude, address=address)
    except Exception as exc:
        logger.error("Error retrieving disaster hazard data: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve disaster hazard telemetry at this time.",
        )


@router.post("/compare", response_model=DisasterCompareResponse)
async def compare_disaster_locations(request: DisasterCompareRequest):
    """
    Compare disaster hazard exposures between Location A and Location B side-by-side.
    Provides explainable evidence-by-evidence contrasts without a fake composite score.
    """
    try:
        return await compare_disaster_hazards(request)
    except Exception as exc:
        logger.error("Error comparing disaster hazard data: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to execute disaster relocation comparison at this time.",
        )
