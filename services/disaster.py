import json
import logging
import math
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from backend.models.disaster import (
    DisasterHazardItem,
    DisasterLocationResponse,
    DisasterCompareRequest,
    DisasterCompareResponse,
)
from backend.services.crime_data import (
    point_in_polygon,
    calculate_haversine_distance_km,
)
from backend.services.air_quality import fetch_real_aqi_with_status

logger = logging.getLogger("nivas.services.disaster")

BASE_DIR = Path(__file__).resolve().parent.parent
HAZARD_GEOJSON_PATH = BASE_DIR / "data" / "disaster" / "delhi_hazard_zones.geojson"

_CACHED_HAZARDS: Optional[Dict[str, Any]] = None


def load_hazard_zones_geojson() -> Dict[str, Any]:
    global _CACHED_HAZARDS
    if _CACHED_HAZARDS is None:
        try:
            if HAZARD_GEOJSON_PATH.exists():
                with open(HAZARD_GEOJSON_PATH, "r", encoding="utf-8") as f:
                    _CACHED_HAZARDS = json.load(f)
            else:
                logger.error("Hazard zones GeoJSON not found at %s", HAZARD_GEOJSON_PATH)
                _CACHED_HAZARDS = {"features": []}
        except Exception as e:
            logger.error("Error loading hazard zones GeoJSON: %s", e)
            _CACHED_HAZARDS = {"features": []}
    return _CACHED_HAZARDS


