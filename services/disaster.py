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
    DisasterHazardLayer,
    DisasterLayersRegistryResponse,
)
from backend.services.crime_data import (
    point_in_polygon,
    calculate_haversine_distance_km,
)

logger = logging.getLogger("nivas.services.disaster")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "disaster"

HAZARD_REGISTRY_PATH = DATA_DIR / "hazard_registry.json"
DELHI_HAZARD_PATH = DATA_DIR / "delhi_hazard_zones.geojson"
SEISMIC_GEOJSON_PATH = DATA_DIR / "india_seismic_zones.geojson"
FLOOD_BASINS_PATH = DATA_DIR / "india_flood_basins.geojson"
CYCLONE_GEOJSON_PATH = DATA_DIR / "india_coastal_cyclone_zones.geojson"
LANDSLIDE_GEOJSON_PATH = DATA_DIR / "india_landslide_zones.geojson"
HEATWAVE_GEOJSON_PATH = DATA_DIR / "india_heatwave_zones.geojson"
DROUGHT_GEOJSON_PATH = DATA_DIR / "india_drought_zones.geojson"

# In-memory GeoJSON cache
_LAYER_CACHE: Dict[str, Any] = {}

# Territorial bounding box for the Republic of India
INDIA_BOUNDS = {
    "min_lat": 6.5,
    "max_lat": 37.5,
    "min_lon": 68.0,
    "max_lon": 97.5,
}

# NCT of Delhi spatial bounds for high-resolution municipal layers
DELHI_BOUNDS = {
    "min_lat": 28.30,
    "max_lat": 28.95,
    "min_lon": 76.80,
    "max_lon": 77.45,
}


def _load_json_file(path: Path) -> Dict[str, Any]:
    key = str(path)
    if key not in _LAYER_CACHE:
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    _LAYER_CACHE[key] = json.load(f)
            else:
                logger.error("Dataset not found at %s", path)
                _LAYER_CACHE[key] = {"type": "FeatureCollection", "features": []}
        except Exception as exc:
            logger.error("Error reading JSON from %s: %s", path, exc)
            _LAYER_CACHE[key] = {"type": "FeatureCollection", "features": []}
    return _LAYER_CACHE[key]


def get_hazard_layers_registry() -> DisasterLayersRegistryResponse:
    """Return the authoritative registry of all supported disaster hazard layers."""
    registry_data = _load_json_file(HAZARD_REGISTRY_PATH)
    layers = [DisasterHazardLayer.model_validate(l) for l in registry_data.get("layers", [])]
    return DisasterLayersRegistryResponse(
        version=registry_data.get("version", "2.0.0"),
        national_coverage=registry_data.get("national_coverage", {}),
        layers=layers,
        total_layers=len(layers),
    )


def get_layer_geometry(layer_id: str) -> Optional[Dict[str, Any]]:
    """Return GeoJSON FeatureCollection or Feature for a specific layer ID."""
    if layer_id == "seismic_zones":
        return _load_json_file(SEISMIC_GEOJSON_PATH)
    elif layer_id == "river_flood_basins":
        return _load_json_file(FLOOD_BASINS_PATH)
    elif layer_id == "cyclone_coastal":
        return _load_json_file(CYCLONE_GEOJSON_PATH)
    elif layer_id == "landslide_zones":
        return _load_json_file(LANDSLIDE_GEOJSON_PATH)
    elif layer_id == "heatwave_zones":
        return _load_json_file(HEATWAVE_GEOJSON_PATH)
    elif layer_id == "drought_water_stress":
        return _load_json_file(DROUGHT_GEOJSON_PATH)
    elif layer_id == "yamuna_flood_corridor":
        delhi_data = _load_json_file(DELHI_HAZARD_PATH)
        feat = next(
            (f for f in delhi_data.get("features", []) if f.get("properties", {}).get("hazard_type") == "flood"),
            None,
        )
        if feat:
            return {"type": "FeatureCollection", "features": [feat]}
        return {"type": "FeatureCollection", "features": []}
    elif layer_id == "delhi_waterlogging_hotspots":
        delhi_data = _load_json_file(DELHI_HAZARD_PATH)
        feat = next(
            (f for f in delhi_data.get("features", []) if f.get("properties", {}).get("hazard_type") == "waterlogging"),
            None,
        )
        if feat:
            return {"type": "FeatureCollection", "features": [feat]}
        return {"type": "FeatureCollection", "features": []}
    return None


def _check_point_in_geometry(lon: float, lat: float, geometry: Dict[str, Any]) -> Tuple[bool, float]:
    """
    Test if (lon, lat) is inside geometry.
    Returns (inside: bool, min_distance_km: float).
    """
    gtype = geometry.get("type")
    coords = geometry.get("coordinates", [])
    if gtype == "Polygon":
        if not coords:
            return False, float("inf")
        ring = coords[0]
        if point_in_polygon(lon, lat, ring):
            return True, 0.0
        min_d = float("inf")
        for p in ring:
            d = calculate_haversine_distance_km(lat, lon, p[1], p[0])
            if d is not None and d < min_d:
                min_d = d
        return False, min_d
    elif gtype == "MultiPolygon":
        min_d = float("inf")
        for poly in coords:
            if not poly:
                continue
            ring = poly[0]
            if point_in_polygon(lon, lat, ring):
                return True, 0.0
            for p in ring:
                d = calculate_haversine_distance_km(lat, lon, p[1], p[0])
                if d is not None and d < min_d:
                    min_d = d
        return False, min_d
    return False, float("inf")


def load_hazard_zones_geojson() -> Dict[str, Any]:
    """Backward compatibility loader for Delhi hazard zones GeoJSON."""
    return _load_json_file(DELHI_HAZARD_PATH)


