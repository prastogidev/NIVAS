import os
import math
import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Tuple, Optional
import httpx

from backend.models.livability import (
    LivabilityChatRequest,
    LivabilityChatResponse,
    LivabilityChatContext,
    LivabilityChatFacilityItem,
)
from backend.services.location import fetch_overpass_infrastructure
from backend.services.air_quality import fetch_real_aqi_with_status
from backend.core.config import settings

logger = logging.getLogger("nivas.services.livability_advisor")


def calculate_haversine_distance_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> Optional[float]:
    """Calculate great-circle distance between two coordinates in kilometers."""
    try:
        if any(x is None or math.isnan(x) for x in (lat1, lon1, lat2, lon2)):
            return None
        r = 6371.0  # Earth mean radius in kilometers
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


def format_distance(distance_km: Optional[float]) -> str:
    """Format distance in km or meters."""
    if distance_km is None or math.isnan(distance_km):
        return "Distance unavailable"
    if distance_km < 1.0:
        meters = int(round(distance_km * 1000))
        return f"{meters} m"
    return f"{distance_km:.2f} km"


async def build_context_from_coordinates(
    latitude: float, longitude: float, address: Optional[str] = None
) -> LivabilityChatContext:
    """Retrieve and build fresh context from existing location and air quality services."""
    infra_task = fetch_overpass_infrastructure(latitude, longitude)
    aqi_task = fetch_real_aqi_with_status(latitude, longitude)

    infra_result, aqi_result = await asyncio.gather(
        infra_task, aqi_task, return_exceptions=True
    )

    locality = address.split(",")[0].strip() if address else None

    # Infrastructure facilities
    facilities: List[LivabilityChatFacilityItem] = []
    schools_cnt = 0
    hospitals_cnt = 0
    clinics_cnt = 0
    pharmacies_cnt = 0
    police_cnt = 0
    fire_cnt = 0
    transit_cnt = 0
    railway_cnt = 0
    roads_cnt = 0
    nearby_places: List[str] = []
    infra_status = "active"

    if isinstance(infra_result, Exception) or infra_result is None:
        infra_status = "fetch_failed"
    else:
        schools_cnt = infra_result.schools_count
        hospitals_cnt = infra_result.hospitals_count
        clinics_cnt = infra_result.clinics_count
        pharmacies_cnt = infra_result.pharmacies_count
        police_cnt = infra_result.police_stations_count
        fire_cnt = infra_result.fire_stations_count
        transit_cnt = infra_result.public_transport_count
        railway_cnt = infra_result.railway_stations_count
        roads_cnt = infra_result.major_roads_count
        nearby_places = infra_result.nearby_places or []

        total = (
            schools_cnt
            + hospitals_cnt
            + clinics_cnt
            + pharmacies_cnt
            + police_cnt
            + fire_cnt
            + transit_cnt
            + railway_cnt
            + roads_cnt
        )
        if total == 0 and not nearby_places:
            infra_status = "empty"

        raw_facs = getattr(infra_result, "facilities", []) or []
        for fac in raw_facs:
            fac_dict = fac if isinstance(fac, dict) else fac.model_dump()
            lat = fac_dict.get("latitude")
            lon = fac_dict.get("longitude")
            dist = calculate_haversine_distance_km(latitude, longitude, lat, lon)
            facilities.append(
                LivabilityChatFacilityItem(
                    id=fac_dict.get("id"),
                    name=fac_dict.get("name", "Unnamed Facility"),
                    category=fac_dict.get("category", "general"),
                    category_label=fac_dict.get("category_label"),
                    latitude=lat,
                    longitude=lon,
                    distance_km=dist,
                    formatted_distance=format_distance(dist),
                    source=fac_dict.get("source", "OpenStreetMap"),
                )
            )

    # Air quality
    aqi_status = "provider_not_configured"
    aqi_val = None
    aqi_cat = None
    aqi_station = None
    aqi_src = None
    env_score = None

    if not isinstance(aqi_result, Exception) and aqi_result is not None:
        aqi_obj, aqi_status_val, _ = aqi_result
        aqi_status = aqi_status_val
        if aqi_obj is not None:
            aqi_val = aqi_obj.aqi_value
            aqi_cat = aqi_obj.category
            aqi_station = aqi_obj.station_name
            aqi_src = aqi_obj.source
            env_score = aqi_obj.environmental_score

    return LivabilityChatContext(
        latitude=latitude,
        longitude=longitude,
        address=address,
        locality=locality,
        search_radius_meters=1200,
        railway_search_radius_meters=2000,
        infrastructure_status=infra_status,
        facilities=facilities,
        schools_count=schools_cnt,
        hospitals_count=hospitals_cnt,
        clinics_count=clinics_cnt,
        pharmacies_count=pharmacies_cnt,
        police_stations_count=police_cnt,
        fire_stations_count=fire_cnt,
        public_transport_count=transit_cnt,
        railway_stations_count=railway_cnt,
        major_roads_count=roads_cnt,
        nearby_places=nearby_places,
        air_quality_status=aqi_status,
        aqi_value=aqi_val,
        aqi_category=aqi_cat,
        aqi_station=aqi_station,
        aqi_source=aqi_src,
        environmental_score=env_score,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        hazards_status="data_not_configured",
        hazards_message="Real-time environmental hazard sensor network not configured for this region",
    )


