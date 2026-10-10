import logging
import math
from typing import Optional, Tuple, Dict, Any
import httpx
from backend.core.config import settings
from backend.models.score import AQIResult

logger = logging.getLogger("nivas.services.air_quality")

# Maximum acceptable distance (in kilometers) between property coordinates and AQI monitoring station (for AQICN)
MAX_AQI_STATION_DISTANCE_KM: float = 50.0

# OpenWeather Air Pollution API Scale (1 - 5)
OPENWEATHER_AQI_CATEGORIES: Dict[int, str] = {
    1: "Good",
    2: "Fair",
    3: "Moderate",
    4: "Poor",
    5: "Very Poor",
}

# Standardized 0-100 environmental score mapping for OpenWeather 1-5 scale
OPENWEATHER_ENV_SCORES: Dict[int, float] = {
    1: 95.0,  # Good
    2: 80.0,  # Fair
    3: 60.0,  # Moderate
    4: 40.0,  # Poor
    5: 20.0,  # Very Poor
}


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
    """CPCB / US EPA AQI category for continuous scales (0 - 500+)."""
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
    Converts a continuous AQI value (0 to 500+) into a standardized 0-100 Environmental Health Score.
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


async def fetch_openweather_air_pollution(
    latitude: float, longitude: float, timeout: float = 5.0
) -> Tuple[Optional[AQIResult], str, Optional[str]]:
    """
    Fetch current air pollution data from OpenWeather Air Pollution API:
    https://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API key}

    Preserves OpenWeather native AQI scale (1 - 5):
      1 = Good, 2 = Fair, 3 = Moderate, 4 = Poor, 5 = Very Poor
    Extracts pollutant components: pm2_5, pm10, no2, o3, so2, co, etc. (µg/m³).

    Returns:
        (aqi_result, status, error_message)
        where status is one of:
        - 'active': valid pollution data returned
        - 'provider_not_configured': OPENWEATHER_API_KEY missing or empty
        - 'fetch_failed': invalid key, rate limit, HTTP error, timeout, network error
        - 'data_unavailable': HTTP 200 but list is empty or main.aqi missing
    """
    api_key = getattr(settings, "OPENWEATHER_API_KEY", None)
    if not api_key or not api_key.strip():
        return None, "provider_not_configured", "OPENWEATHER_API_KEY is not configured in backend environment."

    clean_key = api_key.strip()

    try:
        url = "https://api.openweathermap.org/data/2.5/air_pollution"
        params = {
            "lat": float(latitude),
            "lon": float(longitude),
            "appid": clean_key,
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, params=params)

            if resp.status_code == 401:
                msg = "OpenWeather API key is invalid or unauthorized."
                logger.warning(msg)
                return None, "fetch_failed", msg
            elif resp.status_code == 429:
                msg = "OpenWeather API rate limit exceeded."
                logger.warning(msg)
                return None, "fetch_failed", msg
            elif resp.status_code != 200:
                msg = f"OpenWeather API returned HTTP status {resp.status_code}."
                logger.warning(msg)
                return None, "fetch_failed", msg

            data = resp.json()
            items = data.get("list")
            if not items or not isinstance(items, list) or len(items) == 0:
                msg = "OpenWeather API returned empty air pollution list."
                logger.warning(msg)
                return None, "data_unavailable", msg

            entry = items[0]
            main_block = entry.get("main", {})
            aqi_int = main_block.get("aqi")

            if aqi_int is None:
                msg = "OpenWeather Air Pollution API response missing main.aqi index."
                logger.warning(msg)
                return None, "data_unavailable", msg

            try:
                aqi_val = float(aqi_int)
            except (ValueError, TypeError):
                msg = f"Invalid AQI value from OpenWeather: {aqi_int}"
                logger.warning(msg)
                return None, "fetch_failed", msg

            # Category and Environmental score based on 1-5 scale
            aqi_key = int(round(aqi_val))
            category = OPENWEATHER_AQI_CATEGORIES.get(aqi_key, "Moderate")
            env_score = OPENWEATHER_ENV_SCORES.get(aqi_key, 60.0)

            # Components: pm2_5, pm10, no2, o3, so2, co, etc.
            raw_comps = entry.get("components", {})
            components: Dict[str, float] = {}
            for comp_name, comp_val in raw_comps.items():
                try:
                    components[comp_name] = float(comp_val)
                except (ValueError, TypeError):
                    continue

            logger.info(
                "OpenWeather Air Pollution fetched for (%.4f, %.4f): AQI=%d (%s), PM2.5=%.1f µg/m³, PM10=%.1f µg/m³",
                latitude, longitude, aqi_key, category,
                components.get("pm2_5", 0.0), components.get("pm10", 0.0)
            )

            res = AQIResult(
                aqi_value=aqi_val,
                category=category,
                station_name=f"OpenWeather Grid ({latitude:.3f}°N, {longitude:.3f}°E)",
                source="OpenWeather Air Pollution API",
                scale="1-5 (OpenWeather)",
                components=components,
                environmental_score=env_score,
                fetch_status="active",
            )
            return res, "active", None

    except httpx.TimeoutException:
        msg = f"OpenWeather API request timed out for coordinates ({latitude:.4f}, {longitude:.4f})"
        logger.warning(msg)
        return None, "fetch_failed", msg
    except Exception as err:
        msg = f"Error fetching air pollution data from OpenWeather: {str(err)}"
        logger.error(msg)
        return None, "fetch_failed", msg


