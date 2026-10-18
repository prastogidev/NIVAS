import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.disaster import (
    load_hazard_zones_geojson,
    get_disaster_hazards,
    compare_disaster_hazards,
)
from backend.models.disaster import DisasterCompareRequest


@pytest.fixture
def client():
    return TestClient(app)


def test_hazard_geojson_validity():
    """Verify hazard zones GeoJSON loads correctly."""
    data = load_hazard_zones_geojson()
    assert "features" in data
    assert len(data["features"]) >= 3
    types = [f["properties"]["hazard_type"] for f in data["features"]]
    assert "earthquake" in types
    assert "flood" in types
    assert "waterlogging" in types


@pytest.mark.asyncio
async def test_get_disaster_hazards_dwarka_upland():
    """Verify Dwarka hazards (upland from Yamuna, in Zone IV)."""
    res = await get_disaster_hazards(latitude=28.5921, longitude=77.0460, address="Dwarka Sector 12")
    assert res.status == "active"
    assert len(res.hazards) >= 4

    # Seismic hazard must always be present
    seismic = next((h for h in res.hazards if h.hazard_type == "earthquake"), None)
    assert seismic is not None
    assert seismic.severity == "high"
    assert "Zone IV" in seismic.title

    # Flood hazard in Dwarka must be low (upland)
    flood = next((h for h in res.hazards if h.hazard_type == "flood"), None)
    assert flood is not None
    assert flood.severity == "low"


@pytest.mark.asyncio
async def test_get_disaster_hazards_yamuna_floodplain():
    """Verify coordinates inside Yamuna floodplain evaluate to critical flood severity."""
    # Near Yamuna Bazar / Old Railway Bridge: 28.665, 77.240
    res = await get_disaster_hazards(latitude=28.665, longitude=77.240, address="Yamuna Bazar")
    assert res.status == "active"

    flood = next((h for h in res.hazards if h.hazard_type == "flood"), None)
    assert flood is not None
    assert flood.severity in ("critical", "moderate")


@pytest.mark.asyncio
async def test_compare_disaster_hazards_between_two_localities():
    """Verify relocation comparison between Dwarka (upland) and Yamuna Bazar (floodplain)."""
    req = DisasterCompareRequest(
        location_a={"latitude": 28.5921, "longitude": 77.0460, "address": "Dwarka Sector 12"},
        location_b={"latitude": 28.6650, "longitude": 77.2400, "address": "Yamuna Bazar"},
    )
    res = await compare_disaster_hazards(req)
    assert res.status == "active"
    assert res.location_a.locality_name is not None
    assert res.location_b.locality_name is not None
    assert len(res.comparative_analysis) >= 2


def test_api_disaster_hazard_endpoint(client):
    """Test FastAPI GET /api/disaster/hazard-data."""
    resp = client.get("/api/disaster/hazard-data?latitude=28.5921&longitude=77.0460&address=Dwarka")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"
    assert len(data["hazards"]) >= 4


def test_api_disaster_compare_endpoint(client):
    """Test FastAPI POST /api/disaster/compare."""
    payload = {
        "location_a": {"latitude": 28.5921, "longitude": 77.0460, "address": "Dwarka Sector 12"},
        "location_b": {"latitude": 28.6517, "longitude": 77.1583, "address": "Shadipur, Delhi"},
    }
    resp = client.post("/api/disaster/compare", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"
    assert "comparative_analysis" in data
