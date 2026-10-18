import asyncio
import logging
from typing import Optional, List, Dict, Any
import httpx
from backend.models.score import LocationResult, InfrastructureSummary
from backend.services.geocoding import geocode_address

logger = logging.getLogger("nivas.services.location")

# ==============================================================================
# Transparent Location Infrastructure Scoring Weights (0 - 100)
# All weight factors and saturation caps are centralized here for easy tuning.
# ==============================================================================
LOCATION_SCORE_WEIGHTS = {
    "healthcare": {
        "weight": 0.25,        # 25% of overall location score
        "hospital_cap": 2,     # Cap at 2 hospitals for 100% health component score
        "clinic_cap": 3,
        "pharmacy_cap": 3,
    },
    "emergency": {
        "weight": 0.20,        # 20% of overall location score
        "police_cap": 1,
        "fire_station_cap": 1,
    },
    "education": {
        "weight": 0.20,        # 20% of overall location score
        "school_cap": 3,
    },
    "transit": {
        "weight": 0.20,        # 20% of overall location score
        "bus_station_cap": 3,
        "railway_cap": 1,
    },
    "connectivity": {
        "weight": 0.15,        # 15% of overall location score
        "major_road_cap": 2,
    },
}


def calculate_location_score(infra: Optional[InfrastructureSummary]) -> Optional[float]:
    """
    Computes a transparent 0-100 infrastructure accessibility score from real Overpass results.
    Returns None if infra is None or unavailable (never treats missing data as a score of zero).

    Formula breakdown using LOCATION_SCORE_WEIGHTS:
    - Healthcare (25%): Hospitals (50%), Clinics (30%), Pharmacies (20%)
    - Emergency (20%): Police stations (60%), Fire stations (40%)
    - Education (20%): Schools
    - Transit (20%): Public transport / Bus stations (50%), Railway / Metro stations (50%)
    - Connectivity (15%): Major roads / High-speed arterials
    """
    if infra is None:
        return None

    w = LOCATION_SCORE_WEIGHTS

    # 1. Healthcare Component (0 - 100)
    h_hosp = min(1.0, infra.hospitals_count / w["healthcare"]["hospital_cap"]) if w["healthcare"]["hospital_cap"] > 0 else 0
    h_clin = min(1.0, infra.clinics_count / w["healthcare"]["clinic_cap"]) if w["healthcare"]["clinic_cap"] > 0 else 0
    h_pharm = min(1.0, infra.pharmacies_count / w["healthcare"]["pharmacy_cap"]) if w["healthcare"]["pharmacy_cap"] > 0 else 0
    health_score = (0.5 * h_hosp + 0.3 * h_clin + 0.2 * h_pharm) * 100.0

    # 2. Emergency Services Component (0 - 100)
    e_pol = min(1.0, infra.police_stations_count / w["emergency"]["police_cap"]) if w["emergency"]["police_cap"] > 0 else 0
    e_fire = min(1.0, infra.fire_stations_count / w["emergency"]["fire_station_cap"]) if w["emergency"]["fire_station_cap"] > 0 else 0
    emergency_score = (0.6 * e_pol + 0.4 * e_fire) * 100.0

    # 3. Education Component (0 - 100)
    ed_school = min(1.0, infra.schools_count / w["education"]["school_cap"]) if w["education"]["school_cap"] > 0 else 0
    education_score = ed_school * 100.0

    # 4. Transit Component (0 - 100)
    t_bus = min(1.0, infra.public_transport_count / w["transit"]["bus_station_cap"]) if w["transit"]["bus_station_cap"] > 0 else 0
    t_rail = min(1.0, infra.railway_stations_count / w["transit"]["railway_cap"]) if w["transit"]["railway_cap"] > 0 else 0
    transit_score = (0.5 * t_bus + 0.5 * t_rail) * 100.0

    # 5. Connectivity Component (0 - 100)
    c_road = min(1.0, infra.major_roads_count / w["connectivity"]["major_road_cap"]) if w["connectivity"]["major_road_cap"] > 0 else 0
    connectivity_score = c_road * 100.0

    # Composite weighted sum
    total_score = (
        w["healthcare"]["weight"] * health_score
        + w["emergency"]["weight"] * emergency_score
        + w["education"]["weight"] * education_score
        + w["transit"]["weight"] * transit_score
        + w["connectivity"]["weight"] * connectivity_score
    )

    return round(max(0.0, min(100.0, total_score)), 2)


OVERPASS_ENDPOINTS = [
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]



