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

        self.assertCountEqual(_FakeAsyncClient.calls, endpoints)
        self.assertIsNotNone(infrastructure)
        self.assertEqual(infrastructure.hospitals_count, 1)
        self.assertEqual(infrastructure.schools_count, 1)
        self.assertEqual(infrastructure.major_roads_count, 1)
        self.assertCountEqual(
            infrastructure.nearby_places,
            ["Fallback Hospital", "Fallback Road", "Fallback School"],
        )
        self.assertEqual(len(_FakeAsyncClient.timeouts), 1)
        self.assertEqual(_FakeAsyncClient.timeouts[0].connect, 0.1)
        self.assertEqual(_FakeAsyncClient.timeouts[0].read, 0.2)

    @patch("backend.services.location.geocode_address")
    @patch("backend.services.location.fetch_overpass_infrastructure")
    async def test_fetch_location_retries_once_on_first_attempt_failure(self, mock_fetch_infra, mock_geocode):
        from backend.services.geocoding import GeocodeResult
        from backend.models.score import InfrastructureSummary
        from backend.services.location import fetch_location

        mock_geocode.return_value = GeocodeResult(latitude=28.59, longitude=77.04, formatted_address="Dwarka, Delhi")
        # Attempt 1 fails (None), Attempt 2 succeeds
        mock_fetch_infra.side_effect = [
            None,
            InfrastructureSummary(hospitals_count=2, schools_count=3, major_roads_count=2)
        ]

        result = await fetch_location("Dwarka Sector 12, New Delhi")
        self.assertIsNotNone(result)
        self.assertEqual(mock_fetch_infra.call_count, 2)
        self.assertEqual(result.fetch_status, "active")
        self.assertIsNotNone(result.risk_score)
        self.assertEqual(result.latitude, 28.59)

    @patch("backend.services.location.geocode_address")
    @patch("backend.services.location.fetch_overpass_infrastructure")
    async def test_fetch_location_marks_fetch_failed_after_two_failed_attempts(self, mock_fetch_infra, mock_geocode):
        from backend.services.geocoding import GeocodeResult
        from backend.services.location import fetch_location

        mock_geocode.return_value = GeocodeResult(latitude=28.59, longitude=77.04, formatted_address="Dwarka, Delhi")
        # Both attempts fail
        mock_fetch_infra.side_effect = [None, None]

        result = await fetch_location("Dwarka Sector 12, New Delhi")
        self.assertIsNotNone(result)
        self.assertEqual(mock_fetch_infra.call_count, 2)
        self.assertEqual(result.fetch_status, "fetch_failed")
        self.assertIsNone(result.risk_score)
        # Lat/lon are preserved so map can still render!
        self.assertEqual(result.latitude, 28.59)
        self.assertIn("temporarily unavailable", result.error_message)

    @patch("backend.services.location.geocode_address")
    @patch("backend.services.location.fetch_overpass_infrastructure")
    async def test_fetch_location_does_not_retry_on_invalid_address(self, mock_fetch_infra, mock_geocode):
        from backend.services.location import fetch_location

        mock_geocode.return_value = None

        result = await fetch_location("Nonexistent Fake Address 999999")
        self.assertIsNotNone(result)
        mock_fetch_infra.assert_not_called()
        self.assertEqual(result.fetch_status, "invalid_address")
        self.assertIsNone(result.latitude)

    def test_compare_location_flags_fetch_failure(self):
        from backend.models.score import LocationResult
        from backend.services.compare import _compare_location

        loc_a = LocationResult(
            locality="Dwarka",
            latitude=28.59,
            longitude=77.04,
            risk_score=None,
            fetch_status="fetch_failed",
            error_message="Overpass timeout"
        )
        loc_b = LocationResult(
            locality="Connaught Place",
            latitude=28.63,
            longitude=77.22,
            risk_score=55.0,
            fetch_status="active"
        )

        diff = _compare_location(loc_a, loc_b, "Dwarka", "Connaught Place")
        self.assertTrue(diff.fetch_failed_a)
        self.assertFalse(diff.fetch_failed_b)
        self.assertIsNone(diff.score_a)
        self.assertEqual(diff.score_b, 55.0)
        self.assertIn("Overpass timeout", diff.reason)

    async def test_empty_mirror_does_not_preempt_non_empty_mirror(self):
        """A mirror returning 0 elements must not cancel other mirrors that have verified elements."""
        class _EmptyResponse:
            status_code = 200
            def json(self):
                return {"elements": []}

        class _NonEmptyResponse:
            status_code = 200
            def json(self):
                return {
                    "elements": [
                        {"tags": {"amenity": "school", "name": "Delhi Public School"}},
                        {"tags": {"amenity": "hospital", "name": "City Hospital"}},
                    ]
                }

        class _MockClient:
            def __init__(self, *, timeout):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return False
            async def post(self, url, **kwargs):
                if "fast-empty" in url:
                    return _EmptyResponse()
                return _NonEmptyResponse()

        endpoints = [
            "https://fast-empty.example/api/interpreter",
            "https://has-elements.example/api/interpreter",
        ]
        with patch("backend.services.location.httpx.AsyncClient", _MockClient):
            infra = await fetch_overpass_infrastructure(
                lat=28.65, lon=77.15, endpoints=endpoints
            )
            self.assertIsNotNone(infra)
            self.assertEqual(infra.schools_count, 1)
            self.assertEqual(infra.hospitals_count, 1)
            self.assertIn("Delhi Public School", infra.nearby_places)

    async def test_all_mirrors_fail_returns_none_not_zero(self):
        """When all mirrors fail or timeout, returns None so caller can set fetch_failed instead of 0 amenities."""
        class _FailingClient:
            def __init__(self, *, timeout):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return False
            async def post(self, url, **kwargs):
                raise httpx.ReadTimeout("Mirror timed out")

        with patch("backend.services.location.httpx.AsyncClient", _FailingClient):
            infra = await fetch_overpass_infrastructure(
                lat=28.65, lon=77.15, endpoints=["https://mirror1.example", "https://mirror2.example"]
            )
            self.assertIsNone(infra)

    async def test_headers_include_accept_and_user_agent(self):
        """Verify headers sent to Overpass mirrors contain Accept: application/json and User-Agent."""
        captured_headers = {}

        class _HeaderCapturingClient:
            def __init__(self, *, timeout):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return False
            async def post(self, url, **kwargs):
                captured_headers.update(kwargs.get("headers", {}))
                return _FakeResponse()

        with patch("backend.services.location.httpx.AsyncClient", _HeaderCapturingClient):
            await fetch_overpass_infrastructure(
                lat=28.65, lon=77.15, endpoints=["https://test.example"]
            )
            self.assertIn("application/json", captured_headers.get("Accept", ""))
            self.assertIn("NIVAS", captured_headers.get("User-Agent", ""))


