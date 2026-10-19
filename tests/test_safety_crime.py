import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.crime_data import (
    point_in_polygon,
    resolve_police_district,
    load_crime_baseline,
    load_districts_geojson,
    get_locality_safety_data,
    get_national_safety_overview,
    load_india_states_geojson,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_crime_baseline_dataset_integrity():
    """Verify official NCRB and Delhi Police dataset schema and 15-district completeness."""
    baseline = load_crime_baseline()
    assert "metadata" in baseline
    assert baseline["metadata"]["latest_reporting_year"] == 2022
    assert len(baseline["metadata"]["historical_years_covered"]) == 5

    districts = baseline.get("districts", {})
    assert len(districts) == 15, "Dataset must cover all 15 Delhi Police Districts"

    for dcode, data in districts.items():
        assert data["district_code"] == dcode
        assert "district_name" in data
        assert data["total_ipc_crimes_2022"] > 0
        assert data["population_projection_2022"] > 0
        assert data["crime_rate_per_lakh"] is None, "District crime rate per lakh must be suppressed due to unaligned Census boundaries"
        assert data["data_status"] == "derived_estimate"
        assert data["is_derived_estimate"] is True
        assert "Census" in data["rate_unavailable_reason"]
        assert len(data["historical_trend_ipc"]) == 5
        assert len(data["categories_2022"]) >= 4

        # Validate category share sum ~ 100%
        shares = [c["share_pct"] for c in data["categories_2022"]]
        assert 95.0 <= sum(shares) <= 105.0


def test_districts_geojson_validity():
    """Verify GeoJSON polygon definitions for Delhi Police districts."""
    geojson = load_districts_geojson()
    features = geojson.get("features", [])
    assert len(features) == 15
    for feat in features:
        geom = feat.get("geometry", {})
        assert geom.get("type") == "Polygon"
        coords = geom.get("coordinates", [])[0]
        assert len(coords) >= 4
        # Verify closed ring
        assert coords[0] == coords[-1]


def test_point_in_polygon_ray_casting():
    """Test ray casting point-in-polygon math."""
    # Unit box [0,0] to [10,10]
    box = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]]
    assert point_in_polygon(5.0, 5.0, box) is True
    assert point_in_polygon(15.0, 5.0, box) is False
    assert point_in_polygon(5.0, 15.0, box) is False
    assert point_in_polygon(-1.0, -1.0, box) is False


def test_resolve_police_district_dwarka():
    """Verify Dwarka coordinates resolve to Dwarka District."""
    # Dwarka Sector 12: 28.5921, 77.0460
    resolved = resolve_police_district(28.5921, 77.0460)
    assert resolved is not None
    dcode, ring = resolved
    assert dcode == "DEL_DWK"
    assert len(ring) >= 4


def test_resolve_police_district_connaught_place():
    """Verify Connaught Place coordinates resolve to New Delhi District."""
    # CP: 28.6315, 77.2167
    resolved = resolve_police_district(28.6315, 77.2167)
    assert resolved is not None
    dcode, ring = resolved
    assert dcode == "DEL_ND"


def test_resolve_outside_delhi():
    """Verify coordinates far outside Delhi return None (unknown jurisdiction)."""
    # Mumbai coordinates
    resolved = resolve_police_district(19.0760, 72.8777)
    assert resolved is None


