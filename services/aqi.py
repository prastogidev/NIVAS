from typing import Optional
from backend.models.score import AQIResult
from backend.services.air_quality import fetch_real_aqi


async def fetch_aqi(
    address: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> Optional[AQIResult]:
    """
    Fetch AQI data for the property address using resolved coordinates.
    If coordinates are not available, returns None immediately without redundant geocoding hits.
    """
    if lat is None or lon is None:
        return None

    return await fetch_real_aqi(latitude=lat, longitude=lon)
