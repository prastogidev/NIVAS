import pytest
import unittest
from unittest.mock import patch
from backend.core.config import settings
from backend.services.weather import fetch_current_weather, CurrentWeatherResult


class FakeWeatherResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self):
        return self._json_data


class FakeWeatherClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def get(self, url, *, params):
        if params.get("appid") == "valid_key":
            return FakeWeatherResponse(
                200,
                {
                    "name": "Dwarka",
                    "main": {
                        "temp": 28.5,
                        "feels_like": 30.1,
                        "humidity": 65,
                        "pressure": 1012,
                    },
                    "wind": {"speed": 3.6, "deg": 120},
                    "weather": [
                        {
                            "main": "Haze",
                            "description": "haze",
                            "icon": "50d",
                        }
                    ],
                },
            )
        elif params.get("appid") == "invalid_key":
            return FakeWeatherResponse(401, {"cod": 401, "message": "Invalid API key."})
        elif params.get("appid") == "rate_limited":
            return FakeWeatherResponse(429, {"cod": 429, "message": "Rate limit exceeded."})
        return FakeWeatherResponse(500, {})


@pytest.mark.asyncio
async def test_fetch_current_weather_missing_key():
    with patch.object(settings, "OPENWEATHER_API_KEY", None):
        result, status, err = await fetch_current_weather(28.59, 77.04)
        assert status == "provider_not_configured"
        assert result.status == "provider_not_configured"
        assert "OPENWEATHER_API_KEY" in err


@pytest.mark.asyncio
async def test_fetch_current_weather_valid_key():
    with (
        patch.object(settings, "OPENWEATHER_API_KEY", "valid_key"),
        patch("backend.services.weather.httpx.AsyncClient", FakeWeatherClient),
    ):
        result, status, err = await fetch_current_weather(28.59, 77.04)
        assert status == "active"
        assert err is None
        assert result.temperature_c == 28.5
        assert result.feels_like_c == 30.1
        assert result.humidity_percent == 65
        assert result.condition == "Haze"
        assert result.location_name == "Dwarka"
        assert "statutory disaster risk zoning" in result.provenance_note


@pytest.mark.asyncio
async def test_fetch_current_weather_invalid_key_graceful():
    with (
        patch.object(settings, "OPENWEATHER_API_KEY", "invalid_key"),
        patch("backend.services.weather.httpx.AsyncClient", FakeWeatherClient),
    ):
        result, status, err = await fetch_current_weather(28.59, 77.04)
        assert status == "fetch_failed"
        assert result.status == "fetch_failed"
        assert "invalid" in err.lower()
