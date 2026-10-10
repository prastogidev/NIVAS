import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import httpx

from backend.services.air_quality import (
    fetch_openweather_air_pollution,
    fetch_real_aqi_with_status,
    OPENWEATHER_AQI_CATEGORIES,
    OPENWEATHER_ENV_SCORES,
)
from backend.core.config import settings


class _MockResponse:
    def __init__(self, status_code: int, json_data: dict):
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        return self._json_data


class TestOpenWeatherAirPollution(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.orig_ow_key = getattr(settings, "OPENWEATHER_API_KEY", None)
        self.orig_aqicn_key = getattr(settings, "AQICN_TOKEN", None)

    def tearDown(self):
        settings.OPENWEATHER_API_KEY = self.orig_ow_key
        settings.AQICN_TOKEN = self.orig_aqicn_key

    async def test_missing_api_key_returns_provider_not_configured(self):
        """When OPENWEATHER_API_KEY is not set, returns 'provider_not_configured'."""
        settings.OPENWEATHER_API_KEY = None
        settings.AQICN_TOKEN = None

        result, status, err = await fetch_real_aqi_with_status(28.59, 77.04)
        self.assertIsNone(result)
        self.assertEqual(status, "provider_not_configured")
        self.assertIn("not configured", err.lower())

    async def test_successful_openweather_response_parsed_correctly(self):
        """Valid response is parsed with 1-5 scale, components, and env score."""
        settings.OPENWEATHER_API_KEY = "test_openweather_key_12345"

        sample_payload = {
            "coord": {"lon": 77.04, "lat": 28.59},
            "list": [
                {
                    "main": {"aqi": 3},
                    "components": {
                        "co": 317.1,
                        "no": 0.0,
                        "no2": 15.6,
                        "o3": 85.8,
                        "so2": 4.1,
                        "pm2_5": 28.4,
                        "pm10": 46.2,
                        "nh3": 2.3,
                    },
                    "dt": 1605182400,
                }
            ],
        }

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=_MockResponse(200, sample_payload))

        with patch("backend.services.air_quality.httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_client

            result, status, err = await fetch_openweather_air_pollution(28.59, 77.04)

        self.assertIsNotNone(result)
        self.assertEqual(status, "active")
        self.assertIsNone(err)

        # Provider's native AQI scale 1-5
        self.assertEqual(result.aqi_value, 3.0)
        self.assertEqual(result.category, "Moderate")
        self.assertEqual(result.scale, "1-5 (OpenWeather)")
        self.assertEqual(result.source, "OpenWeather Air Pollution API")
        self.assertEqual(result.environmental_score, 60.0)

        # Components parsed
        self.assertEqual(result.components["pm2_5"], 28.4)
        self.assertEqual(result.components["pm10"], 46.2)
        self.assertEqual(result.components["no2"], 15.6)
        self.assertEqual(result.components["o3"], 85.8)
        self.assertEqual(result.components["so2"], 4.1)

    async def test_invalid_api_key_401_returns_fetch_failed(self):
        """Unauthorized 401 returns 'fetch_failed' with clear message."""
        settings.OPENWEATHER_API_KEY = "invalid_key_abc"

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=_MockResponse(401, {"cod": 401, "message": "Invalid API key."}))

        with patch("backend.services.air_quality.httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_client

            result, status, err = await fetch_openweather_air_pollution(28.59, 77.04)

        self.assertIsNone(result)
        self.assertEqual(status, "fetch_failed")
        self.assertIn("invalid", err.lower())

    async def test_rate_limit_429_returns_fetch_failed(self):
        """Rate limit 429 returns 'fetch_failed'."""
        settings.OPENWEATHER_API_KEY = "test_key"

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=_MockResponse(429, {"cod": 429, "message": "Rate limit exceeded"}))

        with patch("backend.services.air_quality.httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_client

            result, status, err = await fetch_openweather_air_pollution(28.59, 77.04)

        self.assertIsNone(result)
        self.assertEqual(status, "fetch_failed")
        self.assertIn("rate limit", err.lower())

    async def test_timeout_returns_fetch_failed(self):
        """Timeout exception returns 'fetch_failed' without raising."""
        settings.OPENWEATHER_API_KEY = "test_key"

        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Connection timed out"))

        with patch("backend.services.air_quality.httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_client

            result, status, err = await fetch_openweather_air_pollution(28.59, 77.04)

        self.assertIsNone(result)
        self.assertEqual(status, "fetch_failed")
        self.assertIn("timed out", err.lower())

    async def test_empty_pollution_list_returns_data_unavailable(self):
        """HTTP 200 with empty list returns 'data_unavailable'."""
        settings.OPENWEATHER_API_KEY = "test_key"

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=_MockResponse(200, {"coord": {}, "list": []}))

        with patch("backend.services.air_quality.httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value.__aenter__.return_value = mock_client

            result, status, err = await fetch_openweather_air_pollution(28.59, 77.04)

        self.assertIsNone(result)
        self.assertEqual(status, "data_unavailable")
        self.assertIn("empty", err.lower())

    async def test_native_aqi_scale_categories_and_environmental_scores(self):
        """Verify the 1 to 5 mapping matches OpenWeather specifications."""
        self.assertEqual(OPENWEATHER_AQI_CATEGORIES[1], "Good")
        self.assertEqual(OPENWEATHER_AQI_CATEGORIES[2], "Fair")
        self.assertEqual(OPENWEATHER_AQI_CATEGORIES[3], "Moderate")
        self.assertEqual(OPENWEATHER_AQI_CATEGORIES[4], "Poor")
        self.assertEqual(OPENWEATHER_AQI_CATEGORIES[5], "Very Poor")

        self.assertEqual(OPENWEATHER_ENV_SCORES[1], 95.0)
        self.assertEqual(OPENWEATHER_ENV_SCORES[2], 80.0)
        self.assertEqual(OPENWEATHER_ENV_SCORES[3], 60.0)
        self.assertEqual(OPENWEATHER_ENV_SCORES[4], 40.0)
        self.assertEqual(OPENWEATHER_ENV_SCORES[5], 20.0)
