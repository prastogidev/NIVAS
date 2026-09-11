import logging
import math
from typing import Optional, Tuple
import httpx
from backend.core.config import settings
from backend.models.score import AQIResult

logger = logging.getLogger("nivas.services.air_quality")

# Maximum acceptable distance (in kilometers) between property coordinates and AQI monitoring station
MAX_AQI_STATION_DISTANCE_KM: float = 50.0


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on the Earth in kilometers."""
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def get_aqi_category(aqi: float) -> str:
    if aqi <= 50:
        return "Good"
    elif aqi <= 100:
        return "Moderate"
    elif aqi <= 150:
        return "Unhealthy for Sensitive Groups"
    elif aqi <= 200:
        return "Unhealthy"
    elif aqi <= 300:
        return "Very Unhealthy"
    else:
        return "Hazardous"


def calculate_environmental_score(aqi_value: float) -> float:
    """
    Converts an un-modified AQI value (0 to 500+) into a standardized 0-100 Environmental Health Score.

    Formula & Piecewise Linear Mapping (100 = Pristine Air Quality, 0 = Extremely Severe/Hazardous Air):
    - AQI [0 - 50] (Good): 100.0 down to 90.0
        Formula: 100.0 - (aqi / 50.0) * 10.0
    - AQI [50 - 100] (Moderate): 90.0 down to 75.0
        Formula: 90.0 - ((aqi - 50.0) / 50.0) * 15.0
    - AQI [100 - 150] (Unhealthy for Sensitive Groups): 75.0 down to 55.0
        Formula: 75.0 - ((aqi - 100.0) / 50.0) * 20.0
    - AQI [150 - 200] (Unhealthy): 55.0 down to 35.0
        Formula: 55.0 - ((aqi - 150.0) / 50.0) * 20.0
    - AQI [200 - 300] (Very Unhealthy): 35.0 down to 15.0
        Formula: 35.0 - ((aqi - 200.0) / 100.0) * 20.0
    - AQI [> 300] (Hazardous): 15.0 down to 0.0
        Formula: max(0.0, 15.0 - ((aqi - 300.0) / 200.0) * 15.0)

    Note: The original AQI value returned by the API remains completely untouched.
    """
    if aqi_value <= 0:
        return 100.0
    elif aqi_value <= 50.0:
        score = 100.0 - (aqi_value / 50.0) * 10.0
    elif aqi_value <= 100.0:
        score = 90.0 - ((aqi_value - 50.0) / 50.0) * 15.0
    elif aqi_value <= 150.0:
        score = 75.0 - ((aqi_value - 100.0) / 50.0) * 20.0
    elif aqi_value <= 200.0:
        score = 55.0 - ((aqi_value - 150.0) / 50.0) * 20.0
    elif aqi_value <= 300.0:
        score = 35.0 - ((aqi_value - 200.0) / 100.0) * 20.0
    else:
        score = max(0.0, 15.0 - ((aqi_value - 300.0) / 200.0) * 15.0)

    return round(score, 2)


async def fetch_real_aqi_with_status(
    latitude: float, longitude: float, timeout: float = 5.0
) -> Tuple[Optional[AQIResult], str, Optional[str]]:
    """
    Fetch live Air Quality Index (AQI) and station info from official AQICN API (https://api.waqi.info/)
    using geocoded latitude and longitude coordinates.

    Returns:
        (aqi_result, status, error_message)
        where status is one of:
        - 'active': verified monitoring station <= 50km, valid AQI data returned.
        - 'provider_not_configured': AQICN token missing or 'demo'.
        - 'fetch_failed': HTTP timeout, network error, or non-200/error response.
        - 'data_unavailable': API call succeeded, but no station within 50km radius or AQI missing.
    """
    token = getattr(settings, "AQICN_TOKEN", None)

    if not token or not token.strip() or token.strip().lower() == "demo":
        msg = "AQICN API token is not configured in backend environment."
        logger.info("AQICN token not configured or set to 'demo'. Returning status 'provider_not_configured'.")
        return None, "provider_not_configured", msg

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            url = f"https://api.waqi.info/feed/geo:{latitude};{longitude}/"
            params = {"token": token.strip()}
            resp = await client.get(url, params=params)

            if resp.status_code != 200:
                msg = f"AQICN API returned HTTP status {resp.status_code}"
                logger.warning(msg)
                return None, "fetch_failed", msg

            res_json = resp.json()
            if res_json.get("status") != "ok":
                msg = f"AQICN API error: {res_json.get('data', 'Unknown API error')}"
                logger.warning(msg)
                return None, "fetch_failed", msg

            data = res_json.get("data", {})
            station_info = data.get("city", {})
            station_name = station_info.get("name")
            station_geo = station_info.get("geo")

            # Validate geographical proximity of returned monitoring station
            if not station_geo or not isinstance(station_geo, (list, tuple)) or len(station_geo) < 2:
                msg = f"AQICN station '{station_name}' missing geographic coordinates to verify proximity."
                logger.warning(
                    "AQICN station '%s' missing geographic coordinates. Cannot verify proximity to (%.4f, %.4f).",
                    station_name, latitude, longitude,
                )
                return None, "data_unavailable", msg

            try:
                st_lat = float(station_geo[0])
                st_lon = float(station_geo[1])
            except (ValueError, TypeError):
                msg = f"AQICN station '{station_name}' has invalid coordinates {station_geo}."
                logger.warning("AQICN station '%s' has invalid coordinates %s.", station_name, station_geo)
                return None, "data_unavailable", msg

            distance_km = haversine_distance_km(latitude, longitude, st_lat, st_lon)
            if distance_km > MAX_AQI_STATION_DISTANCE_KM:
                msg = (
                    f"Nearest station '{station_name}' at ({st_lat:.4f}, {st_lon:.4f}) is {distance_km:.1f} km away, "
                    f"exceeding max radius {MAX_AQI_STATION_DISTANCE_KM:.1f} km."
                )
                logger.warning(
                    "AQICN station '%s' at (%.4f, %.4f) is %.1f km away from property at (%.4f, %.4f), exceeding max radius %.1f km.",
                    station_name, st_lat, st_lon, distance_km, latitude, longitude, MAX_AQI_STATION_DISTANCE_KM,
                )
                return None, "data_unavailable", msg

            # Explicit check against known unrelated fallback keywords
            if station_name and any(unrelated in station_name.lower() for unrelated in ["shanghai", "beijing"]):
                msg = f"AQICN returned known unrelated fallback station '{station_name}'."
                logger.warning("AQICN returned known unrelated fallback station '%s'.", station_name)
                return None, "data_unavailable", msg

            aqi_raw = data.get("aqi")
            if aqi_raw is None or aqi_raw == "-":
                msg = f"AQI value missing or unavailable for station '{station_name}'."
                logger.info(msg)
                return None, "data_unavailable", msg

            try:
                aqi_value = float(aqi_raw)
            except (ValueError, TypeError):
                msg = f"Invalid AQI value format from AQICN: {aqi_raw}"
                logger.warning(msg)
                return None, "fetch_failed", msg

            category = get_aqi_category(aqi_value)
            env_score = calculate_environmental_score(aqi_value)

            logger.info(
                "AQICN verified nearby station '%s' (%.1f km away at %.4f, %.4f) for (%.4f, %.4f): AQI=%.1f (%s)",
                station_name, distance_km, st_lat, st_lon, latitude, longitude, aqi_value, category,
            )

            res = AQIResult(
                aqi_value=aqi_value,
                category=category,
                station_name=station_name,
                environmental_score=env_score,
                fetch_status="active",
            )
            return res, "active", None

    except httpx.TimeoutException:
        msg = f"AQICN API request timed out for coordinates ({latitude:.4f}, {longitude:.4f})"
        logger.warning(msg)
        return None, "fetch_failed", msg
    except Exception as err:
        msg = f"Error fetching AQI data from AQICN: {str(err)}"
        logger.error(msg)
        return None, "fetch_failed", msg


async def fetch_real_aqi(
    latitude: float, longitude: float, timeout: float = 5.0
) -> Optional[AQIResult]:
    """
    Fetch live Air Quality Index (AQI) and station info from official AQICN API (https://api.waqi.info/)
    using geocoded latitude and longitude coordinates.

    Guarantees:
    - Never uses 'demo' token or fallback stations that return unrelated locations (such as Shanghai).
    - Validates that the returned monitoring station is geographically relevant and within MAX_AQI_STATION_DISTANCE_KM.
    - If no valid nearby station is available, returns None (unavailable/disconnected).
    """
    result, _, _ = await fetch_real_aqi_with_status(latitude, longitude, timeout=timeout)
    return result
