from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
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
    file_name: Optional[str] = Field(None, description="Original filename of the uploaded property image or video")
    video_url: Optional[str] = Field(None, description="URL of an uploaded property video for frame-based CV analysis")
    video_base64: Optional[str] = Field(None, description="Base64 encoded property video for frame-based CV analysis")
    video_type: Optional[str] = Field(None, description="Video MIME type, such as video/mp4")
    images: Optional[List[Dict[str, Any]]] = Field(None, description="List of multiple uploaded property images")
    thermal_base64: Optional[str] = Field(None, description="Dedicated base64 encoded radiometric thermal scan image")
    thermal_url: Optional[str] = Field(None, description="URL of dedicated radiometric thermal scan image")
    thermal_file_name: Optional[str] = Field(None, description="Filename of uploaded thermal scan image")


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
    fetch_status: Optional[str] = Field("active", description="Fetch status: 'active', 'fetch_failed', 'timeout', 'invalid_address', 'unassessed'")
    error_message: Optional[str] = Field(None, description="Human-readable explanation if fetch failed")



class AQIResult(BaseOptimizedModel):
    aqi_value: Optional[float] = None
    category: Optional[str] = None
    station_name: Optional[str] = None
    source: Optional[str] = Field("OpenWeather Air Pollution API", description="Underlying air quality data provider")
    scale: Optional[str] = Field("1-5 (OpenWeather)", description="Native AQI index scale")
    components: Optional[Dict[str, float]] = Field(
        None, description="Pollutant concentrations in µg/m³ (pm2_5, pm10, no2, o3, so2, co, etc.)"
    )
    environmental_score: Optional[float] = Field(
        None, description="Converted 0-100 environmental score (100=pristine, 0=hazardous)"
    )
    fetch_status: Optional[str] = Field("active", description="Fetch status: 'active', 'provider_not_configured', 'fetch_failed', 'data_unavailable', 'not_assessed'")
    error_message: Optional[str] = Field(None, description="Detailed explanation if fetch failed or unavailable")




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
    delhi_circle_category: Optional[str] = Field(None, description="Delhi circle rate category (e.g. Category B, Category G)")
    fetch_status: Optional[str] = Field("active", description="Fetch status: 'active', 'provider_not_configured', 'fetch_failed', 'data_unavailable', 'not_assessed'")
    error_message: Optional[str] = Field(None, description="Detailed explanation if price benchmark failed or unavailable")



class VisualEvidenceItem(BaseOptimizedModel):
    file_name: Optional[str] = Field(None, description="Original filename or identifier of the inspection media")
    image_url: Optional[str] = Field(None, description="Direct URL of the visual evidence image")
    image_base64: Optional[str] = Field(None, description="Base64 encoded string of the visual evidence image")
    predicted_class: str = Field(..., description="Predicted condition class (clean, damp, algae, mold, broken)")
    confidence: Optional[float] = Field(None, description="Model prediction confidence score (0.0 - 1.0)")
    is_video_frame: bool = Field(False, description="True if extracted from uploaded property video")


class CVModelResult(BaseOptimizedModel):
    predicted_class: Optional[str] = Field(None, description="Predicted wall condition class (clean, damp, algae, mold, broken)")
    confidence: Optional[float] = Field(None, description="Model prediction confidence score (0.0 - 1.0)")
    defects_detected: Optional[List[str]] = None
    defect_coverage_ratio: Optional[float] = None
    structural_score: Optional[float] = Field(None, description="Normalized 0-100 wall condition structural score")
    is_blurry: Optional[bool] = Field(None, description="True if image blurriness exceeds quality threshold")
    visual_evidence: Optional[List[VisualEvidenceItem]] = Field(
        None, description="Actual inspection images associated with visual condition findings"
    )


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


class DecisionFactor(BaseOptimizedModel):
    category: str = Field(..., description="Category: location, price, cv, thermal, aqi, composite")
    title: str = Field(..., description="Concise factor heading")
    description: str = Field(..., description="Clear explanation strictly grounded in module data")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Raw supporting evidence key-values")


class DecisionRisk(BaseOptimizedModel):
    category: str = Field(..., description="Category: location, price, cv, thermal, aqi, composite")
    severity: str = Field(..., description="Severity level: low, medium, high, critical")
    title: str = Field(..., description="Concise risk heading")
    description: str = Field(..., description="Clear explanation of the risk grounded in empirical module values")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Supporting module data points")


class RecommendedCheck(BaseOptimizedModel):
    category: str = Field(..., description="Category: legal, structural, thermal, location, financial, environmental, general")
    priority: str = Field(..., description="Priority: high, medium, standard")
    action: str = Field(..., description="Actionable inspection or verification step for the buyer")
    rationale: str = Field(..., description="Why this check is recommended based on data or missing modules")