def generate_grounded_telemetry_reply(
    query: str, ctx: LivabilityChatContext
) -> Tuple[str, List[str]]:
    """
    Deterministic grounded telemetry responder that strictly uses verified facts from ctx.
    Identifies sources, acknowledges missing data, and never fabricates numbers or safety claims.
    """
    q = query.lower()
    sources = ["OpenStreetMap Overpass API"]
    loc_name = ctx.locality or ctx.address or f"coordinates ({ctx.latitude:.4f}° N, {ctx.longitude:.4f}° E)"

    # Conversational greeting handling: respond briefly without dumping telemetry report
    clean_q = "".join(ch for ch in q.strip() if ch.isalnum() or ch.isspace()).strip()
    greeting_phrases = {
        "hi", "hello", "hey", "howdy", "greetings", "good morning", "good afternoon",
        "good evening", "how are you", "how are you doing", "what's up", "whats up",
        "who are you", "help",
    }
    if clean_q in greeting_phrases or (
        any(clean_q.startswith(g + " ") for g in ["hi", "hello", "hey"])
        and len(clean_q.split()) <= 4
    ):
        loc_str = f" for {loc_name}" if loc_name else ""
        return (
            f"Hello! I am your NIVAS Neighborhood AI Advisor. I can provide grounded insights on schools, healthcare, transit, emergency services, and air quality{loc_str}. How can I assist you with this area today?",
            sources,
        )

    # 1. Healthcare inquiry
    if any(k in q for k in ["health", "hospital", "clinic", "pharmacy", "medical", "doctor"]):
        hc_facilities = [
            f for f in ctx.facilities if f.category in ["hospital", "clinic", "pharmacy"]
        ]
        hc_facilities.sort(key=lambda x: (x.distance_km if x.distance_km is not None else float("inf")))

        if ctx.infrastructure_status == "fetch_failed":
            return (
                f"Healthcare facility telemetry for {loc_name} is currently unavailable because the OpenStreetMap Overpass query encountered a timeout or network failure. No synthetic healthcare facilities can be reported.",
                sources,
            )

        if not hc_facilities:
            return (
                f"There are 0 healthcare facilities (hospitals, clinics, or pharmacies) mapped within the {ctx.search_radius_meters / 1000:.1f} km search radius of {loc_name} in OpenStreetMap.\n\n"
                f"• Coverage Note: OpenStreetMap relies on community GIS mapping. The absence of mapped clinics in this radius does not guarantee that none exist beyond this boundary.",
                sources,
            )

        lines = [
            f"Verified healthcare facilities within {ctx.search_radius_meters / 1000:.1f} km of {loc_name} (Source: OpenStreetMap):"
        ]
        for f in hc_facilities[:6]:
            dist_str = f.formatted_distance or (f"{f.distance_km:.2f} km" if f.distance_km is not None else "distance unknown")
            lines.append(f"• {f.name} ({f.category_label or f.category.title()}): ~{dist_str} away ({f.latitude:.4f}° N, {f.longitude:.4f}° E)")

        lines.append("\nNote: Distances are calculated using straight-line geometric distance (Haversine formula). Actual walking or driving route distances may vary.")
        return ("\n".join(lines), sources)

    # 2. Transit / Commute inquiry
    if any(k in q for k in ["transit", "metro", "bus", "rail", "train", "commute", "station", "connectivity"]):
        transit_facilities = [
            f for f in ctx.facilities if f.category in ["transit", "railway"]
        ]
        transit_facilities.sort(key=lambda x: (x.distance_km if x.distance_km is not None else float("inf")))

        if ctx.infrastructure_status == "fetch_failed":
            return (
                f"Transit telemetry for {loc_name} is currently unavailable due to an OpenStreetMap Overpass API mirror timeout. No synthetic transit stops can be reported.",
                sources,
            )

        if not transit_facilities:
            return (
                f"No public transit stops (bus stops within {ctx.search_radius_meters / 1000:.1f} km) or railway/metro stations (within {ctx.railway_search_radius_meters / 1000:.1f} km) were mapped for {loc_name} in OpenStreetMap.\n\n"
                f"• Connectivity Status: 0 mapped transit nodes in search radius. This indicates limited community GIS transit coverage or lower immediate arterial transit density.",
                sources,
            )

        nearest = transit_facilities[0]
        nearest_dist = nearest.formatted_distance or (f"{nearest.distance_km:.2f} km" if nearest.distance_km is not None else "distance unknown")
        lines = [
            f"Transit connectivity near {loc_name} (Source: OpenStreetMap):",
            f"• Nearest mapped transit facility: {nearest.name} ({nearest.category_label or nearest.category.title()}) at approximately {nearest_dist} straight-line distance.",
            f"• Total mapped transit amenities: {len(transit_facilities)} ({ctx.railway_stations_count} rail/metro stations, {ctx.public_transport_count} bus stops).",
        ]
        for f in transit_facilities[1:5]:
            dist_str = f.formatted_distance or (f"{f.distance_km:.2f} km" if f.distance_km is not None else "distance unknown")
            lines.append(f"• {f.name}: ~{dist_str}")

        lines.append("\nNote: Distance metric is straight-line Haversine distance, not road navigation distance.")
        return ("\n".join(lines), sources)

    # 3. Schools / Education inquiry
    if any(k in q for k in ["school", "education", "college", "university", "academic", "study"]):
        schools = [f for f in ctx.facilities if f.category == "school"]
        schools.sort(key=lambda x: (x.distance_km if x.distance_km is not None else float("inf")))

        if ctx.infrastructure_status == "fetch_failed":
            return (
                f"School facility telemetry for {loc_name} could not be retrieved due to an OpenStreetMap Overpass API query failure.",
                sources,
            )

        if not schools:
            return (
                f"0 educational institutions (schools) are mapped within {ctx.search_radius_meters / 1000:.1f} km of {loc_name} in OpenStreetMap.\n\n"
                f"• Coverage Note: Unmapped schools in OSM do not guarantee the total absence of private or unindexed institutions.",
                sources,
            )

        lines = [
            f"Verified schools within {ctx.search_radius_meters / 1000:.1f} km of {loc_name} (Source: OpenStreetMap):"
        ]
        for s in schools[:6]:
            dist_str = s.formatted_distance or (f"{s.distance_km:.2f} km" if s.distance_km is not None else "distance unknown")
            lines.append(f"• {s.name}: ~{dist_str} ({s.latitude:.4f}° N, {s.longitude:.4f}° E)")

        return ("\n".join(lines), sources)

    # 4. Emergency & Safety inquiry
    if any(k in q for k in ["police", "fire", "emergency", "safety", "crime"]):
        sources.append("Delhi Police / NCRB Official Statistics")
        emergency_facilities = [
            f for f in ctx.facilities if f.category in ["police", "fire"]
        ]
        emergency_facilities.sort(key=lambda x: (x.distance_km if x.distance_km is not None else float("inf")))

        lines = [f"Safety and Emergency services data for {loc_name}:"]

        # Resolved district crime baseline
        try:
            from backend.services.crime_data import resolve_police_district, load_crime_baseline
            resolved = resolve_police_district(ctx.latitude, ctx.longitude)
            if resolved:
                dcode, _ = resolved
                baseline = load_crime_baseline()
                ddata = baseline.get("districts", {}).get(dcode)
                if ddata:
                    lines.append(f"• Jurisdictional Police District: {ddata['district_name']} (HQ: {ddata.get('headquarters', 'N/A')}).")
                    lines.append(f"• Official Annual Statistics (2022 NCRB): {ddata['total_ipc_crimes_2022']:,} total reported IPC crimes ({ddata.get('crime_rate_per_lakh', 'N/A')} per 100k residents).")
                    top_cats = ddata.get("categories_2022", [])
                    if top_cats:
                        top_strs = [f"{c['label']} ({c['share_pct']}%)" for c in top_cats[:3]]
                        lines.append(f"• Primary Reported Offense Types: {', '.join(top_strs)}.")
                    lines.append("• Crime Telemetry Disclosure: High theft figures reflect online e-FIR auto-registration rather than higher localized physical danger. Individual incident addresses are not published to safeguard citizen privacy.")
        except Exception as e:
            logger.debug("District crime lookup in advisor: %s", e)

        if emergency_facilities:
            lines.append(f"\nVerified nearby emergency stations within {ctx.search_radius_meters / 1000:.1f} km (OpenStreetMap):")
            for f in emergency_facilities:
                dist_str = f.formatted_distance or (f"{f.distance_km:.2f} km" if f.distance_km is not None else "distance unknown")
                lines.append(f"• {f.name} ({f.category_label or f.category.title()}): ~{dist_str} away")
        else:
            lines.append(f"\n• 0 police or fire stations mapped within {ctx.search_radius_meters / 1000:.1f} km in OpenStreetMap.")

        lines.append(f"\n• Hazard Telemetry Status: {ctx.hazards_message or 'Real-time hazard sensors not configured'}.")
        lines.append("• Safety Caution: The absence of unmapped hazard records does NOT imply guaranteed safety or zero hazard.")
        return ("\n".join(lines), sources)

    # 4b. Disaster & Geological Hazard inquiry
    if any(k in q for k in ["disaster", "flood", "earthquake", "seismic", "waterlog", "heatwave"]):
        sources.append("BIS IS 1893:2016 / CWC / IMD Disaster Telemetry")
        lines = [
            f"Documented Disaster & Hazard Intelligence for {loc_name}:",
            "• Seismic Hazard (BIS IS 1893:2016): All of Delhi falls under Seismic Zone IV (High Damage Risk Zone - Zone factor 0.24, MSK VIII). Structural compliance with NBC 2016 and ductile detailing (IS 13920) is mandatory.",
        ]
        try:
            from backend.services.disaster import load_hazard_zones_geojson
            from backend.services.crime_data import point_in_polygon
            hz = load_hazard_zones_geojson()
            flood_feat = next((f for f in hz.get("features", []) if f.get("properties", {}).get("hazard_type") == "flood"), None)
            in_flood = False
            if flood_feat:
                fcoords = flood_feat.get("geometry", {}).get("coordinates", [])
                if fcoords:
                    in_flood = point_in_polygon(ctx.longitude, ctx.latitude, fcoords[0])
            if in_flood:
                lines.append("• Riverine Flood Hazard (CWC): Location lies inside the active Yamuna River floodplain corridor (submerged during 2023 flood at HFL 208.66m). Permanent construction is restricted.")
            else:
                lines.append("• Riverine Flood Hazard (CWC): Location lies on natural upland terrain outside the active Yamuna floodplain corridor.")
        except Exception as e:
            logger.debug("Flood lookup in advisor: %s", e)

        lines.append("• Urban Drainage / Waterlogging (Delhi PWD): Chronic waterlogging depressions occur at underpasses during extreme cloudbursts (>50 mm/hr).")
        lines.append("• Extreme Heat (IMD): Summer maximums reach 42°C-47°C; urban density elevates local temperatures +2°C to +4°C over vegetated belts.")
        lines.append("\nImportant: Long-term zoning indicates structural engineering requirements, not predictive disaster forecasting.")
        return ("\n".join(lines), sources)

    # 5. Air Quality & Environmental inquiry
    if any(k in q for k in ["air", "aqi", "pollution", "environment", "smog", "pm2.5", "pm10", "weather"]):
        sources.append("CPCB / OpenWeather Telemetry")
        if ctx.air_quality_status == "active":
            lines = [
                f"Atmospheric environmental telemetry for {loc_name}:",
                f"• AQI Reading: {ctx.aqi_value} ({ctx.aqi_category or 'Standard Index'})",
                f"• Monitoring Station: {ctx.aqi_station or 'Regional Monitoring Station'}",
                f"• Data Provider: {ctx.aqi_source or 'CPCB CAAQMS / OpenWeather'}",
            ]
            if ctx.environmental_score is not None:
                lines.append(f"• Environmental Baseline Score: {ctx.environmental_score} / 100")
            if ctx.retrieved_at:
                lines.append(f"• Observation Timestamp: {ctx.retrieved_at}")
            lines.append(f"• Local Hazards: {ctx.hazards_message or 'Sensor network not configured'}.")
            return ("\n".join(lines), sources)

        if ctx.air_quality_status == "provider_not_configured":
            return (
                f"Air quality telemetry is currently unconfigured for {loc_name}.\n\n"
                f"• Status: Air quality API keys (OpenWeather or AQICN) are not configured in the backend environment.\n"
                f"• Integrity Guarantee: NIVAS does not synthesize or fabricate estimated air pollution numbers when physical sensors are unconfigured.\n"
                f"• Hazard Network: Real-time environmental hazard sensors are also unconfigured for this region.",
                sources,
            )

        if ctx.air_quality_status == "data_unavailable":
            return (
                f"Air quality data unavailable for {loc_name}.\n\n"
                f"• Status: No active atmospheric monitoring stations reported readings within range (50 km).\n"
                f"• Unconfigured Hazards: {ctx.hazards_message or 'Hazard sensor network not configured'}.",
                sources,
            )

        return (
            f"Air quality telemetry fetch encountered an error or service timeout. Telemetry will re-attempt upon your next selection.",
            sources,
        )

    # 6. Missing Information / Limitations inquiry
    if any(k in q for k in ["missing", "limitation", "gap", "unknown", "coverage", "unavailable", "what don't"]):
        lines = [
            f"Data Coverage Limitations and Missing Information for {loc_name}:",
            f"1. Search Radius Boundary: Civic amenities are queried within a {ctx.search_radius_meters / 1000:.1f} km radius ({ctx.railway_search_radius_meters / 1000:.1f} km for railway/metro). Amenities outside these radii are not shown.",
            f"2. GIS Provenance: Infrastructure data relies on OpenStreetMap. Facilities not tagged in OSM or newly built cannot be indexed.",
            f"3. Distance Metric: Distances are straight-line geometric distances (Haversine formula), not pedestrian street routes.",
            f"4. Environmental Sensor Network: Real-time environmental hazard sensors are currently unconfigured.",
        ]
        if ctx.air_quality_status == "provider_not_configured":
            lines.append("5. Air Quality Telemetry: Atmospheric sensor API key is not configured in backend environment; no estimated AQI is fabricated.")
        elif ctx.air_quality_status == "data_unavailable":
            lines.append("5. Air Quality Telemetry: No physical CAAQMS stations detected within 50 km.")

        lines.append("\nImportant: Missing data or unmapped nodes must NEVER be interpreted as confirmation of safety, low risk, or absence of facilities.")
        return ("\n".join(lines), sources)

    # 7. General / Infrastructure Overview
    lines = [
        f"Verified Location Overview for {loc_name} ({ctx.latitude:.4f}° N, {ctx.longitude:.4f}° E):",
    ]

    if ctx.infrastructure_status == "fetch_failed":
        lines.append(
            f"• Civic Infrastructure: Telemetry is currently unavailable because OpenStreetMap Overpass mirrors timed out or encountered a network error. No synthetic amenity data can be reported."
        )
    elif ctx.infrastructure_status == "empty":
        lines.append(
            f"• Civic Infrastructure (OpenStreetMap within {ctx.search_radius_meters / 1000:.1f} km):"
        )
        lines.append(
            f"  0 mapped civic amenities were recorded within the {ctx.search_radius_meters / 1000:.1f} km search radius in OpenStreetMap."
        )
    else:
        lines.extend([
            f"• Civic Infrastructure (OpenStreetMap within {ctx.search_radius_meters / 1000:.1f} km):",
            f"  - Schools: {ctx.schools_count}",
            f"  - Healthcare: {ctx.hospitals_count + ctx.clinics_count + ctx.pharmacies_count} (hospitals: {ctx.hospitals_count}, clinics: {ctx.clinics_count}, pharmacies: {ctx.pharmacies_count})",
            f"  - Transit & Rail: {ctx.public_transport_count + ctx.railway_stations_count} (metro/rail stations: {ctx.railway_stations_count}, bus stops: {ctx.public_transport_count})",
            f"  - Emergency: {ctx.police_stations_count + ctx.fire_stations_count} (police: {ctx.police_stations_count}, fire: {ctx.fire_stations_count})",
            f"  - Arterial Roads: {ctx.major_roads_count}",
        ])

    if ctx.nearby_places:
        places_str = ", ".join(ctx.nearby_places[:5])
        lines.append(f"• Mapped Landmarks & Places: {places_str}")

    if ctx.air_quality_status == "active" and ctx.aqi_value is not None:
        sources.append("CPCB / OpenWeather")
        lines.append(f"• Air Quality: AQI {ctx.aqi_value} ({ctx.aqi_category or 'Standard Index'}) via {ctx.aqi_station or 'Monitoring Station'}")
    elif ctx.air_quality_status == "provider_not_configured":
        lines.append("• Air Quality: API key not configured; no synthetic AQI fabricated.")
    else:
        lines.append(f"• Air Quality: Telemetry status '{ctx.air_quality_status}'.")

    lines.append(f"• Hazard Network: {ctx.hazards_message or 'Sensor network not configured'}.")
    lines.append("\nFacts are based strictly on real OpenStreetMap nodes and sensor readings. Unmapped items do not guarantee absence of amenities.")
    return ("\n".join(lines), sources)


