from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class BaseOptimizedModel(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
        validate_assignment=False,
    )


class ImageInfo(BaseOptimizedModel):
    image_url: Optional[str] = Field(None, description="URL of the uploaded property image")
    image_base64: Optional[str] = Field(None, description="Base64 encoded representation of the property image")
    image_type: Optional[str] = Field(None, description="Category of image (e.g. RGB, Thermal, Defect)")


class ScoreRequest(BaseOptimizedModel):
    address: str = Field(..., description="Address or locality of the property")
    property_type: str = Field(..., description="Type of property (e.g., Apartment, Villa, Independent House)")
    image_info: Optional[ImageInfo] = Field(None, description="Optional property image metadata")


class InfrastructureSummary(BaseOptimizedModel):
    schools_count: int = 0
    hospitals_count: int = 0
    clinics_count: int = 0
    pharmacies_count: int = 0
    police_stations_count: int = 0
    fire_stations_count: int = 0
    public_transport_count: int = 0
    railway_stations_count: int = 0
    major_roads_count: int = 0
    nearby_places: List[str] = []


class LocationResult(BaseOptimizedModel):
    locality: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    risk_score: Optional[float] = Field(None, description="Transparent 0-100 infrastructure score (null if API data is missing)")
    infrastructure: Optional[InfrastructureSummary] = None



class AQIResult(BaseOptimizedModel):
    aqi_value: Optional[float] = None
    category: Optional[str] = None
    station_name: Optional[str] = None
    environmental_score: Optional[float] = Field(
        None, description="Converted 0-100 environmental score (100=pristine, 0=hazardous)"
    )




class PropertyListing(BaseOptimizedModel):
    listing_id: str
    address: str
    property_type: str
    price_per_sqft: float
    area_sqft: float
    total_price_inr: float
    source_reference: str


class PriceBenchmarkResult(BaseOptimizedModel):
    estimated_price_per_sqft: Optional[float] = None
    fairness_score: Optional[float] = None
    source: Optional[str] = None
    fetched_at: Optional[str] = None
    expiry: Optional[str] = None
    sample_count: Optional[int] = None
    actual_listings: Optional[List[PropertyListing]] = None



class CVModelResult(BaseOptimizedModel):
    predicted_class: Optional[str] = Field(None, description="Predicted wall condition class (clean, damp, algae, mold)")
    confidence: Optional[float] = Field(None, description="Model prediction confidence score (0.0 - 1.0)")
    defects_detected: Optional[List[str]] = None
    defect_coverage_ratio: Optional[float] = None
    structural_score: Optional[float] = Field(None, description="Normalized 0-100 wall condition structural score")
    is_blurry: Optional[bool] = Field(None, description="True if image blurriness exceeds quality threshold")


class ThermalModuleResult(BaseOptimizedModel):
    thermal_matrix: Optional[List[List[float]]] = Field(None, description="Real 32x24 thermal temperature frame matrix in degrees Celsius")
    min_temp: Optional[float] = Field(None, description="Minimum temperature in degrees Celsius")
    max_temp: Optional[float] = Field(None, description="Maximum temperature in degrees Celsius")
    mean_temp: Optional[float] = Field(None, description="Mean temperature in degrees Celsius")
    std_temp: Optional[float] = Field(None, description="Standard deviation of temperature matrix")
    thermal_anomaly_delta: Optional[float] = Field(None, description="Global temperature delta (max - min) in degrees Celsius")
    max_local_variation_delta: Optional[float] = Field(None, description="Maximum local temperature variation |T - Median_local| in degrees Celsius")
    anomalies_detected_count: Optional[int] = Field(None, description="Number of thermal anomaly pixels exceeding configurable threshold")
    anomaly_threshold_c: Optional[float] = Field(None, description="Configurable temperature variation threshold in degrees Celsius")
    insulation_score: Optional[float] = Field(None, description="Normalized 0-100 thermal insulation score")
    sensor_status: Optional[str] = Field(None, description="Hardware sensor connection status message")


class ReportResult(BaseOptimizedModel):
    summary: Optional[str] = None
    recommendations: Optional[List[str]] = None


class ScoreResponse(BaseOptimizedModel):
    location: Optional[LocationResult] = None
    aqi: Optional[AQIResult] = None
    aqi_status: str = Field(
        "unavailable",
        description="AQI availability: 'available' only when AQICN returns a geographically verified nearby station",
    )
    price: Optional[PriceBenchmarkResult] = None
    cv: Optional[CVModelResult] = None
    thermal: Optional[ThermalModuleResult] = None
    overall_score: Optional[float] = Field(None, description="Overall score, null if modules are disconnected")
    is_provisional: Optional[bool] = Field(None, description="True if overall score is provisional from partial module inputs")
    active_modules_count: Optional[int] = Field(None, description="Number of active modules contributing to overall score")
    score_weight_coverage: Optional[float] = Field(None, description="Percentage of total weight (0-100%) active in overall score")
    report: Optional[ReportResult] = Field(None, description="Report, null if modules are disconnected")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CompareRequest(BaseOptimizedModel):
    property_a: ScoreRequest = Field(..., description="Property A inspection request parameters")
    property_b: ScoreRequest = Field(..., description="Property B inspection request parameters")


class ModuleDifference(BaseOptimizedModel):
    module_key: str = Field(..., description="Module identifier (location, price, cv, thermal, aqi)")
    module_label: str = Field(..., description="Human-readable module title")
    weight_pct: str = Field(..., description="Configured module score weight percentage")
    score_a: Optional[float] = Field(None, description="Module score for Property A (null if disconnected)")
    score_b: Optional[float] = Field(None, description="Module score for Property B (null if disconnected)")
    score_delta: Optional[float] = Field(None, description="Absolute difference |Score_A - Score_B| if both active")
    advantage: Optional[str] = Field(None, description="Advantage label: 'Property A', 'Property B', 'Tie', or 'Incomparable'")
    reason: str = Field(..., description="Plain-language reason for difference based strictly on real metrics")


class CompareResponse(BaseOptimizedModel):
    property_a: ScoreResponse = Field(..., description="Complete ScoreResponse for Property A")
    property_b: ScoreResponse = Field(..., description="Complete ScoreResponse for Property B")
    label_a: str = Field(..., description="Identifier/Address for Property A")
    label_b: str = Field(..., description="Identifier/Address for Property B")
    overall_score_a: Optional[float] = Field(None, description="Composite score for Property A")
    overall_score_b: Optional[float] = Field(None, description="Composite score for Property B")
    overall_delta: Optional[float] = Field(None, description="Absolute composite score difference")
    overall_winner: Optional[str] = Field(None, description="Overall winning property label or 'Tie / Equivalent'")
    module_differences: List[ModuleDifference] = Field(..., description="Breakdown of differences per module")
    comparison_summary: str = Field(..., description="Plain-language comparison executive summary")
    key_takeaways: List[str] = Field(..., description="List of grounded comparative takeaways")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


