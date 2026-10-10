import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx
from backend.services.price import (
    fetch_price_benchmark_with_status,
    calculate_price_fairness_score,
    normalize_locality_key,
)
from backend.models.score import PriceBenchmarkResult


@pytest.mark.asyncio
async def test_price_not_assessed_empty_address():
    """1. NOT ASSESSED: Empty address returns not_assessed status."""
    res, status, error = await fetch_price_benchmark_with_status("", "Apartment")
    assert res is None
    assert status == "not_assessed"
    assert "required" in (error or "").lower()


@pytest.mark.asyncio
async def test_price_provider_not_configured_when_no_key_and_no_local_dataset():
    """2. PROVIDER NOT CONFIGURED: Remote unknown locality with missing PROPSTACK_API_KEY."""
    with patch("backend.services.price.settings.PROPSTACK_API_KEY", None), \
         patch("backend.services.price.get_cached_price", return_value=None):
        res, status, error = await fetch_price_benchmark_with_status("Kodaikanal Remote Hilltop, Tamil Nadu", "Apartment")
        assert res is None
        assert status == "provider_not_configured"
        assert "propstack api key is not configured" in (error or "").lower()


@pytest.mark.asyncio
async def test_price_successful_propstack_valuation():
    """3. ACTIVE: Propstack API succeeds with valid credentials."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "price_per_sqft": 12500.0,
        "median_price_per_sqft": 13000.0,
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("backend.services.price.settings.PROPSTACK_API_KEY", "mock_valid_propstack_key"), \
         patch("backend.services.price.get_cached_price", return_value=None), \
         patch("httpx.AsyncClient", return_value=mock_client), \
         patch("backend.services.price.save_price_cache") as mock_save:

        res, status, error = await fetch_price_benchmark_with_status("Indirapuram, Ghaziabad", "Apartment")

        assert status == "active"
        assert error is None
        assert res is not None
        assert res.estimated_price_per_sqft == 12500.0
        assert res.source == "Propstack Valuation API"
        assert res.fairness_score is not None
        assert mock_save.called


@pytest.mark.asyncio
async def test_price_propstack_auth_failure_401():
    """4. AUTH FAILURE: Propstack returns 401 Unauthorized."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("backend.services.price.settings.PROPSTACK_API_KEY", "invalid_propstack_key"), \
         patch("backend.services.price.get_cached_price", return_value=None), \
         patch("httpx.AsyncClient", return_value=mock_client):

        res, status, error = await fetch_price_benchmark_with_status("Indirapuram, Ghaziabad", "Apartment")

        assert res is None
        assert status == "fetch_failed"
        assert "authentication failed" in (error or "").lower()


@pytest.mark.asyncio
async def test_price_propstack_timeout():
    """5. FETCH FAILED: Propstack request times out."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timed out"))
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("backend.services.price.settings.PROPSTACK_API_KEY", "mock_key"), \
         patch("backend.services.price.get_cached_price", return_value=None), \
         patch("httpx.AsyncClient", return_value=mock_client):

        res, status, error = await fetch_price_benchmark_with_status("Indirapuram, Ghaziabad", "Apartment")

        assert res is None
        assert status == "fetch_failed"
        assert "timed out" in (error or "").lower()


@pytest.mark.asyncio
async def test_price_data_unavailable_when_propstack_returns_zero():
    """6. DATA UNAVAILABLE: Propstack responds 200 but has no price listings for address."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "price_per_sqft": 0,
        "listings_count": 0,
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("backend.services.price.settings.PROPSTACK_API_KEY", "mock_key"), \
         patch("backend.services.price.get_cached_price", return_value=None), \
         patch("httpx.AsyncClient", return_value=mock_client):

        res, status, error = await fetch_price_benchmark_with_status("Unknown Hamlet, Himachal Pradesh", "Apartment")

        assert res is None
        assert status == "data_unavailable"
        assert "no listings or price benchmark found" in (error or "").lower()


@pytest.mark.asyncio
async def test_price_cached_local_benchmark_fallback_dwarka():
    """7. ACTIVE LOCAL CACHE: Verified Delhi benchmark for Dwarka succeeds without Propstack key."""
    with patch("backend.services.price.settings.PROPSTACK_API_KEY", None), \
         patch("backend.services.price.get_cached_price", return_value=None):

        res, status, error = await fetch_price_benchmark_with_status("Dwarka Sector 12, New Delhi", "Apartment")

        assert status == "active"
        assert error is None
        assert res is not None
        assert res.estimated_price_per_sqft == 8500.0
        assert res.delhi_circle_category == "Category B"
        assert "Cached Demo Benchmark Dataset" in res.source
        assert res.fairness_score == 85.0
        assert res.sample_count is not None


@pytest.mark.asyncio
async def test_price_cached_local_benchmark_fallback_rohini():
    """8. ACTIVE LOCAL CACHE: Verified Delhi benchmark for Rohini succeeds without Propstack key."""
    with patch("backend.services.price.settings.PROPSTACK_API_KEY", None), \
         patch("backend.services.price.get_cached_price", return_value=None):

        res, status, error = await fetch_price_benchmark_with_status("Rohini Sector 15, New Delhi", "Independent House")

        assert status == "active"
        assert error is None
        assert res is not None
        assert res.estimated_price_per_sqft == 9200.0
        assert res.delhi_circle_category == "Category B/C"
        assert res.fairness_score is not None


@pytest.mark.asyncio
async def test_price_cached_local_benchmark_fallback_lajpat_nagar():
    """9. ACTIVE LOCAL CACHE: Verified Delhi benchmark for Lajpat Nagar succeeds without Propstack key."""
    with patch("backend.services.price.settings.PROPSTACK_API_KEY", None), \
         patch("backend.services.price.get_cached_price", return_value=None):

        res, status, error = await fetch_price_benchmark_with_status("Lajpat Nagar Central Market, New Delhi", "Apartment")

        assert status == "active"
        assert error is None
        assert res is not None
        assert res.estimated_price_per_sqft == 14000.0
        assert res.delhi_circle_category == "Category A/B"
        assert res.fairness_score is not None


@pytest.mark.asyncio
async def test_price_ttl_cache_hit():
    """10. CACHE HIT: Returns cached PriceBenchmarkResult immediately."""
    cached_obj = PriceBenchmarkResult(
        estimated_price_per_sqft=9000.0,
        fairness_score=85.0,
        source="Deterministic TTL Cache",
        fetch_status="active",
    )

    with patch("backend.services.price.get_cached_price", return_value=cached_obj):
        res, status, error = await fetch_price_benchmark_with_status("Dwarka Sector 12, New Delhi", "Apartment")
        assert status == "active"
        assert error is None
        assert res is not None
        assert res.estimated_price_per_sqft == 9000.0
        assert res.source == "Deterministic TTL Cache"
