import json
import logging
import math
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

from backend.models.safety import (
    CrimeCategoryStat,
    DistrictCrimeProfile,
    PoliceStationFacility,
    LocalitySafetyResponse,
    OfficialStateCrimeStat,
)
from backend.services.location import fetch_overpass_infrastructure

logger = logging.getLogger("nivas.services.crime_data")


def calculate_haversine_distance_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> Optional[float]:
    """Calculate great-circle distance between two coordinates in kilometers."""
    try:
        if any(x is None or math.isnan(x) for x in (lat1, lon1, lat2, lon2)):
            return None
        r = 6371.0
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = (
            math.sin(d_lat / 2.0) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(d_lon / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return round(r * c, 2)
    except Exception:
        return None

BASE_DIR = Path(__file__).resolve().parent.parent
CRIME_DATA_PATH = BASE_DIR / "data" / "crime" / "delhi_district_crime_baseline.json"
DISTRICTS_GEOJSON_PATH = BASE_DIR / "data" / "crime" / "delhi_police_districts.geojson"

# Module-level cache
_CACHED_BASELINE: Optional[Dict[str, Any]] = None
_CACHED_GEOJSON: Optional[Dict[str, Any]] = None


def load_crime_baseline() -> Dict[str, Any]:
    global _CACHED_BASELINE
    if _CACHED_BASELINE is None:
        try:
            if CRIME_DATA_PATH.exists():
                with open(CRIME_DATA_PATH, "r", encoding="utf-8") as f:
                    _CACHED_BASELINE = json.load(f)
            else:
                logger.error("Crime baseline file not found at %s", CRIME_DATA_PATH)
                _CACHED_BASELINE = {"metadata": {}, "districts": {}}
        except Exception as e:
            logger.error("Error loading crime baseline: %s", e)
            _CACHED_BASELINE = {"metadata": {}, "districts": {}}
    return _CACHED_BASELINE


def load_districts_geojson() -> Dict[str, Any]:
    global _CACHED_GEOJSON
    if _CACHED_GEOJSON is None:
        try:
            if DISTRICTS_GEOJSON_PATH.exists():
                with open(DISTRICTS_GEOJSON_PATH, "r", encoding="utf-8") as f:
                    _CACHED_GEOJSON = json.load(f)
            else:
                logger.error("Districts GeoJSON not found at %s", DISTRICTS_GEOJSON_PATH)
                _CACHED_GEOJSON = {"features": []}
        except Exception as e:
            logger.error("Error loading districts GeoJSON: %s", e)
            _CACHED_GEOJSON = {"features": []}
    return _CACHED_GEOJSON


def point_in_polygon(lon: float, lat: float, poly_coords: List[List[float]]) -> bool:
    """
    Standard ray-casting point-in-polygon test.
    poly_coords is a list of [lon, lat] pairs.
    """
    n = len(poly_coords)
    if n < 3:
        return False
    inside = False
    p1x, p1y = poly_coords[0]
    for i in range(1, n + 1):
        p2x, p2y = poly_coords[i % n]
        if lat > min(p1y, p2y):
            if lat <= max(p1y, p2y):
                if lon <= max(p1x, p2x):
                    xinters = (lat - p1y) * (p2x - p1x) / (p2y - p1y) + p1x if p1y != p2y else p1x
                    if p1x == p2x or lon <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def resolve_police_district(latitude: float, longitude: float) -> Optional[Tuple[str, List[List[float]]]]:
    """
    Match latitude and longitude against Delhi Police district polygons.
    Returns (district_code, polygon_coordinates) or None.
    Only returns a match when point strictly intersects a reference polygon.
    Never assigns an arbitrary jurisdiction via centroid fallback.
    """
    geojson = load_districts_geojson()
    features = geojson.get("features", [])

    for feat in features:
        geom = feat.get("geometry", {})
        props = feat.get("properties", {})
        dcode = props.get("district_code")
        coords = geom.get("coordinates", [])

        if geom.get("type") == "Polygon" and coords:
            ring = coords[0]
            if point_in_polygon(longitude, latitude, ring):
                return dcode, ring

    return None


def get_official_state_crime_stat() -> OfficialStateCrimeStat:
    """Return verified official NCT of Delhi multi-year crime statistics from NCRB Table 1A.1."""
    baseline = load_crime_baseline()
    meta = baseline.get("metadata", {})
    state_ut_totals = meta.get("official_state_ut_totals", {})

    return OfficialStateCrimeStat(
        state_ut_name="NCT of Delhi",
        reporting_year=2022,
        total_ipc_cases=298988,
        crime_rate_per_lakh=1422.6,
        data_status="verified_official",
        is_derived_estimate=False,
        geographic_resolution="state_ut",
        source_agency="National Crime Records Bureau (NCRB), Ministry of Home Affairs",
        source_title="Crime in India 2022",
        source_url="https://ncrb.gov.in/crime-in-india.html",
        source_table_or_page="Table 1A.1: Cognizable IPC Crimes in States and Union Territories",
        population_denominator=21023000,
        population_denominator_year=2022,
        population_source="Report of the Technical Group on Population Projections (RGI / Census of India)",
        multi_year_totals=state_ut_totals,
        limitations="NCT-wide statutory aggregate. Does not represent local neighborhood-level incident density. Over 74% of offenses represent property and vehicle thefts registered via online e-FIRs.",
    )


async def get_locality_safety_data(
    latitude: float,
    longitude: float,
    address: Optional[str] = None,
    radius: int = 1200,
) -> LocalitySafetyResponse:
    """
    Produce truthful, evidence-backed safety and historical crime intelligence for given coordinates.
    Strictly separates verified official State/UT statistics (NCRB Table 1A.1) from exploratory
    derived district allocations. Never claims an approximate polygon is an official cadastral boundary.
    """
    # 1. Coordinate bounds validation
    if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0) or math.isnan(latitude) or math.isnan(longitude):
        return LocalitySafetyResponse(
            status="data_unavailable",
            latitude=latitude,
            longitude=longitude,
            address=address,
            search_radius_meters=radius,
            error_message="Invalid latitude or longitude coordinates.",
        )

    # 2. Build verified official State/UT benchmark (NCRB Table 1A.1)
    baseline = load_crime_baseline()
    meta = baseline.get("metadata", {})
    state_ut_totals = meta.get("official_state_ut_totals", {})
    official_state_crime = get_official_state_crime_stat()

    # 3. Check regional coverage for NCT of Delhi (28.20° - 29.05° N, 76.75° - 77.50° E)
    is_in_delhi_bbox = (28.20 <= latitude <= 29.05 and 76.75 <= longitude <= 77.50)
    if not is_in_delhi_bbox:
        return LocalitySafetyResponse(
            status="unknown_jurisdiction",
            latitude=latitude,
            longitude=longitude,
            address=address,
            search_radius_meters=radius,
            official_state_crime=None,
            matched_district=None,
            jurisdiction_match_type="none",
            error_message="Coordinates fall outside the National Capital Territory of Delhi coverage.",
        )

    # 4. Resolve Police District reference polygon
    resolved = resolve_police_district(latitude, longitude)
    if not resolved:
        return LocalitySafetyResponse(
            status="unknown_jurisdiction",
            latitude=latitude,
            longitude=longitude,
            address=address,
            search_radius_meters=radius,
            official_state_crime=official_state_crime,
            matched_district=None,
            jurisdiction_match_type="none",
            error_message="Location coordinates do not intersect any known police district reference polygon.",
        )

    district_code, boundary_polygon = resolved
    districts_data = baseline.get("districts", {})
    raw_district = districts_data.get(district_code)

    if not raw_district:
        return LocalitySafetyResponse(
            status="data_unavailable",
            latitude=latitude,
            longitude=longitude,
            address=address,
            search_radius_meters=radius,
            official_state_crime=official_state_crime,
            matched_district=None,
            jurisdiction_match_type="none",
            error_message=f"Official crime records for district {district_code} are not indexed.",
        )

    # 5. Build DistrictCrimeProfile (strictly marked as derived_estimate)
    categories = [
        CrimeCategoryStat(
            category_id=c["category_id"],
            label=c["label"],
            count=c["count"],
            share_pct=c["share_pct"],
            description=c["description"],
        )
        for c in raw_district.get("categories_2022", [])
    ]

    provenance_details = {
        "source_agency": "National Crime Records Bureau (NCRB), Ministry of Home Affairs & Delhi Police",
        "publication": "Crime in India (2018–2022) Annual Compendiums & Delhi Police Statistical Statements",
        "official_table_state_ut": "NCRB Crime in India Table 1A.1: Cognizable IPC Crimes in States/UTs",
        "official_table_cities": "NCRB Crime in India Table 1B.1: Cognizable IPC Crimes in 19 Metropolitan Cities (Delhi City)",
        "official_portal_url": "https://ncrb.gov.in/crime-in-india.html",
        "delhi_police_url": "https://delhipolice.gov.in/statistics",
        "geographic_resolution": "NCT of Delhi State/UT Total with Police District Administrative Allocation",
        "is_derived_estimate": True,
        "population_methodology": "Census of India 2011 was surveyed for Revenue Districts, not operational Police Districts. Police district populations are derived projections used by Delhi Police; per-capita rates are suppressed.",
        "boundary_type": "spatial_approximation_reference",
        "boundary_disclaimer": "Approximated Police District Jurisdictional Zone. Macro reference geometry for locality mapping; not an official cadastral boundary published by Delhi Police or Survey of India.",
        "e_fir_theft_context": "Over 74% of registered IPC crimes in Delhi constitute property and vehicle theft, filed digitally via citizen e-FIR portals. Higher counts reflect digital reporting adoption rather than heightened physical danger.",
    }

    district_profile = DistrictCrimeProfile(
        district_code=raw_district["district_code"],
        district_name=raw_district["district_name"],
        headquarters=raw_district.get("headquarters"),
        reporting_year=2022,
        source_agency="Delhi Police & National Crime Records Bureau (NCRB)",
        source_title="Crime in India 2022 & Delhi Police Annual Review",
        source_url="https://ncrb.gov.in/crime-in-india.html",
        source_table_or_page="Derived operational allocation from NCRB Table 1A.1 and Delhi Police Compendiums",
        publication_date="2023-12-03",
        geographic_resolution="police_district_estimate",
        data_status="derived_estimate",
        is_derived_estimate=True,
        derivation_method="Administrative operational allocation from aggregate Delhi totals. Not a direct census-tract enumeration.",
        rate_unavailable_reason="Official Census population denominators do not align with operational police district boundaries; per-capita rate calculation is suppressed to avoid distortions from daytime commuter populations.",
        limitations="District figures are operational research allocations. Police boundaries are unverified spatial approximations; not published as cadastral GIS layers by Delhi Police or Survey of India. Per-capita crime rates and rankings are strictly suppressed.",
        population_denominator_year=None,
        population_projection_2022=raw_district.get("population_projection_2022"),
        total_ipc_crimes_2022=raw_district["total_ipc_crimes_2022"],
        crime_rate_per_lakh=None,  # Suppressed: incompatible denominators
        clearance_rate_pct=raw_district.get("clearance_rate_pct"),
        historical_trend_ipc=raw_district.get("historical_trend_ipc", {}),
        categories_2022=categories,
        jurisdiction_polygon=boundary_polygon,
        boundary_type="spatial_approximation_reference",
        boundary_disclaimer="Approximated Police District Jurisdictional Zone. Macro reference geometry for locality mapping; not an official cadastral boundary published by Delhi Police or Survey of India.",
        state_ut_benchmark=state_ut_totals,
        provenance_details=provenance_details,
    )

    # 6. Query real emergency / police stations from OpenStreetMap via location service
    nearby_stations: List[PoliceStationFacility] = []
    try:
        if radius > 0:
            infra_summary = await fetch_overpass_infrastructure(latitude, longitude, radius=radius)
            if infra_summary and getattr(infra_summary, "facilities", None):
                radius_km = radius / 1000.0
                for fac in infra_summary.facilities:
                    if getattr(fac, "category", "") == "police":
                        flat = float(fac.latitude)
                        flon = float(fac.longitude)
                        dist_km = calculate_haversine_distance_km(latitude, longitude, flat, flon)
                        if dist_km is not None and dist_km <= radius_km + 0.005:
                            dist_str = f"{int(round(dist_km * 1000))} m" if dist_km < 1.0 else f"{dist_km:.2f} km"
                            nearby_stations.append(
                                PoliceStationFacility(
                                    osm_id=fac.id,
                                    name=fac.name,
                                    category="police",
                                    category_label="Police Station",
                                    latitude=flat,
                                    longitude=flon,
                                    distance_km=dist_km,
                                    formatted_distance=dist_str,
                                    source="OpenStreetMap Overpass API",
                                )
                            )
                nearby_stations.sort(key=lambda s: s.distance_km if s.distance_km is not None else float("inf"))
    except Exception as e:
        logger.warning("Overpass police stations query failed: %s", e)

    return LocalitySafetyResponse(
        status="active",
        latitude=latitude,
        longitude=longitude,
        address=address,
        search_radius_meters=radius,
        official_state_crime=official_state_crime,
        matched_district=district_profile,
        jurisdiction_match_type="approximate_spatial_reference",
        jurisdiction_disclaimer="Approximate macro reference territory. Official cadastral police district boundaries are not open data; property jurisdiction is indicative.",
        nearby_police_stations=nearby_stations,
        total_police_stations_in_radius=len(nearby_stations),
    )
