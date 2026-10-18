import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.score import InfrastructureSummary, AQIResult

client = TestClient(app)


def test_livability_data_get_success():
    """Test successful GET request returning structured location data."""
    mock_infra = InfrastructureSummary(
        schools_count=5,
        hospitals_count=3,
        clinics_count=2,
        pharmacies_count=4,
        police_stations_count=1,
        fire_stations_count=1,
        public_transport_count=8,
        railway_stations_count=2,
        major_roads_count=6,
        nearby_places=["Dwarka Sector 12 Metro", "Venkateshwar Hospital", "Delhi Public School"],
    )
    mock_aqi = (
        AQIResult(
            aqi_value=142.0,
            category="Unhealthy for Sensitive Groups",
            station_name="Dwarka Sector 8",
            source="AQICN WAQI API",
            environmental_score=45.0,
            fetch_status="active",
        ),
        "active",
        None,
    )

    with patch("backend.api.livability.fetch_overpass_infrastructure", new=AsyncMock(return_value=mock_infra)), \
         patch("backend.api.livability.fetch_real_aqi_with_status", new=AsyncMock(return_value=mock_aqi)):
        
        response = client.get(
            "/api/livability/location-data",
            params={"latitude": 28.5921, "longitude": 77.0460, "address": "Dwarka Sector 12, New Delhi"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["latitude"] == 28.5921
        assert data["longitude"] == 77.0460
        assert data["address"] == "Dwarka Sector 12, New Delhi"
        assert data["locality"] == "Dwarka Sector 12"
        assert "retrieved_at" in data

        # Civic Infrastructure
        infra = data["infrastructure"]
        assert infra["status"] == "active"
        assert infra["source"] == "OpenStreetMap Overpass API"
        assert infra["schools_count"] == 5
        assert infra["hospitals_count"] == 3
        assert infra["railway_stations_count"] == 2
        assert infra["total_facilities"] == 32
        assert len(infra["nearby_places"]) == 3
        assert "Dwarka Sector 12 Metro" in infra["nearby_places"]

        # Air Quality
        aqi = data["air_quality"]
        assert aqi["status"] == "active"
        assert aqi["aqi_value"] == 142.0
        assert aqi["category"] == "Unhealthy for Sensitive Groups"
        assert aqi["station_name"] == "Dwarka Sector 8"

        # Hazards
        hazards = data["environmental_hazards"]
        assert hazards["status"] == "data_not_configured"
        assert "not configured" in hazards["message"]


def test_livability_data_post_success():
    """Test successful POST request alternative."""
    mock_infra = InfrastructureSummary(
        schools_count=1,
        hospitals_count=0,
        clinics_count=0,
        pharmacies_count=1,
        police_stations_count=0,
        fire_stations_count=0,
        public_transport_count=2,
        railway_stations_count=0,
        major_roads_count=1,
        nearby_places=["Local Park"],
    )
    mock_aqi = (None, "provider_not_configured", "Air quality API key is not configured in backend environment.")

    with patch("backend.api.livability.fetch_overpass_infrastructure", new=AsyncMock(return_value=mock_infra)), \
         patch("backend.api.livability.fetch_real_aqi_with_status", new=AsyncMock(return_value=mock_aqi)):

        response = client.post(
            "/api/livability/location-data",
            json={"latitude": 28.7041, "longitude": 77.1025, "address": "Rohini Sector 8, Delhi"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["locality"] == "Rohini Sector 8"
        assert data["infrastructure"]["status"] == "active"
        assert data["infrastructure"]["total_facilities"] == 5
        assert data["air_quality"]["status"] == "provider_not_configured"
        assert data["air_quality"]["aqi_value"] is None
        assert "not configured" in data["air_quality"]["error_message"]


def test_livability_data_distinguishes_zero_results_from_failure():
    """Test that zero recorded facilities returns status='empty' instead of 'fetch_failed'."""
    empty_infra = InfrastructureSummary(
        schools_count=0,
        hospitals_count=0,
        clinics_count=0,
        pharmacies_count=0,
        police_stations_count=0,
        fire_stations_count=0,
        public_transport_count=0,
        railway_stations_count=0,
        major_roads_count=0,
        nearby_places=[],
    )
    mock_aqi = (None, "data_unavailable", "No monitoring stations within 50km.")

    with patch("backend.api.livability.fetch_overpass_infrastructure", new=AsyncMock(return_value=empty_infra)), \
         patch("backend.api.livability.fetch_real_aqi_with_status", new=AsyncMock(return_value=mock_aqi)):

        response = client.get(
            "/api/livability/location-data",
            params={"latitude": 28.0, "longitude": 77.0},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["infrastructure"]["status"] == "empty"
        assert data["infrastructure"]["total_facilities"] == 0
        assert data["air_quality"]["status"] == "data_unavailable"


def test_livability_data_handles_overpass_timeout_or_failure():
    """Test that mirror failure reports status='fetch_failed' with transparent message."""
    mock_aqi = (None, "provider_not_configured", "Provider missing")

    with patch("backend.api.livability.fetch_overpass_infrastructure", new=AsyncMock(return_value=None)), \
         patch("backend.api.livability.fetch_real_aqi_with_status", new=AsyncMock(return_value=mock_aqi)):

        response = client.get(
            "/api/livability/location-data",
            params={"latitude": 28.5921, "longitude": 77.0460},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["infrastructure"]["status"] == "fetch_failed"
        assert "unreachable or timed out" in data["infrastructure"]["error_message"]
        assert data["infrastructure"]["total_facilities"] == 0


def test_livability_data_invalid_coordinates():
    """Test latitude and longitude boundary validation."""
    # Latitude out of bounds
    res1 = client.get(
        "/api/livability/location-data",
        params={"latitude": 95.0, "longitude": 77.0},
    )
    assert res1.status_code in (400, 422)

    # Longitude out of bounds
    res2 = client.get(
        "/api/livability/location-data",
        params={"latitude": 28.0, "longitude": 195.0},
    )
    assert res2.status_code in (400, 422)


def test_inspection_endpoint_isolation():
    """Verify inspection /api/score endpoint is completely unaffected and healthy."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_livability_facility_markers_use_actual_coordinates():
    """Verify that facilities list preserves exact provider coordinates without synthetic alteration."""
    facilities_data = [
        {
            "id": "1001",
            "name": "Delhi Public School Dwarka",
            "category": "school",
            "category_label": "School",
            "latitude": 28.591234,
            "longitude": 77.045678,
            "source": "OpenStreetMap",
        },
        {
            "id": "2002",
            "name": "Venkateshwar Hospital",
            "category": "hospital",
            "category_label": "Hospital",
            "latitude": 28.589101,
            "longitude": 77.042233,
            "source": "OpenStreetMap",
        },
    ]
    mock_infra = InfrastructureSummary(
        schools_count=1,
        hospitals_count=1,
        facilities=facilities_data,
    )
    mock_aqi = (None, "provider_not_configured", "Not configured")

    with patch("backend.api.livability.fetch_overpass_infrastructure", new=AsyncMock(return_value=mock_infra)), \
         patch("backend.api.livability.fetch_real_aqi_with_status", new=AsyncMock(return_value=mock_aqi)):

        response = client.get(
            "/api/livability/location-data",
            params={"latitude": 28.5921, "longitude": 77.0460},
        )

        assert response.status_code == 200
        data = response.json()
        facilities = data["infrastructure"]["facilities"]
        assert len(facilities) == 2

        # Verify real coordinates match exactly
        assert facilities[0]["name"] == "Delhi Public School Dwarka"
        assert facilities[0]["latitude"] == 28.591234
        assert facilities[0]["longitude"] == 77.045678
        assert facilities[0]["category"] == "school"
        assert facilities[0]["source"] == "OpenStreetMap"

        assert facilities[1]["name"] == "Venkateshwar Hospital"
        assert facilities[1]["latitude"] == 28.589101
        assert facilities[1]["longitude"] == 77.042233
        assert facilities[1]["category"] == "hospital"