@pytest.mark.asyncio
async def test_get_locality_safety_data_active():
    """Verify full safety response for valid Delhi location with strict official-data separation."""
    res = await get_locality_safety_data(
        latitude=28.5921,
        longitude=77.0460,
        address="Dwarka Sector 12, Delhi",
        radius=1200,
    )
    assert res.status == "active"
    assert res.matched_district is not None
    assert res.matched_district.district_code == "DEL_DWK"
    assert res.matched_district.district_name == "Dwarka District"
    assert res.matched_district.total_ipc_crimes_2022 > 0
    assert res.matched_district.crime_rate_per_lakh is None, "Per-capita rate must be suppressed at district level"
    assert res.matched_district.data_status == "derived_estimate"
    assert res.matched_district.is_derived_estimate is True
    assert res.matched_district.rate_unavailable_reason is not None
    assert res.matched_district.reporting_year == 2022
    assert len(res.matched_district.historical_trend_ipc) == 5
    assert len(res.matched_district.categories_2022) >= 4
    assert res.matched_district.jurisdiction_polygon is not None
    assert len(res.transparency_notes) >= 3

    # Check verified official state crime stat
    assert res.official_state_crime is not None
    assert res.official_state_crime.data_status == "verified_official"
    assert res.official_state_crime.is_derived_estimate is False
    assert res.official_state_crime.total_ipc_cases == 298988
    assert res.official_state_crime.crime_rate_per_lakh == 1422.6
    assert res.official_state_crime.state_ut_name == "NCT of Delhi"


@pytest.mark.asyncio
async def test_get_locality_safety_data_delhi_bbox_outside_polygons():
    """Verify point inside Delhi bounding box but outside approximate polygons never synthesizes a match."""
    # Far southwest corner of Delhi bounding box outside approximate district polygons
    res = await get_locality_safety_data(
        latitude=28.21,
        longitude=76.78,
        address="Rural Border, NCT of Delhi",
        radius=1200,
    )
    assert res.status == "unknown_jurisdiction"
    assert res.matched_district is None
    assert "police district reference polygon" in res.error_message
    # Official state baseline should still be available
    assert res.official_state_crime is not None
    assert res.official_state_crime.total_ipc_cases == 298988


@pytest.mark.asyncio
async def test_get_locality_safety_data_outside_delhi():
    """Verify unknown jurisdiction status when queried outside Delhi."""
    res = await get_locality_safety_data(
        latitude=12.9716,
        longitude=77.5946,
        address="Bengaluru, Karnataka",
        radius=1200,
    )
    assert res.status == "unknown_jurisdiction"
    assert res.matched_district is None
    assert "outside" in res.error_message.lower()


@pytest.mark.asyncio
async def test_get_locality_safety_data_invalid_coords():
    """Verify invalid coordinates handle gracefully."""
    res = await get_locality_safety_data(
        latitude=999.0,
        longitude=77.0,
        address="Invalid",
        radius=1200,
    )
    assert res.status == "data_unavailable"
    assert "invalid" in res.error_message.lower()


def test_api_safety_data_endpoint(client):
    """Test FastAPI GET /api/livability/safety-data endpoint."""
    resp = client.get("/api/livability/safety-data?latitude=28.5921&longitude=77.0460&address=Dwarka&radius=1200")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"
    assert data["matched_district"]["district_code"] == "DEL_DWK"
    assert data["matched_district"]["reporting_year"] == 2022
    assert data["matched_district"]["crime_rate_per_lakh"] is None
    assert data["matched_district"]["data_status"] == "derived_estimate"
    assert "categories_2022" in data["matched_district"]
    assert "historical_trend_ipc" in data["matched_district"]
    assert data["official_state_crime"]["data_status"] == "verified_official"
    assert data["official_state_crime"]["total_ipc_cases"] == 298988
    assert data["official_state_crime"]["crime_rate_per_lakh"] == 1422.6


@pytest.mark.asyncio
async def test_get_locality_safety_data_provenance_and_benchmark():
    """Verify official NCRB Table 1A.1 benchmark and provenance fields are present."""
    res = await get_locality_safety_data(
        latitude=28.5921,
        longitude=77.0460,
        address="Dwarka Sector 12, Delhi",
        radius=1200,
    )
    assert res.status == "active"
    district = res.matched_district
    assert district is not None

    # Provenance fields
    assert district.boundary_type == "spatial_approximation_reference"
    assert "approximated" in district.boundary_disclaimer.lower()
    assert district.is_derived_estimate is True
    assert district.provenance_details is not None
    assert "NCRB" in district.provenance_details["official_table_state_ut"]
    assert "Table 1A.1" in district.provenance_details["official_table_state_ut"]

    # State/UT Benchmark
    benchmark = district.state_ut_benchmark
    assert benchmark is not None
    assert "2022" in benchmark
    assert benchmark["2022"]["total_ipc_cases"] == 298988
    assert benchmark["2022"]["crime_rate_per_lakh"] == 1422.6
    assert "Table 1A.1" in benchmark["2022"]["source_table"]


