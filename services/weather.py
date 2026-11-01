"""
NIVAS Weather Intelligence Service.
Fetches current local meteorological conditions (temperature, humidity, wind, description)
using OpenWeather Current Weather Data API when OPENWEATHER_API_KEY is configured.
Includes graceful fallback and explicit provenance disclosures.
Meteorological conditions are strictly separated from statutory disaster/hazard risk datasets.
"""

import logging
from typing import Optional, Dict, Any, Tuple
import httpx
from pydantic import Field
from backend.core.config import settings
from backend.models.score import BaseOptimizedModel

logger = logging.getLogger("nivas.services.weather")


class CurrentWeatherResult(BaseOptimizedModel):
    status: str = Field(..., description="Status: 'active', 'provider_not_configured', 'fetch_failed', 'data_unavailable'")
    source: str = Field("OpenWeather Current Weather API", description="Underlying provider")
    temperature_c: Optional[float] = Field(None, description="Current ambient temperature in Celsius")
    feels_like_c: Optional[float] = Field(None, description="Apparent temperature in Celsius")
    humidity_percent: Optional[int] = Field(None, description="Relative humidity percentage")
    pressure_hpa: Optional[int] = Field(None, description="Atmospheric pressure in hPa")
    wind_speed_mps: Optional[float] = Field(None, description="Wind speed in meters per second")
    wind_direction_deg: Optional[int] = Field(None, description="Wind direction in meteorological degrees")
    condition: Optional[str] = Field(None, description="Primary weather condition (e.g. Clear, Clouds, Haze)")
    description: Optional[str] = Field(None, description="Detailed condition (e.g. scattered clouds, light rain)")
    icon_code: Optional[str] = Field(None, description="Weather icon code")
    location_name: Optional[str] = Field(None, description="Station or municipality name reported by provider")
    provenance_note: str = Field(
        "Real-time meteorological observation. This represents instantaneous ambient weather, "
        "strictly distinct from statutory disaster risk zoning (BIS Seismic, CWC Flood, NDMA Cyclone).",
        description="Factual scope and non-hazard boundary disclosure"
    )
    error_message: Optional[str] = None


async def fetch_current_weather(
    latitude: float, longitude: float, timeout: float = 5.0
) -> Tuple[Optional[CurrentWeatherResult], str, Optional[str]]:
    """
    Fetch live weather for coordinates from OpenWeather API:
    https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric

    Returns (CurrentWeatherResult, status, error_message).
    """
    api_key = getattr(settings, "OPENWEATHER_API_KEY", None)
    if not api_key or not api_key.strip():
        return (
            CurrentWeatherResult(
                status="provider_not_configured",
                source="OpenWeather Current Weather API",
                error_message="OPENWEATHER_API_KEY is not configured in backend environment."
            ),
            "provider_not_configured",
            "OPENWEATHER_API_KEY is not configured in backend environment."
        )

    clean_key = api_key.strip()
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "lat": float(latitude),
            "lon": float(longitude),
            "appid": clean_key,
            "units": "metric",
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, params=params)

            if resp.status_code == 401:
                msg = "OpenWeather API key is invalid or not yet activated by the provider."
                logger.warning(msg)
                return (
                    CurrentWeatherResult(
                        status="fetch_failed",
                        source="OpenWeather Current Weather API",
                        error_message=msg,
                    ),
                    "fetch_failed",
                    msg,
                )
            elif resp.status_code == 429:
                msg = "OpenWeather API rate limit exceeded."
                logger.warning(msg)
                return (
                    CurrentWeatherResult(
                        status="fetch_failed",
                        source="OpenWeather Current Weather API",
                        error_message=msg,
                    ),
                    "fetch_failed",
                    msg,
                )
            elif resp.status_code != 200:
                msg = f"OpenWeather API returned HTTP status {resp.status_code}."
                logger.warning(msg)
                return (
                    CurrentWeatherResult(
                        status="fetch_failed",
                        source="OpenWeather Current Weather API",
                        error_message=msg,
                    ),
                    "fetch_failed",
                    msg,
                )

            data = resp.json()
            main = data.get("main", {})
            wind = data.get("wind", {})
            weather_list = data.get("weather", [])
            primary_weather = weather_list[0] if weather_list else {}

            temp = main.get("temp")
            feels_like = main.get("feels_like")
            humidity = main.get("humidity")
            pressure = main.get("pressure")
            wind_speed = wind.get("speed")
            wind_deg = wind.get("deg")
            condition = primary_weather.get("main")
            description = primary_weather.get("description")
            icon = primary_weather.get("icon")
            loc_name = data.get("name")

            result = CurrentWeatherResult(
                status="active",
                source="OpenWeather Current Weather API",
                temperature_c=float(temp) if temp is not None else None,
                feels_like_c=float(feels_like) if feels_like is not None else None,
                humidity_percent=int(humidity) if humidity is not None else None,
                pressure_hpa=int(pressure) if pressure is not None else None,
                wind_speed_mps=float(wind_speed) if wind_speed is not None else None,
                wind_direction_deg=int(wind_deg) if wind_deg is not None else None,
                condition=condition,
                description=description,
                icon_code=icon,
                location_name=loc_name,
            )
            return result, "active", None

    except httpx.TimeoutException:
        msg = f"OpenWeather API request timed out for coordinates ({latitude:.4f}, {longitude:.4f})"
        logger.warning(msg)
        return (
            CurrentWeatherResult(status="fetch_failed", source="OpenWeather Current Weather API", error_message=msg),
            "fetch_failed",
            msg,
        )
    except Exception as err:
        msg = f"Error fetching current weather from OpenWeather: {str(err)}"
        logger.error(msg)
        return (
            CurrentWeatherResult(status="fetch_failed", source="OpenWeather Current Weather API", error_message=msg),
            "fetch_failed",
            msg,
        )
