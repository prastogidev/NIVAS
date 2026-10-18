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
    """
    geojson = load_districts_geojson()
    features = geojson.get("features", [])

    # 1. Exact point-in-polygon test
    for feat in features:
        geom = feat.get("geometry", {})
        props = feat.get("properties", {})
        dcode = props.get("district_code")
        coords = geom.get("coordinates", [])

        if geom.get("type") == "Polygon" and coords:
            ring = coords[0]
            if point_in_polygon(longitude, latitude, ring):
                return dcode, ring

    # 2. If within general Delhi boundary box, fallback to closest district centroid
    if 28.35 <= latitude <= 28.95 and 76.80 <= longitude <= 77.40:
        min_dist = float("inf")
        best_match = None
        for feat in features:
            geom = feat.get("geometry", {})
            props = feat.get("properties", {})
            dcode = props.get("district_code")
            coords = geom.get("coordinates", [])
            if geom.get("type") == "Polygon" and coords:
                ring = coords[0]
                # Calculate centroid
                lons = [p[0] for p in ring]
                lats = [p[1] for p in ring]
                cent_lon = sum(lons) / len(lons)
                cent_lat = sum(lats) / len(lats)
                dist = (latitude - cent_lat) ** 2 + (longitude - cent_lon) ** 2
                if dist < min_dist:
                    min_dist = dist
                    best_match = (dcode, ring)
        return best_match

    return None


async def get_locality_safety_data(
    latitude: float,
    longitude: float,
    address: Optional[str] = None,
    radius: int = 1200,
) -> LocalitySafetyResponse:
    """
    Produce truthful, evidence-backed safety and historical crime intelligence for given coordinates.
    Never fabricates street-level incident coordinates or artificial composite safety ratings.
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

    # 2. Resolve Police District
    resolved = resolve_police_district(latitude, longitude)
    if not resolved:
        return LocalitySafetyResponse(
            status="unknown_jurisdiction",
            latitude=latitude,
            longitude=longitude,
            address=address,
            search_radius_meters=radius,
            error_message="Coordinates fall outside the National Capital Territory of Delhi police district coverage.",
        )

    district_code, boundary_polygon = resolved
    baseline = load_crime_baseline()
    districts_data = baseline.get("districts", {})
    raw_district = districts_data.get(district_code)

    if not raw_district:
        return LocalitySafetyResponse(
            status="data_unavailable",
            latitude=latitude,
            longitude=longitude,
            address=address,
            search_radius_meters=radius,
            error_message=f"Official crime records for district {district_code} are not indexed.",
        )

    # 3. Build DistrictCrimeProfile
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

    district_profile = DistrictCrimeProfile(
        district_code=raw_district["district_code"],
        district_name=raw_district["district_name"],
        headquarters=raw_district.get("headquarters"),
        reporting_year=2022,
        source_agency="Delhi Police & National Crime Records Bureau (NCRB)",
        source_document_url="https://ncrb.gov.in/crime-in-india.html",
        publication_date="2023-12-03",
        geographic_resolution="police_district",
        population_projection_2022=raw_district.get("population_projection_2022"),
        total_ipc_crimes_2022=raw_district["total_ipc_crimes_2022"],
        crime_rate_per_lakh=raw_district.get("crime_rate_per_lakh"),
        clearance_rate_pct=raw_district.get("clearance_rate_pct"),
        historical_trend_ipc=raw_district.get("historical_trend_ipc", {}),
        categories_2022=categories,
        jurisdiction_polygon=boundary_polygon,
    )

    # 4. Query real emergency / police stations from OpenStreetMap via location service
    nearby_stations: List[PoliceStationFacility] = []
    try:
        # If radius > 0, fetch real infrastructure nodes from Overpass
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
        matched_district=district_profile,
        nearby_police_stations=nearby_stations,
        total_police_stations_in_radius=len(nearby_stations),
    )
