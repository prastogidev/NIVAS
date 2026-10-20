import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.disaster import (
    load_hazard_zones_geojson,
    get_disaster_hazards,
    compare_disaster_hazards,
    get_hazard_layers_registry,
    get_layer_geometry,
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


def test_hazard_layers_registry():
    """Verify hazard layers registry returns all supported layers with metadata."""
    registry = get_hazard_layers_registry()
    assert registry.total_layers >= 7
    layer_ids = [l.layer_id for l in registry.layers]
    assert "seismic_zones" in layer_ids
    assert "river_flood_basins" in layer_ids
    assert "cyclone_coastal" in layer_ids
    assert "landslide_zones" in layer_ids
    assert "delhi_waterlogging_hotspots" in layer_ids


def test_get_layer_geometry():
    """Verify geometry retrieval for valid and invalid layer IDs."""
    geom_seismic = get_layer_geometry("seismic_zones")
    assert geom_seismic is not None
    assert "features" in geom_seismic
    assert len(geom_seismic["features"]) > 0

    geom_cyclone = get_layer_geometry("cyclone_coastal")
    assert geom_cyclone is not None
    assert len(geom_cyclone["features"]) > 0

    geom_invalid = get_layer_geometry("non_existent_layer")
    assert geom_invalid is None


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
    assert seismic.evidence_status == "evidence_found"

    # Flood hazard in Dwarka must be low (upland)
    flood = next((h for h in res.hazards if h.hazard_type == "flood"), None)
    assert flood is not None
    assert flood.severity == "low"


@pytest.mark.asyncio
async def test_get_disaster_hazards_yamuna_floodplain():
    """Verify coordinates inside Yamuna floodplain evaluate to critical flood severity."""
    res = await get_disaster_hazards(latitude=28.665, longitude=77.240, address="Yamuna Bazar")
    assert res.status == "active"

    flood = next((h for h in res.hazards if h.hazard_type == "flood"), None)
    assert flood is not None
    assert flood.severity in ("critical", "moderate")
    assert flood.evidence_status == "evidence_found"


@pytest.mark.asyncio
async def test_get_disaster_hazards_mumbai_coastal():
    """Verify Mumbai hazards: Zone III seismic, coastal cyclone exposure, waterlogging data unavailable."""
    res = await get_disaster_hazards(latitude=19.0760, longitude=72.8777, address="Bandra, Mumbai, Maharashtra")
    assert res.status == "active"
    assert res.state == "Maharashtra"

    # Seismic must be Zone III
    seismic = next((h for h in res.hazards if h.hazard_type == "earthquake"), None)
    assert seismic is not None
    assert seismic.severity == "moderate"
    assert "Zone III" in seismic.title

    # Cyclone must be active on coastal belt
    cyclone = next((h for h in res.hazards if h.hazard_type == "cyclone"), None)
    assert cyclone is not None
    assert cyclone.severity in ("high", "moderate", "critical")
    assert cyclone.evidence_status == "evidence_found"

    # Waterlogging must be explicitly data_unavailable outside Delhi
    waterlogging = next((h for h in res.hazards if h.hazard_type == "waterlogging"), None)
    assert waterlogging is not None
    assert waterlogging.evidence_status == "data_unavailable"
    assert "Data Unavailable" in waterlogging.title or "unavailable" in waterlogging.title.lower()


@pytest.mark.asyncio
async def test_get_disaster_hazards_shimla_landslide():
    """Verify Shimla hazards: Zone IV seismic, GSI landslide susceptibility."""
    res = await get_disaster_hazards(latitude=31.1048, longitude=77.1734, address="Mall Road, Shimla, Himachal Pradesh")
    assert res.status == "active"

    landslide = next((h for h in res.hazards if h.hazard_type == "landslide"), None)
    assert landslide is not None
    assert landslide.severity in ("high", "critical")
    assert landslide.evidence_status == "evidence_found"


@pytest.mark.asyncio
async def test_get_disaster_hazards_patna_ganga_basin():
    """Verify Patna hazards: Zone IV seismic, Ganga river basin flood corridor."""
    res = await get_disaster_hazards(latitude=25.5941, longitude=85.1376, address="Patna, Bihar")
    assert res.status == "active"

    flood = next((h for h in res.hazards if h.hazard_type == "flood"), None)
    assert flood is not None
    assert flood.severity == "high"
    assert "Ganga" in flood.title


@pytest.mark.asyncio
async def test_out_of_coverage_location():
    """Verify location outside India returns out_of_coverage."""
    # London coordinates
    res = await get_disaster_hazards(latitude=51.5074, longitude=-0.1278, address="London, UK")
    assert res.status == "out_of_coverage"
    assert "Republic of India" in res.error_message


@pytest.mark.asyncio
async def test_compare_disaster_hazards_delhi_vs_mumbai():
    """Verify relocation comparison between two Indian cities (Delhi vs Mumbai)."""
    req = DisasterCompareRequest(
        location_a={"latitude": 28.5921, "longitude": 77.0460, "address": "Dwarka Sector 12, Delhi"},
        location_b={"latitude": 19.0760, "longitude": 72.8777, "address": "Bandra, Mumbai, Maharashtra"},
    )
    res = await compare_disaster_hazards(req)
    assert res.status == "active"
    assert len(res.comparative_analysis) >= 4

    seismic_cmp = next((c for c in res.comparative_analysis if c["hazard_type"] == "earthquake"), None)
    assert seismic_cmp is not None
    assert "Zone IV" in seismic_cmp["location_a_verdict"]
    assert "Zone III" in seismic_cmp["location_b_verdict"]


@pytest.mark.asyncio
async def test_compare_disaster_hazards_partial_evidence():
    """Verify comparing a valid Indian location with an out-of-coverage foreign location yields partial_evidence."""
    req = DisasterCompareRequest(
        location_a={"latitude": 28.5921, "longitude": 77.0460, "address": "Dwarka Sector 12, Delhi"},
        location_b={"latitude": 1.3521, "longitude": 103.8198, "address": "Singapore"},
    )
    res = await compare_disaster_hazards(req)
    assert res.status == "partial_evidence"
    assert res.comparative_analysis == []
    assert "cannot be ranked as safer" in res.comparison_verdict


@pytest.mark.asyncio
async def test_compare_disaster_hazards_incomparable():
    """Verify comparing two locations without valid coordinates yields incomparable status."""
    req = DisasterCompareRequest(
        location_a={"latitude": None, "longitude": None, "address": "Unknown A"},
        location_b={"latitude": None, "longitude": None, "address": "Unknown B"},
    )
    res = await compare_disaster_hazards(req)
    assert res.status == "incomparable"
    assert res.comparative_analysis == []
    assert "cannot be performed" in res.comparison_verdict


def test_api_disaster_layers_endpoint(client):
    """Test FastAPI GET /api/disaster/layers."""
    resp = client.get("/api/disaster/layers")
    assert resp.status_code == 200
    data = resp.json()
    assert "layers" in data
    assert data["total_layers"] >= 7


def test_api_disaster_layer_geometry_endpoint(client):
    """Test FastAPI GET /api/disaster/layer-geometry."""
    resp = client.get("/api/disaster/layer-geometry?layer_id=seismic_zones")
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 0

    resp_404 = client.get("/api/disaster/layer-geometry?layer_id=invalid_layer_xyz")
    assert resp_404.status_code == 404


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