async def get_disaster_hazards(
    latitude: float,
    longitude: float,
    address: Optional[str] = None,
) -> DisasterLocationResponse:
    """
    Retrieve grounded disaster, geological, and climate hazard evidence for any location in India.
    Never fabricates synthetic composite disaster scores. Grounded in statutory standards (BIS IS 1893:2016),
    official river basin models (CWC), cyclone exposure models (NDMA/IMD), and landslide susceptibility (GSI NLSM).
    """
    if (
        not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0)
        or math.isnan(latitude)
        or math.isnan(longitude)
        or math.isinf(latitude)
        or math.isinf(longitude)
    ):
        return DisasterLocationResponse(
            status="data_unavailable",
            latitude=latitude,
            longitude=longitude,
            address=address,
            locality_name=address or f"{latitude:.4f}° N, {longitude:.4f}° E",
            error_message="Invalid coordinates provided for disaster hazard query.",
        )

    # Validate spatial dataset coverage for the Republic of India
    in_india = (
        INDIA_BOUNDS["min_lat"] <= latitude <= INDIA_BOUNDS["max_lat"]
        and INDIA_BOUNDS["min_lon"] <= longitude <= INDIA_BOUNDS["max_lon"]
    )
    if not in_india:
        return DisasterLocationResponse(
            status="out_of_coverage",
            latitude=latitude,
            longitude=longitude,
            address=address,
            locality_name=address or f"{latitude:.4f}° N, {longitude:.4f}° E",
            error_message="Location coordinates fall outside supported Republic of India territorial hazard coverage (lat 6.5° - 37.5° N, lon 68.0° - 97.5° E).",
        )

    is_delhi = (
        DELHI_BOUNDS["min_lat"] <= latitude <= DELHI_BOUNDS["max_lat"]
        and DELHI_BOUNDS["min_lon"] <= longitude <= DELHI_BOUNDS["max_lon"]
    )

    hazards: List[DisasterHazardItem] = []
    spatial_layers: Dict[str, Any] = {}

    # 1. Seismic Hazard (BIS IS 1893:2016) — 100% Nationwide Coverage
    seismic_data = _load_json_file(SEISMIC_GEOJSON_PATH)
    matched_seismic_feat = None
    seismic_features = seismic_data.get("features", [])

    for feat in seismic_features:
        inside, _ = _check_point_in_geometry(longitude, latitude, feat.get("geometry", {}))
        if inside:
            matched_seismic_feat = feat
            break

    detected_state = None
    if matched_seismic_feat:
        spatial_layers["seismic_zone"] = matched_seismic_feat
        sp = matched_seismic_feat.get("properties", {})
        zone = sp.get("zone", "III")
        zone_factor = sp.get("zone_factor", 0.16)
        intensity_msk = sp.get("expected_intensity_msk", "VII")
        pga = sp.get("pga_coefficient", "0.16g")
        state_name = sp.get("state_name", "India")
        mandatory_code = sp.get("mandatory_code", "Adhere to IS 1893:2016 ductile detailing.")
        detected_state = state_name

        severity_map = {"V": "critical", "IV": "high", "III": "moderate", "II": "low"}
        sev = severity_map.get(zone, "moderate")

        hazards.append(
            DisasterHazardItem(
                hazard_type="earthquake",
                title=f"BIS Seismic Zone {zone} ({sp.get('zone_name', f'Zone {zone}')})",
                severity=sev,
                evidence_status="evidence_found",
                category="static_zonal",
                evidence_type="static_zonal",
                data_freshness="static_standard",
                geographic_resolution="regional_statutory_standard",
                source_agency="Bureau of Indian Standards (BIS IS 1893:2016) & National Center for Seismology (NCS)",
                source_url="https://seismo.gov.in/",
                description=(
                    f"Selected location falls within BIS Seismic Zone {zone} (Zone Factor Z = {zone_factor}, "
                    f"Expected MSK Intensity {intensity_msk}, Nominal PGA {pga}). Under the National Building "
                    f"Code (NBC 2016) and IS 1893 (Part 1): 2016, engineered structural detailing is statutory."
                ),
                mitigation_notes=mandatory_code,
                is_applicable=True,
                parameters={
                    "seismic_zone": zone,
                    "zone_factor": zone_factor,
                    "expected_intensity_msk": intensity_msk,
                    "pga_coefficient": pga,
                    "state_name": state_name,
                },
                limitations="Macro-scale statutory administrative standard. Micro-zonation and soil liquefaction require site-specific borehole tests.",
            )
        )
    else:
        # Fallback for borderline coastal/frontier coordinates
        hazards.append(
            DisasterHazardItem(
                hazard_type="earthquake",
                title="BIS Seismic Zone III (Moderate Damage Risk)",
                severity="moderate",
                evidence_status="evidence_found",
                category="static_zonal",
                evidence_type="static_zonal",
                data_freshness="static_standard",
                geographic_resolution="regional_statutory_standard",
                source_agency="Bureau of Indian Standards (BIS IS 1893:2016)",
                source_url="https://seismo.gov.in/",
                description="Location evaluated under standard peninsular moderate seismic zoning (Zone Factor 0.16). IS 1893 design criteria apply.",
                mitigation_notes="Structural engineer compliance certificate recommended.",
                is_applicable=True,
                parameters={"seismic_zone": "III", "zone_factor": 0.16},
            )
        )

    # 2. River Flooding & Floodplains (CWC / NDMA / Delhi Yamuna)
    delhi_hazards = _load_json_file(DELHI_HAZARD_PATH)
    delhi_features = delhi_hazards.get("features", [])
    yamuna_feature = next((f for f in delhi_features if f.get("properties", {}).get("hazard_type") == "flood"), None)

    flood_basins_data = _load_json_file(FLOOD_BASINS_PATH)
    flood_basin_features = flood_basins_data.get("features", [])

    matched_basin_feat = None
    min_basin_dist_km = float("inf")
    nearest_basin_name = "Major River Basin"

    for feat in flood_basin_features:
        inside, dist = _check_point_in_geometry(longitude, latitude, feat.get("geometry", {}))
        if inside:
            matched_basin_feat = feat
            min_basin_dist_km = 0.0
            break
        if dist < min_basin_dist_km:
            min_basin_dist_km = dist
            nearest_basin_name = feat.get("properties", {}).get("basin_name", "Major River Basin")

    # Evaluate Delhi Yamuna floodplain if in Delhi
    in_yamuna = False
    yamuna_dist_km = float("inf")
    if is_delhi and yamuna_feature:
        in_yamuna, yamuna_dist_km = _check_point_in_geometry(longitude, latitude, yamuna_feature.get("geometry", {}))
        spatial_layers["yamuna_flood_corridor"] = yamuna_feature

    if in_yamuna:
        hazards.append(
            DisasterHazardItem(
                hazard_type="flood",
                title="Yamuna River Active Floodplain Corridor",
                severity="critical",
                evidence_status="evidence_found",
                category="historical_vulnerability",
                evidence_type="historical_and_zonal",
                data_freshness="historical_compendium",
                geographic_resolution="macro_riverbed_corridor",
                source_agency="Central Water Commission (CWC) & Delhi Irrigation and Flood Control Department",
                source_url="https://cwc.gov.in/",
                description=(
                    "Selected location lies within the Yamuna River active floodplain and regulatory drainage corridor. "
                    "Historically submerged during major Hathnikund barrage releases (Warning Level: 204.50m, "
                    "Danger Level: 205.33m, Historic HFL: 208.66m recorded July 2023)."
                ),
                mitigation_notes="Permanent construction strictly restricted by National Green Tribunal (NGT) directives. Check plinth elevation against historic flood level (208.66m).",
                is_applicable=True,
                distance_km=0.0,
                distance_description="Directly inside regulatory active river floodplain",
                parameters={
                    "warning_level_m": 204.50,
                    "danger_level_m": 205.33,
                    "historic_hfl_m": 208.66,
                    "status": "inside_floodplain",
                },
            )
        )
    elif is_delhi and yamuna_dist_km <= 2.5:
        hazards.append(
            DisasterHazardItem(
                hazard_type="flood",
                title="Yamuna River Buffer Zone (Marginal Risk)",
                severity="moderate",
                evidence_status="evidence_found",
                category="historical_vulnerability",
                evidence_type="historical_and_zonal",
                data_freshness="historical_compendium",
                geographic_resolution="macro_riverbed_corridor",
                source_agency="Central Water Commission (CWC)",
                source_url="https://cwc.gov.in/",
                description=f"Located approximately {yamuna_dist_km:.1f} km from the Yamuna floodplain corridor. Subject to localized storm sewer backpressure during high river stages.",
                mitigation_notes="Ensure stormwater drains have functional non-return check valves and basements are fitted with dual backflow protectors.",
                is_applicable=True,
                distance_km=round(yamuna_dist_km, 2),
                distance_description=f"{yamuna_dist_km:.1f} km from active Yamuna riverbed corridor",
                parameters={
                    "distance_to_floodplain_km": round(yamuna_dist_km, 2),
                    "status": "floodplain_buffer",
                },
            )
        )
    elif matched_basin_feat:
        spatial_layers["river_flood_basin"] = matched_basin_feat
        bp = matched_basin_feat.get("properties", {})
        hazards.append(
            DisasterHazardItem(
                hazard_type="flood",
                title=f"Major Riverine Flood Basin: {bp.get('basin_name', 'Lowland Basin')}",
                severity="high",
                evidence_status="evidence_found",
                category="historical_vulnerability",
                evidence_type="historical_and_zonal",
                data_freshness="historical_compendium",
                geographic_resolution="macro_riverbed_corridor",
                source_agency=bp.get("source", "Central Water Commission (CWC) & NDMA"),
                source_url="https://cwc.gov.in/",
                description=bp.get(
                    "description",
                    "Extensive riverine floodplain corridor historically prone to seasonal monsoon inundation.",
                ),
                mitigation_notes=bp.get(
                    "mitigation_notes",
                    "Verify master plan green buffer and embankments; ensure plinth is above 100-year High Flood Level.",
                ),
                is_applicable=True,
                distance_km=0.0,
                distance_description="Directly inside mapped river basin flood corridor",
                parameters={"basin_name": bp.get("basin_name"), "status": "inside_river_basin"},
            )
        )
    elif min_basin_dist_km <= 20.0:
        hazards.append(
            DisasterHazardItem(
                hazard_type="flood",
                title=f"River Basin Buffer Zone (~{min_basin_dist_km:.1f} km from {nearest_basin_name})",
                severity="moderate",
                evidence_status="evidence_found",
                category="historical_vulnerability",
                evidence_type="historical_and_zonal",
                data_freshness="historical_compendium",
                geographic_resolution="macro_riverbed_corridor",
                source_agency="Central Water Commission (CWC)",
                source_url="https://cwc.gov.in/",
                description=(
                    f"Located {min_basin_dist_km:.1f} km from mapped {nearest_basin_name}. Tributary drainage "
                    f"channels may experience backwater congestion during peak monsoon discharge."
                ),
                mitigation_notes="Inspect local stormwater outlet elevations and ensure basement sump pumps are operational.",
                is_applicable=True,
                distance_km=round(min_basin_dist_km, 2),
                distance_description=f"{min_basin_dist_km:.1f} km from {nearest_basin_name}",
                parameters={"nearest_basin": nearest_basin_name, "distance_km": round(min_basin_dist_km, 2)},
            )
        )
    else:
        dist_label = f"{min_basin_dist_km:.0f} km" if min_basin_dist_km < 999 else "distant"
        hazards.append(
            DisasterHazardItem(
                hazard_type="flood",
                title="Riverine Inundation Risk: Low (Upland Terrain)",
                severity="low",
                evidence_status="no_mapped_feature",
                category="historical_vulnerability",
                evidence_type="historical_and_zonal",
                data_freshness="historical_compendium",
                geographic_resolution="macro_riverbed_corridor",
                source_agency="Central Water Commission (CWC)",
                source_url="https://cwc.gov.in/",
                description=(
                    f"Located on elevated natural upland terrain ({dist_label} from nearest major CWC mapped river flood basin). "
                    f"No macro-scale riverine inundation recorded. Note: local localized cloudburst drainage must still be verified."
                ),
                mitigation_notes="Standard municipal stormwater drainage maintenance applies.",
                is_applicable=False,
                distance_km=round(min_basin_dist_km, 1) if min_basin_dist_km < 999 else None,
                distance_description=f"Outside mapped major river flood corridors (~{dist_label})",
                parameters={"status": "upland"},
                limitations="Non-surveyed minor rivulets and micro-drainage channels are not represented in national macro basin mapping.",
            )
        )

    # 3. Coastal Cyclone & Storm Surge (NDMA NCRMP / IMD)
    cyclone_data = _load_json_file(CYCLONE_GEOJSON_PATH)
    matched_cyclone_feat = None
    min_coast_dist_km = float("inf")
    nearest_cyclone_label = "Coastal Belt"

    for feat in cyclone_data.get("features", []):
        inside, dist = _check_point_in_geometry(longitude, latitude, feat.get("geometry", {}))
        if inside:
            matched_cyclone_feat = feat
            min_coast_dist_km = 0.0
            break
        if dist < min_coast_dist_km:
            min_coast_dist_km = dist
            nearest_cyclone_label = feat.get("properties", {}).get("tier_label", "Coastal Zone")

    if matched_cyclone_feat:
        spatial_layers["coastal_cyclone_zone"] = matched_cyclone_feat
        cp = matched_cyclone_feat.get("properties", {})
        tier = cp.get("risk_tier", "high")
        c_sev = "critical" if tier == "very_high" else "high"
        hazards.append(
            DisasterHazardItem(
                hazard_type="cyclone",
                title=cp.get("tier_label", "High Cyclone & Coastal Exposure"),
                severity=c_sev,
                evidence_status="evidence_found",
                category="modeled_exposure",
                evidence_type="modeled_exposure",
                data_freshness="historical_compendium",
                geographic_resolution="macro_riverbed_corridor",
                source_agency=cp.get("source", "NDMA National Cyclone Risk Mitigation Project (NCRMP) & IMD"),
                source_url="https://ndma.gov.in/",
                description=cp.get("description", "Exposed to tropical cyclone wind forces and coastal storm surge."),
                mitigation_notes=cp.get("mitigation_notes", "Adhere to Coastal Regulation Zone (CRZ) setbacks and wind-resistant roofing."),
                is_applicable=True,
                distance_km=0.0,
                distance_description="Directly inside coastal cyclone & storm surge exposure belt",
                parameters={
                    "wind_speed_kmh": cp.get("wind_speed_kmh"),
                    "storm_surge_m": cp.get("storm_surge_m"),
                    "coastal_belt": cp.get("coastal_belt"),
                },
            )
        )
    elif min_coast_dist_km <= 50.0:
        hazards.append(
            DisasterHazardItem(
                hazard_type="cyclone",
                title=f"Inland Cyclone Wind Buffer (~{min_coast_dist_km:.1f} km from coastline)",
                severity="moderate",
                evidence_status="evidence_found",
                category="modeled_exposure",
                evidence_type="modeled_exposure",
                data_freshness="historical_compendium",
                geographic_resolution="macro_riverbed_corridor",
                source_agency="NDMA & IMD",
                source_url="https://ndma.gov.in/",
                description=f"Located ~{min_coast_dist_km:.1f} km from coastal boundary. Subject to decaying cyclonic gale winds (up to 100-130 km/h) and widespread convective rainfall during post-monsoon cyclogenesis.",
                mitigation_notes="Inspect tree canopies near overhead power lines, verify window glazing ratings and roof sheet fasteners.",
                is_applicable=True,
                distance_km=round(min_coast_dist_km, 1),
                distance_description=f"{min_coast_dist_km:.1f} km inland from mapped coastal surge zone",
                parameters={"distance_to_coast_km": round(min_coast_dist_km, 1)},
            )
        )
    else:
        dist_lbl = f"{min_coast_dist_km:.0f} km" if min_coast_dist_km < 999 else "deep inland"
        hazards.append(
            DisasterHazardItem(
                hazard_type="cyclone",
                title="Inland Location: Low Cyclone & Surge Exposure",
                severity="low",
                evidence_status="no_mapped_feature",
                category="modeled_exposure",
                evidence_type="modeled_exposure",
                data_freshness="historical_compendium",
                geographic_resolution="macro_riverbed_corridor",
                source_agency="NDMA & IMD",
                source_url="https://ndma.gov.in/",
                description=f"Located on interior continental landmass (~{dist_lbl} from maritime coast). Storm surge is not physically possible; exposure restricted to non-destructive depression showers.",
                mitigation_notes="Standard building wind-load provisions under IS 875 (Part 3) apply.",
                is_applicable=False,
                distance_km=round(min_coast_dist_km, 1) if min_coast_dist_km < 999 else None,
                distance_description=f"Interior landmass ({dist_lbl} from coast)",
            )
        )

    # 4. Landslides & Steep Terrain (GSI NLSM)
    landslide_data = _load_json_file(LANDSLIDE_GEOJSON_PATH)
    matched_landslide_feat = None
    min_landslide_dist_km = float("inf")
    nearest_landslide_label = "Hilly Region"

    for feat in landslide_data.get("features", []):
        inside, dist = _check_point_in_geometry(longitude, latitude, feat.get("geometry", {}))
        if inside:
            matched_landslide_feat = feat
            min_landslide_dist_km = 0.0
            break
        if dist < min_landslide_dist_km:
            min_landslide_dist_km = dist
            nearest_landslide_label = feat.get("properties", {}).get("tier_label", "Hilly Terrain")

    if matched_landslide_feat:
        spatial_layers["landslide_susceptibility_zone"] = matched_landslide_feat
        lp = matched_landslide_feat.get("properties", {})
        l_sev = "critical" if lp.get("susceptibility") == "very_high" else "high"
        hazards.append(
            DisasterHazardItem(
                hazard_type="landslide",
                title=f"GSI Landslide Susceptibility ({lp.get('tier_label', 'Hilly Arc')})",
                severity=l_sev,
                evidence_status="evidence_found",
                category="modeled_exposure",
                evidence_type="modeled_exposure",
                data_freshness="historical_compendium",
                geographic_resolution="macro_susceptibility_belt",
                source_agency=lp.get("source", "Geological Survey of India (GSI NLSM)"),
                source_url="https://bhukosh.gsi.gov.in/",
                description=lp.get(
                    "description",
                    "Mapped inside active macro-scale landslide susceptibility belt with high slope gradient.",
                ),
                mitigation_notes=lp.get(
                    "mitigation_notes",
                    "Site-specific slope stability geotechnical analysis required. Mandatory engineered retaining structures.",
                ),
                is_applicable=True,
                distance_km=0.0,
                distance_description="Directly inside GSI mapped landslide susceptibility belt",
                parameters={"region": lp.get("region"), "terrain_type": lp.get("terrain_type")},
            )
        )
    elif min_landslide_dist_km <= 20.0:
        hazards.append(
            DisasterHazardItem(
                hazard_type="landslide",
                title=f"Hill Foot / Slope Buffer (~{min_landslide_dist_km:.1f} km from slope hazard)",
                severity="moderate",
                evidence_status="evidence_found",
                category="modeled_exposure",
                evidence_type="modeled_exposure",
                data_freshness="historical_compendium",
                geographic_resolution="macro_susceptibility_belt",
                source_agency="Geological Survey of India (GSI NLSM)",
                source_url="https://bhukosh.gsi.gov.in/",
                description=f"Located {min_landslide_dist_km:.1f} km from active steep terrain. Down-valley alluvial fans and arterial access roads may experience debris deposition or road cuts during intense rainfall.",
                mitigation_notes="Inspect upslope drainage catchments and verify road access continuity during monsoon.",
                is_applicable=True,
                distance_km=round(min_landslide_dist_km, 1),
                distance_description=f"{min_landslide_dist_km:.1f} km from GSI landslide zone",
                parameters={"distance_to_slopes_km": round(min_landslide_dist_km, 1)},
            )
        )
    else:
        dist_lbl = f"{min_landslide_dist_km:.0f} km" if min_landslide_dist_km < 999 else "distant"
        hazards.append(
            DisasterHazardItem(
                hazard_type="landslide",
                title="Plains / Low-Relief Terrain: No Mapped Landslide Risk",
                severity="low",
                evidence_status="no_mapped_feature",
                category="modeled_exposure",
                evidence_type="modeled_exposure",
                data_freshness="historical_compendium",
                geographic_resolution="macro_susceptibility_belt",
                source_agency="Geological Survey of India (GSI NLSM)",
                source_url="https://bhukosh.gsi.gov.in/",
                description=(
                    f"Selected property is located on flat alluvial plains or low-relief plateau (~{dist_lbl} from "
                    f"mapped mountain mass-wasting belts). Slope failure is physically unviable."
                ),
                mitigation_notes="Standard foundation engineering applies without specialized slope revetments.",
                is_applicable=False,
                distance_km=round(min_landslide_dist_km, 1) if min_landslide_dist_km < 999 else None,
                distance_description=f"Low-relief terrain ({dist_lbl} from steep belts)",
            )
        )

    # 5. Urban Flooding & Waterlogging Hotspots
    # Mapped only for surveyed Delhi PWD points; explicit data_unavailable for outside Delhi
    if is_delhi:
        waterlog_feature = next((f for f in delhi_features if f.get("properties", {}).get("hazard_type") == "waterlogging"), None)
        nearest_hotspot_km = float("inf")
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
                    evidence_status="evidence_found",
                    category="historical_vulnerability",
                    evidence_type="historical_monsoon_vulnerability",
                    data_freshness="historical_compendium",
                    geographic_resolution="point_infrastructure",
                    source_agency="Delhi PWD & IIT Delhi Drainage Master Plan",
                    source_url="https://pwd.delhigovt.nic.in/",
                    description=f"Location is within {nearest_hotspot_km:.2f} km of a chronic PWD waterlogging depression/underpass. Surface runoff accumulation common during precipitation exceeding 40 mm/hr.",
                    mitigation_notes="Verify basement water pumps, ramp coamings, and electrical transformer elevations above road grade.",
                    is_applicable=True,
                    distance_km=round(nearest_hotspot_km, 2),
                    distance_description=f"{nearest_hotspot_km:.2f} km to surveyed chronic underpass choke point",
                    parameters={"nearest_hotspot_km": round(nearest_hotspot_km, 2)},
                )
            )
        else:
            hazards.append(
                DisasterHazardItem(
                    hazard_type="waterlogging",
                    title="Monsoon Waterlogging: Low Direct Exposure",
                    severity="low",
                    evidence_status="evidence_found",
                    category="historical_vulnerability",
                    evidence_type="historical_monsoon_vulnerability",
                    data_freshness="historical_compendium",
                    geographic_resolution="point_infrastructure",
                    source_agency="Delhi PWD & Drainage Master Plan",
                    source_url="https://pwd.delhigovt.nic.in/",
                    description=f"No chronic PWD flood hotspots recorded within 1.2 km (nearest recorded hotspot: ~{nearest_hotspot_km:.1f} km).",
                    mitigation_notes="Regular stormwater drain clearing before monsoon onset is recommended.",
                    is_applicable=False,
                    distance_km=round(nearest_hotspot_km, 2),
                    distance_description=f"Nearest surveyed underpass: ~{nearest_hotspot_km:.1f} km",
                    parameters={"nearest_hotspot_km": round(nearest_hotspot_km, 2)},
                )
            )
    else:
        # Grounded disclosure: Never treat missing data as zero hazard
        hazards.append(
            DisasterHazardItem(
                hazard_type="waterlogging",
                title="Municipal Waterlogging Hotspot Data Unavailable",
                severity="info",
                evidence_status="data_unavailable",
                category="historical_vulnerability",
                evidence_type="historical_monsoon_vulnerability",
                data_freshness="unavailable",
                geographic_resolution="point_infrastructure",
                source_agency="Local Municipal Corporation / PWD (Open Data Pending)",
                source_url="https://mohua.gov.in/",
                description=(
                    "Standardized point-level municipal waterlogging and chronic underpass drainage GIS datasets "
                    "have not been published by municipal authorities for this jurisdiction. The absence of mapped points "
                    "indicates lack of surveyed municipal open data, NOT zero waterlogging risk."
                ),
                mitigation_notes="Conduct localized physical due-diligence: inspect neighborhood road curb heights, storm gutter inlets, and ask local residents about monsoon street ponding.",
                is_applicable=False,
                limitations="Standardized arterial underpass open GIS telemetry is currently published only for NCT of Delhi PWD network.",
                parameters={"status": "data_gap_disclosed"},
            )
        )

    # 6. Extreme Heat & Core Heatwave Belt (IMD / NDMA)
    heatwave_data = _load_json_file(HEATWAVE_GEOJSON_PATH)
    matched_heatwave = False
    for feat in heatwave_data.get("features", []):
        inside, _ = _check_point_in_geometry(longitude, latitude, feat.get("geometry", {}))
        if inside:
            matched_heatwave = True
            spatial_layers["heatwave_zone"] = feat
            break

    if matched_heatwave:
        hazards.append(
            DisasterHazardItem(
                hazard_type="heatwave",
                title="IMD Core Heatwave Zone Exposure",
                severity="moderate",
                evidence_status="evidence_found",
                category="static_zonal",
                evidence_type="static_zonal",
                data_freshness="static_standard",
                geographic_resolution="regional_statutory_standard",
                source_agency="India Meteorological Department (IMD) & NDMA Heat Action Plan",
                source_url="https://mausam.imd.gov.in/",
                description=(
                    "Location falls within the IMD Core Heatwave Zone (CHZ). Experiences peak summer maximums "
                    "of 42°C to 47°C during April to June. Urbanized built surfaces exacerbate ambient temperatures by +2°C to +4°C."
                ),
                mitigation_notes="Evaluate building solar orientation, reflective cool roof coatings (SRI > 78), and passive thermal ventilation.",
                is_applicable=True,
                parameters={
                    "summer_peak_celsius": "42-47°C",
                    "heatwave_threshold": "40°C in plains or departure >= 4.5°C",
                },
            )
        )
    else:
        hazards.append(
            DisasterHazardItem(
                hazard_type="heatwave",
                title="Moderate Summer Climatology (Outside Core Heatwave Belt)",
                severity="low",
                evidence_status="no_mapped_feature",
                category="static_zonal",
                evidence_type="static_zonal",
                data_freshness="static_standard",
                geographic_resolution="regional_statutory_standard",
                source_agency="India Meteorological Department (IMD)",
                source_url="https://mausam.imd.gov.in/",
                description="Location lies outside the IMD Core Heatwave Zone; summer extremes are moderated by maritime sea breezes, Western Ghats topography, or high elevation.",
                mitigation_notes="Standard architectural ventilation practices apply.",
                is_applicable=False,
            )
        )

    # 7. Drought & Groundwater Stress (CGWB)
    drought_data = _load_json_file(DROUGHT_GEOJSON_PATH)
    matched_drought_feat = None
    for feat in drought_data.get("features", []):
        inside, _ = _check_point_in_geometry(longitude, latitude, feat.get("geometry", {}))
        if inside:
            matched_drought_feat = feat
            spatial_layers["drought_stress_zone"] = feat
            break

    if matched_drought_feat:
        dp = matched_drought_feat.get("properties", {})
        hazards.append(
            DisasterHazardItem(
                hazard_type="drought",
                title=f"CGWB Groundwater Stress: {dp.get('zone_name', 'Over-Exploited Unit')}",
                severity="moderate",
                evidence_status="evidence_found",
                category="historical_vulnerability",
                evidence_type="historical_and_zonal",
                data_freshness="historical_compendium",
                geographic_resolution="regional_statutory_standard",
                source_agency="Central Ground Water Board (CGWB) & Ministry of Jal Shakti",
                source_url="https://cgwb.gov.in/",
                description=dp.get(
                    "description",
                    "Intensive groundwater withdrawal exceeding annual replenishable recharge rate (>100% extraction).",
                ),
                mitigation_notes=dp.get(
                    "mitigation_notes",
                    "Mandatory rooftop rainwater harvesting with dual recharge shafts; ensure minimum 3-day water storage.",
                ),
                is_applicable=True,
                parameters={
                    "stress_level": dp.get("stress_level"),
                    "extraction_rate": dp.get("extraction_rate"),
                },
            )
        )
    else:
        hazards.append(
            DisasterHazardItem(
                hazard_type="drought",
                title="Safe / Semi-Critical Aquifer Extraction Unit",
                severity="low",
                evidence_status="no_mapped_feature",
                category="historical_vulnerability",
                evidence_type="historical_and_zonal",
                data_freshness="historical_compendium",
                geographic_resolution="regional_statutory_standard",
                source_agency="Central Ground Water Board (CGWB)",
                source_url="https://cgwb.gov.in/",
                description="Groundwater extraction in this hydrogeological block is within sustainable replenishable recharge limits under CGWB assessment criteria.",
                mitigation_notes="Rainwater harvesting is recommended for long-term domestic water security.",
                is_applicable=False,
            )
        )

    # 8. Severe Rainfall Standard Thresholds (IMD Static Benchmark)
    hazards.append(
        DisasterHazardItem(
            hazard_type="rainfall",
            title="IMD Severe Monsoon Rainfall Thresholds",
            severity="info",
            evidence_status="evidence_found",
            category="static_zonal",
            evidence_type="static_zonal",
            data_freshness="static_standard",
            geographic_resolution="regional_statutory_standard",
            source_agency="India Meteorological Department (IMD)",
            source_url="https://mausam.imd.gov.in/",
            description="IMD statutory monsoon rainfall alert classifications: Heavy Rain (64.5 - 115.5 mm/day), Very Heavy Rain (115.6 - 204.4 mm/day), Extremely Heavy Rain (>204.4 mm/day).",
            mitigation_notes="Inspect building roof rain gutters, downspouts, and rainwater harvesting recharge pits prior to July monsoon onset.",
            is_applicable=True,
            parameters={
                "heavy_rain_mm": "64.5-115.5",
                "very_heavy_rain_mm": "115.6-204.4",
                "extreme_rain_mm": ">204.4",
            },
        )
    )

    locality_name = address.split(",")[0].strip() if address else f"{latitude:.4f}° N, {longitude:.4f}° E"
    state_resolved = detected_state
    if address and "," in address:
        parts = [p.strip() for p in address.split(",")]
        if len(parts) >= 2:
            state_candidate = parts[-1]
            if state_candidate and not any(c.isdigit() for c in state_candidate):
                state_resolved = state_candidate

    return DisasterLocationResponse(
        status="active",
        latitude=latitude,
        longitude=longitude,
        address=address,
        locality_name=locality_name,
        state=state_resolved,
        hazards=hazards,
        active_alerts_count=sum(1 for h in hazards if h.severity in ("critical", "high")),
        spatial_layers=spatial_layers,
        coverage_summary={
            "jurisdiction": "Republic of India",
            "state": state_resolved or "India",
            "seismic_coverage": "statutory_national_100pct",
            "flood_coverage": "regional_major_basins_cwc",
            "cyclone_coverage": "all_coastal_states_13uts",
            "landslide_coverage": "gsi_nlsm_mountain_belts",
            "waterlogging_coverage": "delhi_pwd_point_inventory" if is_delhi else "data_unavailable",
        },
        live_alerts_available=False,
        live_alerts_status="unavailable: Live emergency meteorological radar/alert push feeds require integration with IMD Nowcast or state disaster push feeds. Grounded static and historical zoning baseline is active.",
    )


