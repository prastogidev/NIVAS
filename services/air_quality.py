import logging
import math
from typing import Optional
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
    token = getattr(settings, "AQICN_TOKEN", None)

    if not token or not token.strip() or token.strip().lower() == "demo":
        logger.info("AQICN token not configured or set to 'demo' (demo token returns unrelated Shanghai station). Returning None.")
        return None

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            url = f"https://api.waqi.info/feed/geo:{latitude};{longitude}/"
            params = {"token": token.strip()}
            resp = await client.get(url, params=params)

            if resp.status_code != 200:
                logger.warning("AQICN API returned HTTP status %s", resp.status_code)
                return None

            res_json = resp.json()
            if res_json.get("status") != "ok":
                logger.warning("AQICN API returned error response: %s", res_json.get("data"))
                return None

            data = res_json.get("data", {})
            station_info = data.get("city", {})
            station_name = station_info.get("name")
            station_geo = station_info.get("geo")

            # Validate geographical proximity of returned monitoring station
            if not station_geo or not isinstance(station_geo, (list, tuple)) or len(station_geo) < 2:
                logger.warning(
                    "AQICN station '%s' missing geographic coordinates. Cannot verify proximity to (%.4f, %.4f). Returning None.",
                    station_name, latitude, longitude,
                )
                return None

            try:
                st_lat = float(station_geo[0])
                st_lon = float(station_geo[1])
            except (ValueError, TypeError):
                logger.warning("AQICN station '%s' has invalid coordinates %s. Returning None.", station_name, station_geo)
                return None

            distance_km = haversine_distance_km(latitude, longitude, st_lat, st_lon)
            if distance_km > MAX_AQI_STATION_DISTANCE_KM:
                logger.warning(
                    "AQICN station '%s' at (%.4f, %.4f) is %.1f km away from property at (%.4f, %.4f), exceeding max radius %.1f km. Returning None.",
                    station_name, st_lat, st_lon, distance_km, latitude, longitude, MAX_AQI_STATION_DISTANCE_KM,
                )
                return None

            # Explicit check against known unrelated fallback keywords
            if station_name and any(unrelated in station_name.lower() for unrelated in ["shanghai", "beijing"]):
                logger.warning("AQICN returned known unrelated fallback station '%s'. Returning None.", station_name)
                return None

            aqi_raw = data.get("aqi")
            if aqi_raw is None or aqi_raw == "-":
                logger.info("AQI value missing or unavailable for station '%s'", station_name)
                return None

            try:
                aqi_value = float(aqi_raw)
            except (ValueError, TypeError):
                logger.warning("Invalid AQI value format from AQICN: %s", aqi_raw)
                return None

            category = get_aqi_category(aqi_value)
            env_score = calculate_environmental_score(aqi_value)

            logger.info(
                "AQICN verified nearby station '%s' (%.1f km away at %.4f, %.4f) for (%.4f, %.4f): AQI=%.1f (%s)",
                station_name, distance_km, st_lat, st_lon, latitude, longitude, aqi_value, category,
            )

            return AQIResult(
                aqi_value=aqi_value,
                category=category,
                station_name=station_name,
                environmental_score=env_score,
            )

    except httpx.TimeoutException:
        logger.warning("AQICN API request timed out for lat=%s, lon=%s", latitude, longitude)
        return None
    except Exception as err:
        logger.error("Error fetching AQI data from AQICN: %s", str(err))
        return None
