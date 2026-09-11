import unittest
from unittest.mock import patch

from backend.core.config import settings
from backend.services.air_quality import fetch_real_aqi


class _FakeResponse:
    status_code = 200

    def json(self):
        # Shanghai is deliberately far from the Delhi property coordinates.
        return {
            "status": "ok",
            "data": {
                "aqi": 42,
                "city": {"name": "Shanghai", "geo": [31.2304, 121.4737]},
            },
        }


class _FakeAsyncClient:
    requests = []

    def __init__(self, *, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def get(self, url, *, params):
        type(self).requests.append((url, params))
        return _FakeResponse()


class AQICNGeographicRelevanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_never_requests_aqicn_with_the_demo_token(self):
        _FakeAsyncClient.requests = []

        with (
            patch.object(settings, "AQICN_TOKEN", "demo"),
            patch("backend.services.air_quality.httpx.AsyncClient", _FakeAsyncClient),
        ):
            result = await fetch_real_aqi(latitude=28.6139, longitude=77.2090)

        self.assertIsNone(result)
        self.assertEqual(_FakeAsyncClient.requests, [])

    async def test_rejects_a_station_more_than_50_km_from_the_property(self):
        _FakeAsyncClient.requests = []

        with (
            patch.object(settings, "AQICN_TOKEN", "configured-real-token"),
            patch("backend.services.air_quality.httpx.AsyncClient", _FakeAsyncClient),
        ):
            result = await fetch_real_aqi(latitude=28.6139, longitude=77.2090)

        self.assertIsNone(result)
        self.assertEqual(len(_FakeAsyncClient.requests), 1)
        self.assertEqual(
            _FakeAsyncClient.requests[0][1],
            {"token": "configured-real-token"},
        )