async def fetch_aqicn_with_status(
    latitude: float, longitude: float, timeout: float = 5.0
) -> Tuple[Optional[AQIResult], str, Optional[str]]:
    """
    Fetch live Air Quality Index (AQI) from official AQICN API (https://api.waqi.info/)
    using geocoded latitude and longitude coordinates.
    """
    token = getattr(settings, "AQICN_TOKEN", None)

    if not token or not token.strip() or token.strip().lower() == "demo":
        msg = "AQICN API token is not configured in backend environment."
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

            # Validate geographical proximity
            if not station_geo or not isinstance(station_geo, (list, tuple)) or len(station_geo) < 2:
                msg = f"AQICN station '{station_name}' missing geographic coordinates."
                return None, "data_unavailable", msg

            try:
                st_lat = float(station_geo[0])
                st_lon = float(station_geo[1])
            except (ValueError, TypeError):
                msg = f"AQICN station '{station_name}' has invalid coordinates {station_geo}."
                return None, "data_unavailable", msg

            distance_km = haversine_distance_km(latitude, longitude, st_lat, st_lon)
            if distance_km > MAX_AQI_STATION_DISTANCE_KM:
                msg = (
                    f"Nearest station '{station_name}' at ({st_lat:.4f}, {st_lon:.4f}) is {distance_km:.1f} km away, "
                    f"exceeding max radius {MAX_AQI_STATION_DISTANCE_KM:.1f} km."
                )
                return None, "data_unavailable", msg

            if station_name and any(unrelated in station_name.lower() for unrelated in ["shanghai", "beijing"]):
                msg = f"AQICN returned known unrelated fallback station '{station_name}'."
                return None, "data_unavailable", msg

            aqi_raw = data.get("aqi")
            if aqi_raw is None or aqi_raw == "-":
                msg = f"AQI value missing or unavailable for station '{station_name}'."
                return None, "data_unavailable", msg

            try:
                aqi_value = float(aqi_raw)
            except (ValueError, TypeError):
                msg = f"Invalid AQI value format from AQICN: {aqi_raw}"
                return None, "fetch_failed", msg

            category = get_aqi_category(aqi_value)
            env_score = calculate_environmental_score(aqi_value)

            # Components if provided by AQICN iaqi dict
            iaqi = data.get("iaqi", {})
            components = {}
            for k, v in iaqi.items():
                if isinstance(v, dict) and "v" in v:
                    try:
                        components[k] = float(v["v"])
                    except (ValueError, TypeError):
                        pass

            res = AQIResult(
                aqi_value=aqi_value,
                category=category,
                station_name=station_name,
                source="AQICN WAQI API",
                scale="0-500 (CPCB / US EPA)",
                components=components if components else None,
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


async def fetch_real_aqi_with_status(
    latitude: float, longitude: float, timeout: float = 5.0
) -> Tuple[Optional[AQIResult], str, Optional[str]]:
    """
    Primary Air Quality fetch pipeline:
    1. Try OpenWeather Air Pollution API first if OPENWEATHER_API_KEY is configured.
    2. Fallback to AQICN WAQI API if AQICN_TOKEN is configured.
    3. Return clear status ('provider_not_configured', 'fetch_failed', 'data_unavailable') if none succeed.
    """
    # 1. OpenWeather Air Pollution API
    if settings.OPENWEATHER_API_KEY:
        ow_res, ow_status, ow_err = await fetch_openweather_air_pollution(
            latitude=latitude, longitude=longitude, timeout=timeout
        )
        if ow_status == "active":
            return ow_res, ow_status, None
        # If OpenWeather failed or was unavailable, and AQICN is configured, fallback to AQICN
        if not settings.AQICN_TOKEN:
            return None, ow_status, ow_err

    # 2. AQICN fallback (or primary if only AQICN is set)
    if settings.AQICN_TOKEN:
        aqicn_res, aqicn_status, aqicn_err = await fetch_aqicn_with_status(
            latitude=latitude, longitude=longitude, timeout=timeout
        )
        if aqicn_status == "active":
            return aqicn_res, aqicn_status, None
        return None, aqicn_status, aqicn_err

    # 3. Neither provider configured
    return (
        None,
        "provider_not_configured",
        "Air quality API key (OPENWEATHER_API_KEY or AQICN_TOKEN) is not configured in backend environment.",
    )


async def fetch_real_aqi(
    latitude: float, longitude: float, timeout: float = 5.0
) -> Optional[AQIResult]:
    """Backward-compatible helper returning Optional[AQIResult]."""
    result, _, _ = await fetch_real_aqi_with_status(latitude, longitude, timeout=timeout)
    return result
