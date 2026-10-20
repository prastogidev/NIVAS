import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Query, HTTPException, status

from backend.models.disaster import (
    DisasterLocationResponse,
    DisasterCompareRequest,
    DisasterCompareResponse,
    DisasterLayersRegistryResponse,
)
from backend.services.disaster import (
    get_disaster_hazards,
    compare_disaster_hazards,
    get_hazard_layers_registry,
    get_layer_geometry,
)

logger = logging.getLogger("nivas.api.disaster")

router = APIRouter(prefix="/api/disaster", tags=["disaster"])


@router.get("/layers", response_model=DisasterLayersRegistryResponse)
async def get_hazard_layers():
    """
    Retrieve authoritative registry of all supported India-wide and regional disaster hazard layers.
    Includes layer metadata, statutory sources, visual styles, coverage scopes, and limitations.
    """
    try:
        return get_hazard_layers_registry()
    except Exception as exc:
        logger.error("Error retrieving hazard layers registry: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve hazard layers registry at this time.",
        )


@router.get("/layer-geometry")
async def get_hazard_layer_geometry(
    layer_id: str = Query(..., description="Stable layer ID from registry (e.g. 'seismic_zones')")
):
    """
    Retrieve GeoJSON spatial geometry (Feature or FeatureCollection) for a requested hazard layer.
    """
    geometry = get_layer_geometry(layer_id)
    if geometry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hazard layer '{layer_id}' not found in registry.",
        )
    return geometry


@router.get("/hazard-data", response_model=DisasterLocationResponse)
async def get_disaster_hazard_data(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="Latitude coordinate"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="Longitude coordinate"),
    address: Optional[str] = Query(None, description="Optional address or locality name"),
):
    """
    Retrieve grounded disaster, geological, and climate hazard evidence for given coordinates across India.
    Grounded in BIS IS 1893:2016 seismic zoning, CWC major river basins, NDMA coastal cyclone exposure,
    GSI landslide susceptibility, and surveyed municipal drainage datasets.
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
    Compare disaster hazard exposures between Location A and Location B side-by-side across India.
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