def _parse_overpass_infrastructure(elements: List[Dict[str, Any]]) -> InfrastructureSummary:
    """Convert a verified Overpass response into the existing response schema."""
    schools = 0
    hospitals = 0
    clinics = 0
    pharmacies = 0
    police = 0
    fire_stations = 0
    bus_stations = 0
    railway_stations = 0
    major_roads = 0
    nearby_places_set = set()
    facilities = []
    seen_keys = set()

    for elem in elements:
        tags = elem.get("tags", {})
        name = tags.get("name")
        if name:
            nearby_places_set.add(name)

        amenity = tags.get("amenity")
        railway = tags.get("railway")
        highway = tags.get("highway")

        category = None
        category_label = None

        if amenity == "school":
            schools += 1
            category = "school"
            category_label = "School"
        elif amenity == "hospital":
            hospitals += 1
            category = "hospital"
            category_label = "Hospital"
        elif amenity == "clinic":
            clinics += 1
            category = "clinic"
            category_label = "Clinic"
        elif amenity == "pharmacy":
            pharmacies += 1
            category = "pharmacy"
            category_label = "Pharmacy"
        elif amenity == "police":
            police += 1
            category = "police"
            category_label = "Police Station"
        elif amenity == "fire_station":
            fire_stations += 1
            category = "fire"
            category_label = "Fire Station"
        elif amenity == "bus_station":
            bus_stations += 1
            category = "transit"
            category_label = "Bus Station"

        if railway == "station":
            railway_stations += 1
            category = "railway"
            category_label = "Metro / Railway Station"
        if highway in ("primary", "secondary", "trunk", "motorway"):
            major_roads += 1
            if not category:
                category = "road"
                category_label = f"Major Road ({highway.title()})"

        # Real coordinates extraction
        lat_coord = elem.get("lat")
        lon_coord = elem.get("lon")
        if lat_coord is None and "center" in elem:
            center_obj = elem.get("center") or {}
            lat_coord = center_obj.get("lat")
            lon_coord = center_obj.get("lon")

        if lat_coord is not None and lon_coord is not None and category:
            fac_name = name or tags.get("ref") or f"Local {category_label}"
            fac_id = str(elem.get("id") or f"{lat_coord}_{lon_coord}")
            coord_key = (round(float(lat_coord), 5), round(float(lon_coord), 5), category)
            if coord_key not in seen_keys:
                seen_keys.add(coord_key)
                facilities.append({
                    "id": fac_id,
                    "name": fac_name,
                    "category": category,
                    "category_label": category_label,
                    "latitude": float(lat_coord),
                    "longitude": float(lon_coord),
                    "source": "OpenStreetMap",
                })

    return InfrastructureSummary(
        schools_count=schools,
        hospitals_count=hospitals,
        clinics_count=clinics,
        pharmacies_count=pharmacies,
        police_stations_count=police,
        fire_stations_count=fire_stations,
        public_transport_count=bus_stations,
        railway_stations_count=railway_stations,
        major_roads_count=major_roads,
        nearby_places=list(nearby_places_set)[:10],
        facilities=facilities,
    )


async def _request_overpass_mirror(
    client: httpx.AsyncClient,
    endpoint: str,
    query: str,
    headers: Dict[str, str],
) -> tuple[str, Optional[List[Dict[str, Any]]]]:
    """Return parsed elements from one mirror, or None when that mirror fails."""
    try:
        response = await client.post(endpoint, data={"data": query}, headers=headers)
        if response.status_code != 200:
            logger.warning("Overpass mirror %s returned HTTP %s", endpoint, response.status_code)
            return endpoint, None
        payload = response.json()
        elements = payload.get("elements", [])
        if not isinstance(elements, list):
            logger.warning("Overpass mirror %s returned an invalid elements payload", endpoint)
            return endpoint, None
        return endpoint, elements
    except Exception as err:
        logger.warning("Overpass mirror %s failed (%s: %s)", endpoint, type(err).__name__, str(err))
        return endpoint, None


