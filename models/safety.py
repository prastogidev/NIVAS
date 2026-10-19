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


class OfficialStateCrimeStat(BaseOptimizedModel):
    state_ut_name: str = Field("NCT of Delhi", description="State/UT name")
    reporting_year: int = Field(2022, description="Statutory reporting year")
    total_ipc_cases: int = Field(298988, description="Verified total cognizable IPC crimes from NCRB Table 1A.1")
    crime_rate_per_lakh: float = Field(1422.6, description="Verified official crime rate per lakh residents (RGI projected pop: 21,023,000)")
    data_status: str = Field("verified_official", description="Status is verified_official")
    is_derived_estimate: bool = Field(False, description="Whether this is a derived estimate")
    geographic_resolution: str = Field("state_ut", description="Resolution: state_ut")
    source_agency: str = Field("National Crime Records Bureau (NCRB), Ministry of Home Affairs", description="Agency")
    source_title: str = Field("Crime in India 2022", description="Document title")
    source_url: str = Field("https://ncrb.gov.in/crime-in-india.html", description="URL")
    source_table_or_page: str = Field("Table 1A.1: Cognizable IPC Crimes in States and Union Territories", description="Table reference")
    population_denominator: int = Field(21023000, description="2022 RGI Mid-Year Projected Population (210.2 Lakh)")
    population_denominator_year: int = Field(2022, description="Year of population projection")
    population_source: str = Field("Report of the Technical Group on Population Projections (RGI / Census of India)")
    multi_year_totals: Dict[str, Dict[str, Any]] = Field(
        default_factory=lambda: {
            "2018": {"total_ipc_cases": 236476, "crime_rate_per_lakh": 1215.7, "source_table": "NCRB Crime in India 2018, Table 1A.1"},
            "2019": {"total_ipc_cases": 299475, "crime_rate_per_lakh": 1518.0, "source_table": "NCRB Crime in India 2019, Table 1A.1"},
            "2020": {"total_ipc_cases": 245844, "crime_rate_per_lakh": 1228.6, "source_table": "NCRB Crime in India 2020, Table 1A.1"},
            "2021": {"total_ipc_cases": 287563, "crime_rate_per_lakh": 1410.8, "source_table": "NCRB Crime in India 2021, Table 1A.1"},
            "2022": {"total_ipc_cases": 298988, "crime_rate_per_lakh": 1422.6, "source_table": "NCRB Crime in India 2022, Table 1A.1"},
        }
    )
    limitations: str = Field(
        "NCT-wide statutory aggregate. Does not represent local neighborhood-level incident density. Over 74% of offenses represent property and vehicle thefts registered via online e-FIRs."
    )


