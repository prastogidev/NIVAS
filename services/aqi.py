from typing import Optional, Tuple
from backend.models.score import AQIResult
from backend.services.air_quality import fetch_real_aqi_with_status


async def fetch_aqi(
    address: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> Tuple[Optional[AQIResult], str, Optional[str]]:
    """
    Fetch AQI data for the property address using resolved coordinates.
    Returns:
        (aqi_result, status, error_message)
    """
    if lat is None or lon is None:
        return None, "not_assessed", "Coordinates not resolved for address"

    return await fetch_real_aqi_with_status(latitude=lat, longitude=lon)
