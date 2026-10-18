from datetime import datetime, timezone
from typing import Optional, List, Dict
from pydantic import Field, field_validator
from backend.models.score import BaseOptimizedModel


class LivabilityDataRequest(BaseOptimizedModel):
    latitude: float = Field(..., description="Latitude coordinate between -90 and 90")
    longitude: float = Field(..., description="Longitude coordinate between -180 and 180")
    address: Optional[str] = Field(None, description="Optional address or locality name")
    radius: Optional[int] = Field(1200, ge=0, le=10000, description="Search radius in meters (0m to 10000m)")

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if v < -90.0 or v > 90.0:
            raise ValueError("Latitude must be between -90.0 and 90.0 degrees")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if v < -180.0 or v > 180.0:
            raise ValueError("Longitude must be between -180.0 and 180.0 degrees")
        return v


class LivabilityFacilityItem(BaseOptimizedModel):
    id: Optional[str] = None
    name: str = Field(..., description="Verified name of the amenity or POI")
    category: str = Field(..., description="Category code (e.g. school, hospital, transit, road, police, fire)")
    category_label: str = Field(..., description="User-facing label (e.g. School, Hospital, Transit Stop)")
    latitude: float = Field(..., description="Latitude coordinate from OSM")
    longitude: float = Field(..., description="Longitude coordinate from OSM")
    source: str = Field("OpenStreetMap", description="Underlying provider")


class LivabilityInfrastructureData(BaseOptimizedModel):
    status: str = Field(..., description="Fetch status: 'active', 'fetch_failed', 'empty'")
    source: str = Field("OpenStreetMap Overpass API", description="Data provider")
    schools_count: int = 0
    hospitals_count: int = 0
    clinics_count: int = 0
    pharmacies_count: int = 0
    police_stations_count: int = 0
    fire_stations_count: int = 0
    public_transport_count: int = 0
    railway_stations_count: int = 0
    major_roads_count: int = 0
    nearby_places: List[str] = Field(default_factory=list)
    facilities: List[LivabilityFacilityItem] = Field(default_factory=list, description="Verified facilities with real coordinates")
    total_facilities: int = 0
    search_radius_meters: int = 1200
    railway_search_radius_meters: int = 2000
    error_message: Optional[str] = None


class LivabilityAirQualityData(BaseOptimizedModel):
    status: str = Field(..., description="Status: 'active', 'provider_not_configured', 'fetch_failed', 'data_unavailable'")
    source: Optional[str] = None
    scale: Optional[str] = None
    aqi_value: Optional[float] = None
    category: Optional[str] = None
    station_name: Optional[str] = None
    components: Optional[Dict[str, float]] = None
    environmental_score: Optional[float] = None
    error_message: Optional[str] = None


class LivabilityHazardData(BaseOptimizedModel):
    status: str = Field("data_not_configured", description="Telemetry status: 'data_not_configured', 'active'")
    source: Optional[str] = None
    message: str = "Real-time environmental hazard sensor network not configured for this region"


class LivabilityLocationDataResponse(BaseOptimizedModel):
    latitude: float
    longitude: float
    address: Optional[str] = None
    locality: Optional[str] = None
    retrieved_at: str
    infrastructure: LivabilityInfrastructureData
    air_quality: LivabilityAirQualityData
    environmental_hazards: LivabilityHazardData


class LivabilityChatFacilityItem(BaseOptimizedModel):
    id: Optional[str] = None
    name: str
    category: str
    category_label: Optional[str] = None
    latitude: float
    longitude: float
    distance_km: Optional[float] = None
    formatted_distance: Optional[str] = None
    source: str = "OpenStreetMap"


class LivabilityChatContext(BaseOptimizedModel):
    latitude: float
    longitude: float
    address: Optional[str] = None
    locality: Optional[str] = None
    search_radius_meters: int = 1200
    railway_search_radius_meters: int = 2000
    infrastructure_status: str = "active"
    facilities: List[LivabilityChatFacilityItem] = Field(default_factory=list)
    schools_count: int = 0
    hospitals_count: int = 0
    clinics_count: int = 0
    pharmacies_count: int = 0
    police_stations_count: int = 0
    fire_stations_count: int = 0
    public_transport_count: int = 0
    railway_stations_count: int = 0
    major_roads_count: int = 0
    nearby_places: List[str] = Field(default_factory=list)
    air_quality_status: str = "provider_not_configured"
    aqi_value: Optional[float] = None
    aqi_category: Optional[str] = None
    aqi_station: Optional[str] = None
    aqi_source: Optional[str] = None
    environmental_score: Optional[float] = None
    retrieved_at: Optional[str] = None
    hazards_status: str = "data_not_configured"
    hazards_message: Optional[str] = None


class LivabilityChatRequest(BaseOptimizedModel):
    query: str = Field(..., max_length=500, description="User question about the selected location (max 500 chars)")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude coordinate between -90 and 90")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude coordinate between -180 and 180")
    address: Optional[str] = Field(None, max_length=300, description="Optional address or locality name")
    context: Optional[LivabilityChatContext] = Field(None, description="Optional snapshot of verified location telemetry")

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Query cannot be empty or blank")
        if len(stripped) > 500:
            raise ValueError("Query exceeds maximum allowed length of 500 characters")
        return stripped


class LivabilityChatResponse(BaseOptimizedModel):
    reply: str
    sources: List[str] = Field(default_factory=list)
    provider_configured: bool
    provider_name: Optional[str] = None
    is_ai_generated: bool
    latitude: float
    longitude: float
    address: Optional[str] = None
    retrieved_at: str