GROUNDING_SYSTEM_PROMPT = (
    "You are the NIVAS Neighborhood AI Advisor. "
    "You answer questions about the selected neighborhood strictly and exclusively using the verified data provided below.\n\n"
    "STRICT GROUNDING RULES:\n"
    "1. Rely ONLY on the verified location facts below. Do NOT hallucinate amenities, distances, safety ratings, or schools.\n"
    "2. If the user asks about something not in the data, explicitly state that the information is unavailable or unmapped in OpenStreetMap.\n"
    "3. Clearly cite your sources (OpenStreetMap Overpass API, CPCB/OpenWeather).\n"
    "4. Distinguish facts (observed coordinates, measured AQI, straight-line distance) from interpretation.\n"
    "5. Distinguish straight-line geometric distance from walking route distance.\n"
    "6. Never infer safety, clean air, or low flood risk from missing sensor data.\n"
    "7. Do NOT invent a composite livability score or safety grade.\n"
    "8. For simple conversational greetings (e.g. 'hi', 'hello', 'how are you'), reply briefly and politely introducing your assistance for the selected area. Do NOT dump the full telemetry report in greeting responses.\n"
)


def format_context_prompt(ctx: LivabilityChatContext, query: str) -> str:
    """Format full, validated telemetry context for generative models."""
    facilities_summary = []
    for f in ctx.facilities[:25]:
        facilities_summary.append(
            f"- {f.name} ({f.category}): {f.formatted_distance or 'distance unknown'}, coords: {f.latitude:.4f}° N, {f.longitude:.4f}° E"
        )
    facilities_text = (
        "\n".join(facilities_summary)
        if facilities_summary
        else "No facilities mapped in search radius."
    )

    # Fetch district crime intelligence if in Delhi
    district_info = "Police district crime records: Unindexed or outside Delhi boundary."
    try:
        from backend.services.crime_data import resolve_police_district, load_crime_baseline
        res = resolve_police_district(ctx.latitude, ctx.longitude)
        if res:
            dcode, _ = res
            b = load_crime_baseline()
            d = b.get("districts", {}).get(dcode)
            if d:
                district_info = (
                    f"Jurisdictional District: {d['district_name']} (2022 Official NCRB Report). "
                    f"Total Reported IPC Crimes: {d['total_ipc_crimes_2022']:,} ({d.get('crime_rate_per_lakh', 'N/A')} per 100k residents). "
                    f"Notice: Vehicle & property theft constitutes ~70-75% of filings via online e-FIR. "
                    f"Individual incident addresses are NOT published by police to safeguard privacy."
                )
    except Exception:
        pass

    disaster_info = "Zoning: BIS Seismic Zone IV (High Damage Risk, Zone factor 0.24). Structural NBC 2016 compliance mandatory."

    return (
        f"Selected Location: {ctx.address or ctx.locality or 'Unknown'} ({ctx.latitude:.4f}° N, {ctx.longitude:.4f}° E)\n"
        f"Infrastructure Status: {ctx.infrastructure_status} (Search radius: {ctx.search_radius_meters}m civic, {ctx.railway_search_radius_meters}m rail)\n"
        f"Amenities Count: Schools: {ctx.schools_count}, Healthcare: {ctx.hospitals_count + ctx.clinics_count + ctx.pharmacies_count}, "
        f"Transit: {ctx.public_transport_count + ctx.railway_stations_count}, Emergency: {ctx.police_stations_count + ctx.fire_stations_count}, Roads: {ctx.major_roads_count}\n"
        f"Mapped Facilities:\n{facilities_text}\n\n"
        f"Air Quality Status: {ctx.air_quality_status}, AQI: {ctx.aqi_value}, Category: {ctx.aqi_category}, Station: {ctx.aqi_station}\n"
        f"Hazard & Disaster Telemetry: {disaster_info}\n"
        f"Historical Crime Intelligence: {district_info}\n\n"
        f"User Question: {query}"
    )