@pytest.mark.asyncio
async def test_get_locality_safety_data_zero_radius():
    """Verify zero or non-positive radius defaults gracefully to 0 without crashing."""
    res = await get_locality_safety_data(
        latitude=28.5921,
        longitude=77.0460,
        address="Dwarka Sector 12, Delhi",
        radius=0,
    )
    assert res.status == "active"
    assert res.search_radius_meters == 0
    assert res.nearby_police_stations == []
    # Nearest stations directory still provides orientation
    assert len(res.nearest_police_stations) > 0


@pytest.mark.asyncio
async def test_get_locality_safety_data_nearest_police_stations():
    """Verify nearest police stations are returned, strictly sorted by distance with locality."""
    res = await get_locality_safety_data(
        latitude=28.6315,
        longitude=77.2167,
        address="Connaught Place, New Delhi",
        radius=1200,
    )
    assert res.status == "active"
    assert len(res.nearest_police_stations) >= 3
    # Check strict ascending order by distance
    distances = [s.distance_km for s in res.nearest_police_stations]
    assert distances == sorted(distances)
    # Check attributes
    first = res.nearest_police_stations[0]
    assert first.name is not None
    assert first.distance_km is not None
    assert "km" in first.formatted_distance
    assert first.latitude > 0
    assert first.longitude > 0
    assert isinstance(first.is_within_radius, bool)


def test_national_safety_overview_dataset_and_service():
    """Verify all 36 states/UTs are represented with official Table 1A.1 metrics and valid classification."""
    overview = get_national_safety_overview()
    assert overview.status == "active"
    assert overview.reporting_year == 2022
    assert overview.national_benchmark_rate == 258.1
    assert overview.total_all_india_ipc_cases == 3561379
    assert overview.coverage_summary["total_states_mapped"] == 36
    assert overview.coverage_summary["states_with_statutory_data"] == 36
    assert overview.coverage_summary["coverage_percentage"] == 100.0

    features = overview.geojson.get("features", [])
    assert len(features) == 36

    # Verify classification logic
    for f in features:
        props = f["properties"]
        assert props["state_code"].startswith("IN-")
        assert props["reporting_year"] == 2022
        assert props["risk_tier"] in ("lower", "moderate", "higher", "no_data")
        assert props["color"] in ("#10B981", "#F59E0B", "#EF4444", "#94A3B8")
        rate = props["crime_rate_per_lakh"]
        if rate is not None:
            if rate < 200.0:
                assert props["risk_tier"] == "lower"
                assert props["color"] == "#10B981"
            elif rate <= 350.0:
                assert props["risk_tier"] == "moderate"
                assert props["color"] == "#F59E0B"
            else:
                assert props["risk_tier"] == "higher"
                assert props["color"] == "#EF4444"

    # Specific check for Delhi and Uttar Pradesh
    delhi = [f["properties"] for f in features if f["properties"]["state_code"] == "IN-DL"][0]
    assert delhi["crime_rate_per_lakh"] == 1422.6
    assert delhi["risk_tier"] == "higher"
    assert delhi["has_district_data"] is True
    assert delhi["e_fir_effect"] is not None

    up = [f["properties"] for f in features if f["properties"]["state_code"] == "IN-UP"][0]
    assert up["crime_rate_per_lakh"] == 171.6
    assert up["risk_tier"] == "lower"


def test_national_safety_overview_api_endpoint(client):
    """Verify GET /api/livability/national-safety-overview endpoint returns valid schema."""
    resp = client.get("/api/livability/national-safety-overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"
    assert data["reporting_year"] == 2022
    assert data["national_benchmark_rate"] == 258.1
    assert data["total_all_india_ipc_cases"] == 3561379
    assert data["coverage_summary"]["total_states_mapped"] == 36
    assert len(data["geojson"]["features"]) == 36
    assert "interpretability_guide" in data