class DistrictCrimeProfile(BaseOptimizedModel):
    district_code: str = Field(..., description="Official police district code, e.g. 'DEL_DWK'")
    district_name: str = Field(..., description="Official police district name, e.g. 'Dwarka District'")
    headquarters: Optional[str] = Field(None, description="Headquarters or principal station")
    reporting_year: int = Field(2022, description="Latest reporting year")
    source_agency: str = Field("Delhi Police & National Crime Records Bureau (NCRB)", description="Source authority")
    source_title: str = Field("Crime in India 2022 & Delhi Police Annual Review", description="Publication title")
    source_url: str = Field("https://ncrb.gov.in/crime-in-india.html", description="Citation URL")
    source_table_or_page: str = Field("Derived operational allocation from NCRB Table 1A.1 and Delhi Police Compendiums", description="Table or page")
    publication_date: str = Field("2023-12-03", description="Date document was published by government")
    data_retrieval_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    geographic_resolution: str = Field("police_district_estimate", description="Fixed resolution: police_district_estimate")
    data_status: str = Field("derived_estimate", description="Data status: 'verified_official', 'derived_estimate', 'data_unavailable'")
    is_derived_estimate: bool = Field(True, description="Whether this is a derived estimate")
    derivation_method: str = Field(
        "Administrative operational allocation from aggregate Delhi totals. Not a direct census-tract enumeration.",
        description="Method used to derive sub-district figures",
    )
    rate_unavailable_reason: str = Field(
        "Official Census population denominators do not align with operational police district boundaries; per-capita rate calculation is suppressed to avoid distortions from daytime commuter populations.",
        description="Reason why district crime rate is suppressed",
    )
    limitations: str = Field(
        "District figures are operational research allocations. Police boundaries are unverified spatial approximations; not published as cadastral GIS layers by Delhi Police or Survey of India. Per-capita crime rates and rankings are strictly suppressed.",
        description="Known limitations and uncertainties",
    )
    population_denominator_year: Optional[int] = Field(None, description="Year of census denominator if applicable")
    population_projection_2022: Optional[int] = Field(None, description="Derived projected resident population")
    total_ipc_crimes_2022: int = Field(..., ge=0, description="Estimated total Indian Penal Code crimes in year")
    crime_rate_per_lakh: Optional[float] = Field(None, description="Suppressed for derived district allocations; always None")
    clearance_rate_pct: Optional[float] = Field(None, description="Charge-sheeting / case disposal rate percentage")
    historical_trend_ipc: Dict[str, int] = Field(default_factory=dict, description="Multi-year research allocation trend")
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
    latitude: float = Field(..., description="Latitude coordinate from OpenStreetMap or official directory")
    longitude: float = Field(..., description="Longitude coordinate from OpenStreetMap or official directory")
    distance_km: Optional[float] = Field(None, description="Straight-line Haversine distance in km")
    formatted_distance: Optional[str] = Field(None, description="Human-readable distance string")
    source: str = Field("OpenStreetMap Overpass API", description="Underlying provider")
    locality: Optional[str] = Field(None, description="Locality, sector, or street name")
    is_within_radius: bool = Field(False, description="Whether facility is within user search radius")


class LocalitySafetyResponse(BaseOptimizedModel):
    status: str = Field(..., description="Fetch status: 'active', 'unknown_jurisdiction', 'data_unavailable', 'fetch_failed'")
    latitude: float = Field(..., description="Requested latitude")
    longitude: float = Field(..., description="Requested longitude")
    address: Optional[str] = Field(None, description="Requested address or locality label")
    search_radius_meters: int = Field(1200, ge=0, le=10000, description="Radius used for filtering emergency facilities")
    official_state_crime: Optional[OfficialStateCrimeStat] = Field(None, description="Verified official NCT of Delhi State/UT statistics")
    matched_district: Optional[DistrictCrimeProfile] = Field(None, description="Resolved police district profile (derived operational allocation)")
    jurisdiction_match_type: str = Field("approximate_spatial_reference", description="Type of spatial matching: 'approximate_spatial_reference' or 'none'")
    jurisdiction_disclaimer: str = Field(
        "Approximate macro reference territory. Official cadastral police district boundaries are not open data; property jurisdiction is indicative.",
        description="Jurisdiction precision disclaimer",
    )
    nearby_police_stations: List[PoliceStationFacility] = Field(default_factory=list, description="Real police stations within radius")
    nearest_police_stations: List[PoliceStationFacility] = Field(default_factory=list, description="Top nearest verified police facilities sorted by distance")
    total_police_stations_in_radius: int = Field(0, description="Count of verified police stations within radius")
    transparency_notes: List[str] = Field(
        default_factory=lambda: [
            "Official historical crime statistics are published at State/UT level (NCT of Delhi) by the National Crime Records Bureau (NCRB Table 1A.1).",
            "District-level counts represent operational administrative allocations; per-capita rates are suppressed because Census population does not align with police district boundaries.",
            "High vehicle and property theft figures heavily reflect online e-FIR auto-registration rather than higher localized physical danger.",
            "Zero published incidents in an immediate neighborhood radius does NOT indicate the absence of crime.",
            "Physical police station markers reflect real OpenStreetMap GIS telemetry; individual crime incident addresses are never fabricated."
        ]
    )
    error_message: Optional[str] = None