async def fetch_overpass_infrastructure(
    lat: float,
    lon: float,
    radius: int = 1200,
    connect_timeout: float = 3.5,
    read_timeout: float = 12.0,
    endpoints: Optional[List[str]] = None,
) -> Optional[InfrastructureSummary]:
    """
    Fetch real infrastructure elements from OpenStreetMap Overpass API around (lat, lon).
    Iterates through OVERPASS_ENDPOINTS with concurrent per-mirror requests.
    Returns immediately when a mirror returns verified elements. If a mirror returns 0 elements,
    holds that empty result while allowing remaining mirrors to finish in case of broader coverage.
    Returns None if all API mirrors fail or time out (never treats missing API data as zero).
    """
    if lat is None or lon is None:
        return None

    query = (
        f"""[out:json][timeout:12];"""
        f"""("""
        f"""node["amenity"~"school|hospital|clinic|pharmacy|police|fire_station|bus_station"](around:{radius},{lat},{lon});"""
        f"""node["railway"~"station|subway_entrance"](around:{radius + 800},{lat},{lon});"""
        f"""way["highway"~"primary|secondary|trunk|motorway"](around:{radius},{lat},{lon});"""
        f""");out center 50;"""
    )

    headers = {
        "User-Agent": "NIVAS-Livability-App/1.0 (https://github.com/nivas; contact@nivas.local)",
        "Accept": "application/json, */*",
    }

    mirrors = endpoints if endpoints is not None else OVERPASS_ENDPOINTS
    per_mirror_timeout = httpx.Timeout(connect=connect_timeout, read=read_timeout, write=4.0, pool=4.0)

    async with httpx.AsyncClient(timeout=per_mirror_timeout) as client:
        tasks = [
            asyncio.create_task(_request_overpass_mirror(client, endpoint, query, headers))
            for endpoint in mirrors
        ]
        empty_candidate = None
        try:
            for completed_task in asyncio.as_completed(tasks):
                endpoint, elements = await completed_task
                if elements is not None:
                    if len(elements) > 0:
                        logger.info(
                            "Overpass infrastructure retrieved successfully from mirror %s (%d elements)",
                            endpoint,
                            len(elements),
                        )
                        return _parse_overpass_infrastructure(elements)
                    elif empty_candidate is None:
                        empty_candidate = (endpoint, elements)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        if empty_candidate is not None:
            endpoint, elements = empty_candidate
            logger.info("Overpass query completed with 0 elements from mirror %s", endpoint)
            return _parse_overpass_infrastructure(elements)

    logger.warning("All Overpass API mirrors failed or timed out for lat=%s, lon=%s", lat, lon)
    return None


async def fetch_location(address: str) -> Optional[LocationResult]:
    """
    Fetch location data and real infrastructure elements from OpenStreetMap Overpass API.

    Guarantees:
    - If geocoding fails (bad/unresolvable address), returns LocationResult with
      fetch_status='invalid_address' without attempting Overpass retries.
    - If Overpass API infrastructure cannot be retrieved on attempt 1, retries once
      automatically after a brief backoff before marking as 'fetch_failed'.
    - Preserves resolved geocoded coordinates even if infrastructure query fails,
      ensuring map rendering remains possible while clearly flagging the fetch failure.
    - Never invents or substitutes synthetic location/infrastructure data.
    """
    if not address or not address.strip():
        return None

    try:
        geo = await geocode_address(address)
        if geo is None:
            locality_name = address.split(",")[0].strip()
            logger.warning("Geocoding unfulfilled for address: '%s'", address)
            return LocationResult(
                locality=locality_name,
                latitude=None,
                longitude=None,
                risk_score=None,
                infrastructure=None,
                fetch_status="invalid_address",
                error_message="Address could not be geocoded or resolved to coordinates",
            )

        locality_name = address.split(",")[0].strip()

        # Query real infrastructure from Overpass API (Attempt 1)
        infra = None
        try:
            infra = await fetch_overpass_infrastructure(lat=geo.latitude, lon=geo.longitude)
        except Exception as infra_err:
            logger.warning(
                "Attempt 1 Overpass infrastructure error for '%s' (%s, %s): %s",
                locality_name, geo.latitude, geo.longitude, str(infra_err)
            )

        # Single automatic retry if attempt 1 timed out or failed
        if infra is None:
            logger.info(
                "Overpass infrastructure fetch unfulfilled on attempt 1 for '%s' (%s, %s); retrying once...",
                locality_name, geo.latitude, geo.longitude
            )
            await asyncio.sleep(0.5)
            try:
                infra = await fetch_overpass_infrastructure(lat=geo.latitude, lon=geo.longitude)
            except Exception as retry_err:
                logger.warning(
                    "Attempt 2 (retry) Overpass infrastructure error for '%s' (%s, %s): %s",
                    locality_name, geo.latitude, geo.longitude, str(retry_err)
                )

        if infra is not None:
            location_score = calculate_location_score(infra)
            logger.info("Successfully fetched infrastructure for '%s' (score: %s)", locality_name, location_score)
            return LocationResult(
                locality=locality_name,
                latitude=geo.latitude,
                longitude=geo.longitude,
                risk_score=location_score,
                infrastructure=infra,
                fetch_status="active",
                error_message=None,
            )
        else:
            logger.warning(
                "All Overpass API mirrors failed or timed out after retry for '%s' (%s, %s)",
                locality_name, geo.latitude, geo.longitude
            )
            return LocationResult(
                locality=locality_name,
                latitude=geo.latitude,
                longitude=geo.longitude,
                risk_score=None,
                infrastructure=None,
                fetch_status="fetch_failed",
                error_message="Civic infrastructure data temporarily unavailable from OpenStreetMap mirrors (request timed out)",
            )

    except Exception as err:
        logger.error("Unexpected error in fetch_location for '%s': %s", address, str(err), exc_info=True)
        return LocationResult(
            locality=address.split(",")[0].strip() if address else "Unknown",
            latitude=None,
            longitude=None,
            risk_score=None,
            infrastructure=None,
            fetch_status="fetch_failed",
            error_message=f"Location service error: {str(err)}",
        )