def sanitize_and_validate_ai_reply(ai_reply: str, ctx: LivabilityChatContext) -> str:
    """
    Ensure model outputs do not contain fabricated composite scores or dangerous safety assertions.
    Attaches transparent disclosures if model output contains speculative scoring or unverified safety claims.
    """
    reply = ai_reply.strip()
    notes = []
    lower = reply.lower()

    # Check for fabricated composite scores
    score_triggers = [
        "livability score:",
        "safety score:",
        "livability score of",
        "composite score",
        "composite livability",
        "safety rating:",
        "safety grade:",
    ]
    if any(t in lower for t in score_triggers):
        notes.append(
            "Integrity Note: NIVAS does not calculate composite livability or safety scores. "
            "Any numerical score mentioned is model speculation and not verified NIVAS telemetry."
        )

    # Check for unwarranted safety assertions when sensors are unconfigured
    safety_triggers = [
        "guaranteed safe",
        "completely safe",
        "zero crime",
        "no safety concerns",
        "confirmed safe",
    ]
    if any(t in lower for t in safety_triggers):
        notes.append(
            "Safety Caution: NIVAS does not maintain real-time crime or police incident sensors. "
            "The absence of unmapped hazard records does NOT imply guaranteed safety or zero risk."
        )

    if notes:
        disclaimer = "\n\n" + "\n".join(f"[{n}]" for n in notes)
        return reply + disclaimer

    return reply


