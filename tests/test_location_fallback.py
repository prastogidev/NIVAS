import unittest
from unittest.mock import patch

import httpx

from backend.services.location import fetch_overpass_infrastructure


class _FakeResponse:
    status_code = 200

    def json(self):
        return {
            "elements": [
                {"tags": {"amenity": "hospital", "name": "Fallback Hospital"}},
                {"tags": {"amenity": "school", "name": "Fallback School"}},
                {"tags": {"highway": "primary", "name": "Fallback Road"}},
            ]
        }


class _FakeAsyncClient:
    calls = []
    timeouts = []

    def __init__(self, *, timeout):
        self.timeout = timeout
        type(self).timeouts.append(timeout)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, **kwargs):
        type(self).calls.append(url)
        if url == "https://failed.example/api/interpreter":
            raise httpx.ConnectError("connection refused")
        if url == "https://working.example/api/interpreter":
            return _FakeResponse()
        raise AssertionError(f"Unexpected endpoint: {url}")


class OverpassFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_uses_later_mirror_when_first_connection_fails(self):
        _FakeAsyncClient.calls = []
        _FakeAsyncClient.timeouts = []
        endpoints = [
            "https://failed.example/api/interpreter",
            "https://working.example/api/interpreter",
        ]

        with patch("backend.services.location.httpx.AsyncClient", _FakeAsyncClient):
            infrastructure = await fetch_overpass_infrastructure(
                lat=28.6,
                lon=77.0,
                connect_timeout=0.1,
                read_timeout=0.2,
                endpoints=endpoints,
            )

        self.assertEqual(_FakeAsyncClient.calls, endpoints)
        self.assertIsNotNone(infrastructure)
        self.assertEqual(infrastructure.hospitals_count, 1)
        self.assertEqual(infrastructure.schools_count, 1)
        self.assertEqual(infrastructure.major_roads_count, 1)
        self.assertCountEqual(
            infrastructure.nearby_places,
            ["Fallback Hospital", "Fallback Road", "Fallback School"],
        )
        self.assertEqual(_FakeAsyncClient.timeouts[0].connect, 0.1)
        self.assertEqual(_FakeAsyncClient.timeouts[0].read, 0.2)