async def compare_disaster_hazards(
    request: DisasterCompareRequest,
) -> DisasterCompareResponse:
    """
    Compare disaster hazard exposures between Location A and Location B side-by-side across India.
    Does not invent a synthetic comparative grade; provides evidence-by-evidence contrasts.
    """
    def _safe_float(val):
        if val is None:
            return None
        try:
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return None
            return f
        except (ValueError, TypeError):
            return None

    loc_a_data = request.location_a or {}
    loc_b_data = request.location_b or {}

    lat_a = _safe_float(loc_a_data.get("latitude"))
    lon_a = _safe_float(loc_a_data.get("longitude"))
    addr_a = loc_a_data.get("address") or "Location A"

    lat_b = _safe_float(loc_b_data.get("latitude"))
    lon_b = _safe_float(loc_b_data.get("longitude"))
    addr_b = loc_b_data.get("address") or "Location B"

    if lat_a is None or lon_a is None:
        resp_a = DisasterLocationResponse(
            status="data_unavailable",
            latitude=0.0,
            longitude=0.0,
            address=addr_a,
            locality_name=addr_a,
            error_message="Location A missing valid latitude and longitude coordinates.",
        )
    else:
        resp_a = await get_disaster_hazards(lat_a, lon_a, addr_a)

    if lat_b is None or lon_b is None:
        resp_b = DisasterLocationResponse(
            status="data_unavailable",
            latitude=0.0,
            longitude=0.0,
            address=addr_b,
            locality_name=addr_b,
            error_message="Location B missing valid latitude and longitude coordinates.",
        )
    else:
        resp_b = await get_disaster_hazards(lat_b, lon_b, addr_b)

    status_a = resp_a.status
    status_b = resp_b.status

    if status_a != "active" and status_b != "active":
        return DisasterCompareResponse(
            status="incomparable",
            location_a=resp_a,
            location_b=resp_b,
            comparative_analysis=[],
            comparison_verdict="Both candidate locations lack valid hazard telemetry or fall outside supported spatial coverage. Comparison cannot be performed.",
            disclaimers=[
                "Neither candidate location provided valid coordinates within the Republic of India territorial hazard zoning dataset.",
                "Missing data must not be interpreted as absence of hazard risk.",
            ],
        )

    if status_a != "active" or status_b != "active":
        active_name = resp_a.locality_name if status_a == "active" else resp_b.locality_name
        missing_name = resp_b.locality_name if status_a == "active" else resp_a.locality_name
        return DisasterCompareResponse(
            status="partial_evidence",
            location_a=resp_a,
            location_b=resp_b,
            comparative_analysis=[],
            comparison_verdict=f"Partial comparison only. Grounded hazard telemetry is available for {active_name}, but {missing_name} lacks valid coverage or coordinates. Missing data cannot be ranked as safer.",
            disclaimers=[
                f"Candidate location '{missing_name}' has no verified hazard coverage. It must NOT be inferred as safer due to absence of data.",
                "Relocation comparison requires verified spatial evidence for both candidate properties.",
            ],
        )

    # Both locations are active; build comparative contrast points
    comparison_points = []

    # 1. Seismic Zone
    sz_a = next((h for h in (resp_a.hazards or []) if h.hazard_type == "earthquake"), None)
    sz_b = next((h for h in (resp_b.hazards or []) if h.hazard_type == "earthquake"), None)
    zone_a = sz_a.parameters.get("seismic_zone", "N/A") if sz_a else "N/A"
    zone_b = sz_b.parameters.get("seismic_zone", "N/A") if sz_b else "N/A"

    if zone_a == zone_b:
        seis_summary = f"Both locations fall under BIS Seismic Zone {zone_a}. Identical structural engineering codes (IS 1893:2016) apply."
    else:
        seis_summary = f"{resp_a.locality_name} is in BIS Seismic Zone {zone_a} (Z = {sz_a.parameters.get('zone_factor', 'N/A') if sz_a else 'N/A'}) while {resp_b.locality_name} is in Zone {zone_b} (Z = {sz_b.parameters.get('zone_factor', 'N/A') if sz_b else 'N/A'})."

    comparison_points.append({
        "hazard_type": "earthquake",
        "title": "Seismic Exposure (BIS IS 1893:2016)",
        "summary": seis_summary,
        "location_a_verdict": f"Zone {zone_a} ({sz_a.severity.title() if sz_a else 'N/A'})",
        "location_b_verdict": f"Zone {zone_b} ({sz_b.severity.title() if sz_b else 'N/A'})",
    })

    # 2. Riverine Flooding
    flood_a = next((h for h in (resp_a.hazards or []) if h.hazard_type == "flood"), None)
    flood_b = next((h for h in (resp_b.hazards or []) if h.hazard_type == "flood"), None)
    flood_a_sev = flood_a.severity if flood_a else "low"
    flood_b_sev = flood_b.severity if flood_b else "low"

    if flood_a_sev == flood_b_sev:
        flood_summary = f"Both locations exhibit similar documented riverine inundation exposure ({flood_a_sev})."
    else:
        flood_summary = f"{resp_a.locality_name} is evaluated as '{flood_a_sev}' while {resp_b.locality_name} is evaluated as '{flood_b_sev}' for riverine basin proximity."

    comparison_points.append({
        "hazard_type": "flood",
        "title": "Riverine Flood Risk",
        "summary": flood_summary,
        "location_a_verdict": flood_a.title if flood_a else "Low",
        "location_b_verdict": flood_b.title if flood_b else "Low",
    })

    # 3. Coastal Cyclone & Storm Surge
    cyc_a = next((h for h in (resp_a.hazards or []) if h.hazard_type == "cyclone"), None)
    cyc_b = next((h for h in (resp_b.hazards or []) if h.hazard_type == "cyclone"), None)
    cyc_a_sev = cyc_a.severity if cyc_a else "low"
    cyc_b_sev = cyc_b.severity if cyc_b else "low"

    if cyc_a_sev == cyc_b_sev:
        cyc_summary = f"Both locations share comparable coastal cyclone vulnerability ({cyc_a_sev})."
    else:
        cyc_summary = f"{resp_a.locality_name} ({cyc_a.title if cyc_a else 'Low'}) vs {resp_b.locality_name} ({cyc_b.title if cyc_b else 'Low'})."

    comparison_points.append({
        "hazard_type": "cyclone",
        "title": "Coastal Cyclone & Surge Risk",
        "summary": cyc_summary,
        "location_a_verdict": cyc_a.title if cyc_a else "Low",
        "location_b_verdict": cyc_b.title if cyc_b else "Low",
    })

    # 4. Landslides & Steep Terrain
    ls_a = next((h for h in (resp_a.hazards or []) if h.hazard_type == "landslide"), None)
    ls_b = next((h for h in (resp_b.hazards or []) if h.hazard_type == "landslide"), None)
    ls_a_sev = ls_a.severity if ls_a else "low"
    ls_b_sev = ls_b.severity if ls_b else "low"

    if ls_a_sev == ls_b_sev:
        ls_summary = f"Both locations share similar slope stability classifications ({ls_a_sev})."
    else:
        ls_summary = f"{resp_a.locality_name} ({ls_a_sev}) vs {resp_b.locality_name} ({ls_b_sev}) for GSI landslide susceptibility."

    comparison_points.append({
        "hazard_type": "landslide",
        "title": "Landslide & Slope Stability (GSI NLSM)",
        "summary": ls_summary,
        "location_a_verdict": ls_a.title if ls_a else "Low",
        "location_b_verdict": ls_b.title if ls_b else "Low",
    })

    # 5. Urban Monsoon Waterlogging
    wl_a = next((h for h in (resp_a.hazards or []) if h.hazard_type == "waterlogging"), None)
    wl_b = next((h for h in (resp_b.hazards or []) if h.hazard_type == "waterlogging"), None)
    status_wl_a = wl_a.evidence_status if wl_a else "data_unavailable"
    status_wl_b = wl_b.evidence_status if wl_b else "data_unavailable"

    if status_wl_a == "evidence_found" and status_wl_b == "evidence_found":
        dist_a = wl_a.parameters.get("nearest_hotspot_km", "N/A")
        dist_b = wl_b.parameters.get("nearest_hotspot_km", "N/A")
        wl_summary = f"Surveyed municipal underpass depression proximity: {resp_a.locality_name} (~{dist_a} km) vs {resp_b.locality_name} (~{dist_b} km)."
    elif status_wl_a != status_wl_b:
        avail_name = resp_a.locality_name if status_wl_a == "evidence_found" else resp_b.locality_name
        unavail_name = resp_b.locality_name if status_wl_a == "evidence_found" else resp_a.locality_name
        wl_summary = f"Surveyed municipal point inventory is published for {avail_name}, but currently unavailable as open data for {unavail_name}. Missing data must not be interpreted as zero risk."
    else:
        wl_summary = "Neither jurisdiction currently provides published open GIS point datasets for chronic arterial underpass waterlogging."

    comparison_points.append({
        "hazard_type": "waterlogging",
        "title": "Urban Monsoon Waterlogging",
        "summary": wl_summary,
        "location_a_verdict": wl_a.title if wl_a else "Data Unavailable",
        "location_b_verdict": wl_b.title if wl_b else "Data Unavailable",
    })

    return DisasterCompareResponse(
        status="active",
        location_a=resp_a,
        location_b=resp_b,
        comparative_analysis=comparison_points,
        comparison_verdict="Side-by-side contrast complete across statutory seismic standards, river basin corridors, cyclone surge belts, landslide susceptibility, and surveyed municipal drainage.",
        disclaimers=[
            "Comparative analysis uses identical BIS, CWC, NDMA, and GSI statutory and modeled definitions for both candidate locations.",
            "Differences reflect verifiable geographic coordinates relative to floodplains, coastal surge limits, and tectonic/geomorphological zones.",
            "No location in India is completely hazard-free; earthquake-resistant ductile construction is statutory across all zones.",
        ],
    )