async def get_disaster_hazards(
    latitude: float,
    longitude: float,
    address: Optional[str] = None,
) -> DisasterLocationResponse:
    """
    Retrieve grounded disaster, geological, and climate hazard evidence for given coordinates.
    Never fabricates a synthetic composite disaster score.
    """
    if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0) or math.isnan(latitude) or math.isnan(longitude):
        return DisasterLocationResponse(
            status="data_unavailable",
            latitude=latitude,
            longitude=longitude,
            address=address,
            error_message="Invalid coordinates provided for disaster hazard query.",
        )

    geojson = load_hazard_zones_geojson()
    features = geojson.get("features", [])

    hazards: List[DisasterHazardItem] = []
    spatial_layers: Dict[str, Any] = {}

    # 1. Seismic Hazard (BIS IS 1893:2016)
    hazards.append(
        DisasterHazardItem(
            hazard_type="earthquake",
            title="BIS Seismic Zone IV (High Damage Risk)",
            severity="high",
            category="static_zonal",
            source_agency="Bureau of Indian Standards (BIS IS 1893:2016) & National Center for Seismology (NCS)",
            source_url="https://seismo.gov.in/",
            description="All coordinates across the National Capital Territory of Delhi fall within Seismic Zone IV (Zone Factor 0.24, MSK Intensity VIII). Buildings require earthquake-resistant structural ductile detailing under IS 13920.",
            mitigation_notes="Verify structural stability certificate from a licensed structural engineer adhering to NBC 2016 and IS 1893 standards.",
            is_applicable=True,
            parameters={
                "seismic_zone": "IV",
                "zone_factor": 0.24,
                "expected_intensity_msk": "VIII",
            },
        )
    )

    # 2. Flooding & Yamuna Inundation Corridor
    flood_feature = next((f for f in features if f.get("properties", {}).get("hazard_type") == "flood"), None)
    in_flood_zone = False
    dist_to_flood_km = 999.0

    if flood_feature:
        spatial_layers["yamuna_flood_corridor"] = flood_feature
        flood_coords = flood_feature.get("geometry", {}).get("coordinates", [])
        if flood_coords:
            ring = flood_coords[0]
            in_flood_zone = point_in_polygon(longitude, latitude, ring)
            if not in_flood_zone:
                # Find min distance to polygon vertex
                for p in ring:
                    d = calculate_haversine_distance_km(latitude, longitude, p[1], p[0])
                    if d is not None and d < dist_to_flood_km:
                        dist_to_flood_km = d

    if in_flood_zone:
        hazards.append(
            DisasterHazardItem(
                hazard_type="flood",
                title="Yamuna River Active Floodplain Corridor",
                severity="critical",
                category="historical_vulnerability",
                source_agency="Central Water Commission (CWC) & Delhi Irrigation and Flood Control Department",
                source_url="https://cwc.gov.in/",
                description="Selected location lies within the Yamuna River active floodplain and drainage basin. Historically submerged during major Hathnikund releases (Warning Level: 204.50m, Danger Level: 205.33m, Historic HFL: 208.66m recorded July 2023).",
                mitigation_notes="Permanent construction is strictly regulated by National Green Tribunal (NGT) directives. Check building plinth elevation against historic flood level (208.66m).",
                is_applicable=True,
                parameters={
                    "warning_level_m": 204.50,
                    "danger_level_m": 205.33,
                    "historic_hfl_m": 208.66,
                    "status": "inside_floodplain",
                },
            )
        )
    elif dist_to_flood_km <= 2.5:
        hazards.append(
            DisasterHazardItem(
                hazard_type="flood",
                title="Yamuna River Buffer Zone (Marginal Risk)",
                severity="moderate",
                category="historical_vulnerability",
                source_agency="Central Water Commission (CWC)",
                source_url="https://cwc.gov.in/",
                description=f"Located approximately {dist_to_flood_km:.1f} km from the Yamuna floodplain corridor. Subject to localized storm sewer backpressure during high river stages.",
                mitigation_notes="Ensure stormwater drains have functional non-return check valves and basements are fitted with dual backflow protectors.",
                is_applicable=True,
                parameters={
                    "distance_to_floodplain_km": round(dist_to_flood_km, 2),
                    "status": "floodplain_buffer",
                },
            )
        )
    else:
        hazards.append(
            DisasterHazardItem(
                hazard_type="flood",
                title="Riverine Inundation Risk: Low (Upland Terrain)",
                severity="low",
                category="historical_vulnerability",
                source_agency="Central Water Commission (CWC)",
                source_url="https://cwc.gov.in/",
                description=f"Located {dist_to_flood_km:.1f} km from the Yamuna floodplain corridor on natural upland terrain. Direct riverine inundation is historically not documented.",
                mitigation_notes="Standard municipal stormwater drainage maintenance applies.",
                is_applicable=False,
                parameters={
                    "distance_to_floodplain_km": round(dist_to_flood_km, 2),
                    "status": "upland",
                },
            )
        )

    # 3. Urban Waterlogging Vulnerability
    waterlog_feature = next((f for f in features if f.get("properties", {}).get("hazard_type") == "waterlogging"), None)
    nearest_hotspot_km = 999.0
    if waterlog_feature:
        spatial_layers["waterlogging_hotspots"] = waterlog_feature
        hotspots = waterlog_feature.get("geometry", {}).get("coordinates", [])
        for pt in hotspots:
            d = calculate_haversine_distance_km(latitude, longitude, pt[1], pt[0])
            if d is not None and d < nearest_hotspot_km:
                nearest_hotspot_km = d

    if nearest_hotspot_km <= 1.2:
        hazards.append(
            DisasterHazardItem(
                hazard_type="waterlogging",
                title="Chronic Monsoon Waterlogging Exposure",
                severity="high",
                category="historical_vulnerability",
                source_agency="Delhi PWD & IIT Delhi Drainage Master Plan",
                source_url="https://pwd.delhigovt.nic.in/",
                description=f"Location is within {nearest_hotspot_km:.2f} km of a chronic PWD waterlogging depression/underpass. Surface runoff accumulation common during precipitation exceeding 40 mm/hr.",
                mitigation_notes="Verify basement water pumps, ramp coamings, and electrical transformer elevations above road grade.",
                is_applicable=True,
                parameters={"nearest_hotspot_km": round(nearest_hotspot_km, 2)},
            )
        )
    else:
        hazards.append(
            DisasterHazardItem(
                hazard_type="waterlogging",
                title="Monsoon Waterlogging: Low Direct Exposure",
                severity="low",
                category="historical_vulnerability",
                source_agency="Delhi PWD & Drainage Master Plan",
                source_url="https://pwd.delhigovt.nic.in/",
                description=f"No chronic PWD flood hotspots recorded within 1.2 km (nearest recorded hotspot: ~{nearest_hotspot_km:.1f} km).",
                mitigation_notes="Regular stormwater drain clearing before monsoon onset is recommended.",
                is_applicable=False,
                parameters={"nearest_hotspot_km": round(nearest_hotspot_km, 2)},
            )
        )

    # 4. Extreme Heat & Urban Heat Island Exposure
    hazards.append(
        DisasterHazardItem(
            hazard_type="heatwave",
            title="IMD Extreme Heat & Summer Heatwave Exposure",
            severity="moderate",
            category="static_zonal",
            source_agency="India Meteorological Department (IMD) & NDMA Heat Action Plan",
            source_url="https://mausam.imd.gov.in/",
            description="Delhi experiences peak summer temperatures of 42°C to 47°C during May–June. High-density concrete corridors exhibit +2°C to +4°C Urban Heat Island (UHI) elevation relative to vegetated ridge belts.",
            mitigation_notes="Evaluate building thermal orientation, roof reflective solar reflectance index (SRI cool roof coatings), and cross-ventilation.",
            is_applicable=True,
            parameters={
                "summer_peak_celsius": "42-47°C",
                "heatwave_threshold": "40°C or departure >= 4.5°C",
            },
        )
    )

    # 5. Heavy Rainfall Warning Thresholds
    hazards.append(
        DisasterHazardItem(
            hazard_type="rainfall",
            title="IMD Severe Monsoon Rainfall Thresholds",
            severity="info",
            category="static_zonal",
            source_agency="India Meteorological Department (IMD)",
            source_url="https://mausam.imd.gov.in/",
            description="IMD monsoon classification criteria: Heavy Rain (64.5 - 115.5 mm/day), Very Heavy Rain (115.6 - 204.4 mm/day), Extremely Heavy Rain (>204.4 mm/day).",
            mitigation_notes="Inspect building roof rain gutters, downspouts, and rainwater harvesting recharge pits prior to July monsoon onset.",
            is_applicable=True,
            parameters={
                "heavy_rain_mm": "64.5-115.5",
                "very_heavy_rain_mm": "115.6-204.4",
                "extreme_rain_mm": ">204.4",
            },
        )
    )

    locality_name = address.split(",")[0].strip() if address else "Selected Location"

    return DisasterLocationResponse(
        status="active",
        latitude=latitude,
        longitude=longitude,
        address=address,
        locality_name=locality_name,
        hazards=hazards,
        active_alerts_count=sum(1 for h in hazards if h.severity in ("critical", "high")),
        spatial_layers=spatial_layers,
    )