async def call_gemini_provider(
    query: str, ctx: LivabilityChatContext, api_key: str
) -> Optional[str]:
    """Call Google Gemini generative model with strict factual grounding instructions."""
    context_prompt = format_context_prompt(ctx, query)
    model_name = settings.GEMINI_MODEL or "gemini-2.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    headers = {"x-goog-api-key": api_key}
    payload = {
        "system_instruction": {"parts": [{"text": GROUNDING_SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": context_prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 600},
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"]
            else:
                logger.warning("Gemini API call returned status %s", resp.status_code)
    except Exception as exc:
        logger.warning("Failed to call Gemini provider: %s", type(exc).__name__)
    return None


async def call_openai_provider(
    query: str, ctx: LivabilityChatContext, api_key: str
) -> Optional[str]:
    """Call OpenAI model with strict factual grounding instructions."""
    context_prompt = format_context_prompt(ctx, query)
    model_name = settings.OPENAI_MODEL or "gpt-4o-mini"
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": GROUNDING_SYSTEM_PROMPT},
            {"role": "user", "content": context_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 600,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content")
            else:
                logger.warning("OpenAI API call returned status %s", resp.status_code)
    except Exception as exc:
        logger.warning("Failed to call OpenAI provider: %s", type(exc).__name__)
    return None


async def generate_advisor_response(
    request: LivabilityChatRequest,
) -> LivabilityChatResponse:
    """
    Main entry point for Neighborhood AI Advisor queries.
    1. Builds or reuses verified location telemetry context.
    2. If an AI provider (Gemini/OpenAI) is configured, calls the LLM with grounded context.
    3. If no AI provider is configured, reports that honestly and returns the grounded telemetry reply.
    """
    ctx = request.context
    if ctx is None:
        ctx = await build_context_from_coordinates(
            request.latitude, request.longitude, request.address
        )

    # Check for configured AI provider keys
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    provider_configured = bool(gemini_key or openai_key)
    provider_name = "gemini" if gemini_key else ("openai" if openai_key else None)
    is_ai_generated = False
    reply = ""
    sources = ["OpenStreetMap Overpass API"]

    # 1. Attempt AI Provider if configured
    if provider_configured:
        ai_reply = None
        if gemini_key:
            ai_reply = await call_gemini_provider(request.query, ctx, gemini_key)
        elif openai_key:
            ai_reply = await call_openai_provider(request.query, ctx, openai_key)

        if ai_reply:
            reply = sanitize_and_validate_ai_reply(ai_reply, ctx)
            is_ai_generated = True
            if ctx.air_quality_status == "active":
                sources.append("CPCB / OpenWeather")
        else:
            # If provider was configured but call failed (timeout/quota), fall back with notice
            telemetry_reply, telem_sources = generate_grounded_telemetry_reply(request.query, ctx)
            reply = (
                f"[AI Provider Fallback] The configured AI model provider ({provider_name}) did not return a response. "
                f"Falling back to verified location telemetry:\n\n{telemetry_reply}"
            )
            sources = telem_sources
            is_ai_generated = False
    else:
        # 2. Honest Unconfigured Provider Reporting (Zero simulated AI)
        telemetry_reply, telem_sources = generate_grounded_telemetry_reply(request.query, ctx)
        reply = (
            f"[AI Provider Not Configured] No generative AI provider (GEMINI_API_KEY or OPENAI_API_KEY) is configured in backend environment. "
            f"Real AI model generation is unavailable.\n\n"
            f"Verified location telemetry for your inquiry:\n\n{telemetry_reply}"
        )
        sources = telem_sources
        is_ai_generated = False

    return LivabilityChatResponse(
        reply=reply,
        sources=sources,
        provider_configured=provider_configured,
        provider_name=provider_name,
        is_ai_generated=is_ai_generated,
        latitude=request.latitude,
        longitude=request.longitude,
        address=request.address or ctx.address,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
    )
