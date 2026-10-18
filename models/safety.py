from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import Field, field_validator
from backend.models.score import BaseOptimizedModel


class CrimeCategoryStat(BaseOptimizedModel):
    category_id: str = Field(..., description="Standardized ID: 'property_theft', 'violent', 'women_safety', 'cybercrime', 'other_ipc'")
    label: str = Field(..., description="Human-readable category label")
    count: int = Field(..., ge=0, description="Annual reported count from official police compendium")
    share_pct: float = Field(..., ge=0.0, le=100.0, description="Percentage share of total reported IPC crimes")
    description: str = Field(..., description="Category offense inclusions and details")


class DistrictCrimeProfile(BaseOptimizedModel):
    district_code: str = Field(..., description="Official police district code, e.g. 'DEL_DWK'")
    district_name: str = Field(..., description="Official police district name, e.g. 'Dwarka District'")
    headquarters: Optional[str] = Field(None, description="Headquarters or principal station")
    reporting_year: int = Field(2022, description="Latest verified official reporting year")
    source_agency: str = Field("Delhi Police & National Crime Records Bureau (NCRB)", description="Source authority")
    source_document_url: str = Field("https://ncrb.gov.in/crime-in-india.html", description="Citation URL")
    publication_date: str = Field("2023-12-03", description="Date document was published by government")
    data_retrieval_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    geographic_resolution: str = Field("police_district", description="Fixed resolution: police_district")
    population_projection_2022: Optional[int] = Field(None, description="Official projected resident population")
    total_ipc_crimes_2022: int = Field(..., ge=0, description="Total reported Indian Penal Code crimes in year")
    crime_rate_per_lakh: Optional[float] = Field(None, description="Reported crimes per 100,000 residents")
    clearance_rate_pct: Optional[float] = Field(None, description="Charge-sheeting / case disposal rate percentage")
    historical_trend_ipc: Dict[str, int] = Field(default_factory=dict, description="Multi-year trend (e.g. 2018-2022)")
    categories_2022: List[CrimeCategoryStat] = Field(default_factory=list, description="Categorical offense breakdown")
    jurisdiction_polygon: Optional[List[List[float]]] = Field(None, description="District boundary polygon [[lon, lat], ...]")
    boundary_type: str = Field(
        "spatial_approximation_reference",
        description="Type of polygon: 'spatial_approximation_reference' (macro reference zone, not cadastral)",
    )
    boundary_disclaimer: str = Field(
        "Approximated Police District Jurisdictional Zone. Macro reference geometry for locality mapping; not an official cadastral boundary published by Delhi Police or Survey of India.",
        description="Boundary precision disclaimer",
    )
    is_derived_estimate: bool = Field(
        True,
        description="Whether sub-district crime distribution is derived from regional operational allocations rather than direct census-tract publications.",
    )
    state_ut_benchmark: Optional[Dict[str, Any]] = Field(
        None,
        description="Official State/UT level totals for NCT of Delhi directly verifiable from NCRB Crime in India Table 1A.1.",
    )
    provenance_details: Optional[Dict[str, Any]] = Field(
        None,
        description="Traceable metadata: agency, official table, reporting year, publication URL, population methodology, and comparability notes.",
    )
    jurisdictional_disclaimer: str = Field(
        "District-level aggregate telemetry. Individual incidents are not geocoded to protect citizen privacy and reflect official reporting boundaries."
    )


class PoliceStationFacility(BaseOptimizedModel):
    osm_id: Optional[str] = None
    name: str = Field(..., description="Name of police station or post")
    category: str = Field("police", description="Facility category code")
    category_label: str = Field("Police Station", description="Human-readable category label")
    latitude: float = Field(..., description="Latitude coordinate from OpenStreetMap")
    longitude: float = Field(..., description="Longitude coordinate from OpenStreetMap")
    distance_km: Optional[float] = Field(None, description="Straight-line Haversine distance in km")
    formatted_distance: Optional[str] = Field(None, description="Human-readable distance string")
    source: str = Field("OpenStreetMap Overpass API", description="Underlying provider")


class LocalitySafetyResponse(BaseOptimizedModel):
    status: str = Field(..., description="Fetch status: 'active', 'unknown_jurisdiction', 'data_unavailable', 'fetch_failed'")
    latitude: float = Field(..., description="Requested latitude")
    longitude: float = Field(..., description="Requested longitude")
    address: Optional[str] = Field(None, description="Requested address or locality label")
    search_radius_meters: int = Field(1200, ge=0, le=10000, description="Radius used for filtering emergency facilities")
    matched_district: Optional[DistrictCrimeProfile] = Field(None, description="Resolved police district profile")
    nearby_police_stations: List[PoliceStationFacility] = Field(default_factory=list, description="Real police stations within radius")
    total_police_stations_in_radius: int = Field(0, description="Count of verified police stations within radius")
    transparency_notes: List[str] = Field(
        default_factory=lambda: [
            "Official historical crime statistics represent First Information Reports (FIRs) compiled by the National Crime Records Bureau and Delhi Police.",
            "High vehicle and property theft figures heavily reflect online e-FIR auto-registration rather than higher localized physical danger.",
            "Zero published incidents in an immediate neighborhood radius does NOT indicate the absence of crime.",
            "Physical police station markers reflect real OpenStreetMap GIS telemetry; individual crime incident addresses are never fabricated."
        ]
    )
    error_message: Optional[str] = None