class StateSafetyFeatureProperties(BaseOptimizedModel):
    state_code: str = Field(..., description="Standardized State/UT code (e.g. 'IN-DL', 'IN-UP')")
    state_name: str = Field(..., description="Official State/UT name")
    reporting_year: int = Field(2022, description="Statutory NCRB reporting year")
    total_ipc_cases: Optional[int] = Field(None, ge=0, description="Total cognizable IPC cases registered in 2022")
    projected_population_lakhs: Optional[float] = Field(None, ge=0.0, description="Mid-year projected population in lakhs (RGI Census)")
    crime_rate_per_lakh: Optional[float] = Field(None, ge=0.0, description="Rate per 100,000 population from Table 1A.1")
    risk_tier: str = Field(..., description="Classification: 'lower', 'moderate', 'higher', or 'no_data'")
    tier_label: str = Field(..., description="Human-readable classification label")
    color: str = Field(..., description="Hex color: #10B981, #F59E0B, #EF4444, #94A3B8")
    fill_opacity: float = Field(0.38, ge=0.0, le=1.0, description="Leaflet polygon fill opacity")
    has_district_data: bool = Field(False, description="Whether sub-state district boundaries are currently available")
    source_citation: str = Field("NCRB Crime in India 2022, Table 1A.1: IPC Crimes in States/UTs", description="Official citation")
    legal_disclosure: str = Field("Statutory State/UT aggregate. Does not measure individual property or street-level crime.")
    e_fir_effect: Optional[str] = Field(None, description="Footnote explaining electronic FIR registration impact on reported volume")


class NationalSafetyOverviewResponse(BaseOptimizedModel):
    status: str = Field("active", description="Status: 'active' or 'data_unavailable'")
    reporting_year: int = Field(2022, description="Statutory reporting year")
    source_agency: str = Field(
        "National Crime Records Bureau (NCRB), Ministry of Home Affairs, Government of India",
        description="Official publication authority"
    )
    source_title: str = Field(
        "Crime in India 2022 (Volume I) · Table 1A.1: IPC Crimes (State/UT-wise)",
        description="Publication and table title"
    )
    source_url: str = Field("https://ncrb.gov.in/crime-in-india.html", description="Citation URL")
    national_benchmark_rate: float = Field(258.1, description="All-India average cognizable IPC crime rate per 100k population")
    total_all_india_ipc_cases: int = Field(3561379, description="All-India total cognizable IPC crime cases registered in 2022")
    classification_method: str = Field(
        "relative_comparison_against_national_benchmark",
        description="Method used for green/amber/red classification"
    )
    thresholds: Dict[str, float] = Field(
        default_factory=lambda: {
            "lower_max": 200.0,
            "moderate_max": 350.0,
            "higher_min": 350.0,
        },
        description="Classification boundaries for rate per 100k population"
    )
    color_palette: Dict[str, str] = Field(
        default_factory=lambda: {
            "lower": "#10B981",
            "moderate": "#F59E0B",
            "higher": "#EF4444",
            "no_data": "#94A3B8",
        },
        description="Color palette mapping for thematic tiers"
    )
    coverage_summary: Dict[str, Any] = Field(
        default_factory=lambda: {
            "total_states_mapped": 36,
            "states_with_statutory_data": 36,
            "states_with_subdistrict_polygons": 1,
            "coverage_percentage": 100.0,
        },
        description="Data coverage indicators"
    )
    geojson: Dict[str, Any] = Field(..., description="GeoJSON FeatureCollection with state geometries and properties")
    interpretability_guide: Dict[str, str] = Field(
        default_factory=lambda: {
            "geographic_level": "State and Union Territory statutory aggregates only. Not neighborhood or parcel level.",
            "e_fir_notice": "High recorded rates in states/UTs like Delhi heavily reflect 100% digital e-FIR registration for vehicle and property theft, rather than higher localized physical danger.",
            "relative_nature": "Green/Amber/Red reflects relative statistical comparison against the national benchmark (258.1/100k). It does not certify an individual property as absolutely safe or dangerous.",
            "inspection_distinction": "To inspect local evidence (nearby police stations, district estimates, hazard zones), switch to 'Check My Location' mode."
        }
    )