class DecisionInsights(BaseOptimizedModel):
    verdict: str = Field(..., description="Short executive verdict, e.g. 'Strong Investment Contender', 'Fair Value - Conditional on Checks', 'Elevated Caution Required'")
    overall_interpretation: str = Field(..., description="Comprehensive explainable buyer-oriented interpretation synthesizing all active and inactive signals")
    confidence_level: str = Field(..., description="High, Medium, or Low based strictly on weight coverage & module availability")
    key_risks: List[DecisionRisk] = Field(default_factory=list, description="Empirically grounded risk factors")
    positive_factors: List[DecisionFactor] = Field(default_factory=list, description="Empirically grounded positive factors / strengths")
    recommended_checks: List[RecommendedCheck] = Field(default_factory=list, description="Targeted due diligence and inspection checks")
    coverage_summary: str = Field(..., description="Summary of evaluated vs missing assessment modules")


class ScoreResponse(BaseOptimizedModel):
    location: Optional[LocationResult] = None
    aqi: Optional[AQIResult] = None
    aqi_status: str = Field(
        "not_assessed",
        description="AQI availability: 'active', 'provider_not_configured', 'fetch_failed', 'data_unavailable', 'not_assessed'",
    )
    aqi_error: Optional[str] = Field(None, description="Human-readable explanation of AQI fetch status or failure")
    price: Optional[PriceBenchmarkResult] = None
    price_status: str = Field(
        "not_assessed",
        description="Price benchmark availability: 'active', 'provider_not_configured', 'fetch_failed', 'data_unavailable', 'not_assessed'",
    )
    price_error: Optional[str] = Field(None, description="Human-readable explanation of price benchmark fetch status or failure")
    cv: Optional[CVModelResult] = None
    thermal: Optional[ThermalModuleResult] = None
    overall_score: Optional[float] = Field(None, description="Overall score, null if modules are disconnected")
    is_provisional: Optional[bool] = Field(None, description="True if overall score is provisional from partial module inputs")
    active_modules_count: Optional[int] = Field(None, description="Number of active modules contributing to overall score")
    score_weight_coverage: Optional[float] = Field(None, description="Percentage of total weight (0-100%) active in overall score")
    decision_insights: Optional[DecisionInsights] = Field(None, description="Explainable deterministic decision layer insights")
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
    explanation: Optional[str] = Field(None, description="Detailed dimensional explanation why one is stronger or weaker")
    provenance_a: Optional[str] = Field(None, description="Data provenance/source for Property A")
    provenance_b: Optional[str] = Field(None, description="Data provenance/source for Property B")
    coverage_status: str = Field("both_active", description="Coverage status: 'both_active', 'only_a_active', 'only_b_active', 'both_null'")
    fetch_failed_a: bool = Field(False, description="True if Property A experienced a live data fetch failure or timeout")
    fetch_failed_b: bool = Field(False, description="True if Property B experienced a live data fetch failure or timeout")
    status_a: Optional[str] = Field(None, description="Detailed status for Property A: 'active', 'provider_not_configured', 'fetch_failed', 'data_unavailable', 'not_assessed'")
    status_b: Optional[str] = Field(None, description="Detailed status for Property B: 'active', 'provider_not_configured', 'fetch_failed', 'data_unavailable', 'not_assessed'")
    error_message_a: Optional[str] = Field(None, description="Detailed explanation if Property A fetch failed")
    error_message_b: Optional[str] = Field(None, description="Detailed explanation if Property B fetch failed")


class CompareResponse(BaseOptimizedModel):
    property_a: ScoreResponse = Field(..., description="Complete ScoreResponse for Property A")
    property_b: ScoreResponse = Field(..., description="Complete ScoreResponse for Property B")
    label_a: str = Field(..., description="Identifier/Address for Property A")
    label_b: str = Field(..., description="Identifier/Address for Property B")
    overall_score_a: Optional[float] = Field(None, description="Composite score for Property A")
    overall_score_b: Optional[float] = Field(None, description="Composite score for Property B")
    overall_delta: Optional[float] = Field(None, description="Absolute composite score difference")
    overall_winner: Optional[str] = Field(None, description="Overall winning property label or 'Tie / Equivalent'")
    coverage_a: float = Field(0.0, description="Score weight coverage percentage for Property A")
    coverage_b: float = Field(0.0, description="Score weight coverage percentage for Property B")
    active_modules_a: int = Field(0, description="Active module count for Property A")
    active_modules_b: int = Field(0, description="Active module count for Property B")
    comparison_confidence: str = Field("High", description="High, Medium, or Limited based on coverage parity")
    asymmetric_warning: Optional[str] = Field(None, description="Warning message if evaluation coverage is asymmetric")
    module_differences: List[ModuleDifference] = Field(..., description="Breakdown of differences per module")
    comparison_summary: str = Field(..., description="Plain-language comparison executive summary")
    key_takeaways: List[str] = Field(..., description="List of grounded comparative takeaways")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