async def compare_disaster_hazards(
    request: DisasterCompareRequest,
) -> DisasterCompareResponse:
    """
    Compare disaster hazard exposures between Location A and Location B side-by-side.
    Does not invent a synthetic comparative grade; provides evidence-by-evidence contrasts.
    """
    loc_a_data = request.location_a
    loc_b_data = request.location_b

    lat_a = float(loc_a_data.get("latitude", 28.5921))
    lon_a = float(loc_a_data.get("longitude", 77.0460))
    addr_a = loc_a_data.get("address", "Location A")

    lat_b = float(loc_b_data.get("latitude", 28.6517))
    lon_b = float(loc_b_data.get("longitude", 77.1583))
    addr_b = loc_b_data.get("address", "Location B")

    resp_a = await get_disaster_hazards(lat_a, lon_a, addr_a)
    resp_b = await get_disaster_hazards(lat_b, lon_b, addr_b)

    # Build side-by-side comparative points
    comparison_points = []

    # 1. Seismic Zone
    comparison_points.append({
        "hazard_type": "earthquake",
        "title": "Seismic Exposure",
        "summary": "Both locations are in BIS Seismic Zone IV (High Damage Risk Zone). Equal engineering standard requirements apply.",
        "location_a_verdict": "Zone IV (High)",
        "location_b_verdict": "Zone IV (High)",
    })

    # 2. Flood Risk
    flood_a = next((h for h in resp_a.hazards if h.hazard_type == "flood"), None)
    flood_b = next((h for h in resp_b.hazards if h.hazard_type == "flood"), None)
    flood_a_sev = flood_a.severity if flood_a else "low"
    flood_b_sev = flood_b.severity if flood_b else "low"

    if flood_a_sev == flood_b_sev:
        flood_summary = f"Both locations have similar documented riverine inundation exposure ({flood_a_sev})."
    else:
        flood_summary = f"{resp_a.locality_name} is evaluated as '{flood_a_sev}' while {resp_b.locality_name} is evaluated as '{flood_b_sev}' for Yamuna river floodplain proximity."

    comparison_points.append({
        "hazard_type": "flood",
        "title": "Riverine Flood Risk",
        "summary": flood_summary,
        "location_a_verdict": flood_a.title if flood_a else "Low",
        "location_b_verdict": flood_b.title if flood_b else "Low",
    })

    # 3. Waterlogging Risk
    waterlog_a = next((h for h in resp_a.hazards if h.hazard_type == "waterlogging"), None)
    waterlog_b = next((h for h in resp_b.hazards if h.hazard_type == "waterlogging"), None)
    comparison_points.append({
        "hazard_type": "waterlogging",
        "title": "Urban Monsoon Waterlogging",
        "summary": f"Proximity to chronic PWD drainage depression: {resp_a.locality_name} (~{waterlog_a.parameters.get('nearest_hotspot_km', 'N/A')} km) vs {resp_b.locality_name} (~{waterlog_b.parameters.get('nearest_hotspot_km', 'N/A')} km).",
        "location_a_verdict": waterlog_a.title if waterlog_a else "Low",
        "location_b_verdict": waterlog_b.title if waterlog_b else "Low",
    })

    return DisasterCompareResponse(
        status="active",
        location_a=resp_a,
        location_b=resp_b,
        comparative_analysis=comparison_points,
        disclaimers=[
            "Comparative analysis uses identical BIS, CWC, and PWD dataset definitions for both candidate locations.",
            "Differences in documented risk reflect spatial distance to river floodplains and surveyed municipal drainage bottlenecks.",
            "No location can be certified completely disaster-free; all structures in Delhi require seismic compliance.",
        ],
    )
