from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import Field
from backend.models.score import BaseOptimizedModel


class DisasterHazardLayer(BaseOptimizedModel):
    layer_id: str = Field(..., description="Stable layer identifier (e.g. 'seismic_zones')")
    name: str = Field(..., description="Human-readable layer name")
    category: str = Field(..., description="Category: 'earthquake', 'flood', 'cyclone', 'landslide', 'heatwave', 'waterlogging', 'drought'")
    category_label: str = Field(..., description="User-facing category label")
    description: str = Field(..., description="Authoritative layer description")
    source_agency: str = Field(..., description="Official government source agency")
    source_url: str = Field(..., description="Official portal or publication URL")
    publication_year: Optional[int] = Field(None, description="Year of publication or standard")
    data_type: str = Field(..., description="'official_boundary', 'historical_vulnerability', 'modeled_exposure', 'point_infrastructure', 'static_zonal'")
    geographic_coverage: str = Field(..., description="Coverage scope (e.g. 'National (All 36 States & UTs)')")
    spatial_resolution: str = Field(..., description="Spatial resolution / scale")
    is_active_by_default: bool = Field(True, description="Whether enabled by default")
    visual_style: Dict[str, Any] = Field(default_factory=dict, description="Visual style configuration (colors, opacity, stroke)")
    interpretation_note: str = Field(..., description="Concise interpretation guidance")
    known_limitations: str = Field(..., description="Documented data limitations")


class DisasterLayersRegistryResponse(BaseOptimizedModel):
    version: str = "2.0.0"
    national_coverage: Dict[str, Any] = Field(default_factory=dict)
    layers: List[DisasterHazardLayer] = Field(default_factory=list)
    total_layers: int = 0


class DisasterHazardItem(BaseOptimizedModel):
    hazard_type: str = Field(..., description="Hazard key: 'earthquake', 'flood', 'waterlogging', 'cyclone', 'landslide', 'heatwave', 'rainfall', 'drought'")
    title: str = Field(..., description="User-facing title")
    severity: str = Field(..., description="Severity indicator: 'critical', 'high', 'moderate', 'low', 'info'")
    evidence_status: str = Field("evidence_found", description="Evidence status: 'evidence_found', 'no_mapped_feature', 'data_unavailable', 'source_historical', 'live_feed_unavailable'")
    category: str = Field(..., description="Category: 'static_zonal', 'historical_vulnerability', 'current_alert', 'forecast', 'modeled_exposure'")
    evidence_type: str = Field("static_zonal", description="Evidence type: 'static_zonal', 'historical_vulnerability', 'current_alert', 'forecast', 'modeled_exposure'")
    data_freshness: str = Field("static_standard", description="Data freshness: 'static_standard', 'historical_compendium', 'live_feed', 'unavailable'")
    geographic_resolution: str = Field("regional_statutory_standard", description="Resolution: 'regional_statutory_standard', 'macro_riverbed_corridor', 'point_infrastructure', 'macro_susceptibility_belt'")
    source_agency: str = Field(..., description="Authoritative source agency, e.g. BIS, CWC, IMD, NDMA, GSI")
    source_url: str = Field(..., description="Permanent documentation or source link")
    description: str = Field(..., description="Evidence-backed description of the hazard exposure")
    mitigation_notes: str = Field(..., description="Standard engineering or relocation due-diligence guidance")
    is_applicable: bool = Field(True, description="Whether this locality is exposed to this hazard")
    distance_km: Optional[float] = Field(None, description="Straight-line distance to hazard boundary if outside polygon")
    distance_description: Optional[str] = Field(None, description="Human-readable distance explanation")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Quantitative thresholds (e.g. seismic zone factor, flood level)")
    limitations: Optional[str] = Field(None, description="Important dataset limitations")


class DisasterLocationResponse(BaseOptimizedModel):
    status: str = Field(..., description="Status: 'active', 'out_of_coverage', 'data_unavailable', 'fetch_failed'")
    latitude: float
    longitude: float
    address: Optional[str] = None
    locality_name: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    retrieved_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    hazards: List[DisasterHazardItem] = Field(default_factory=list)
    active_alerts_count: int = 0
    spatial_layers: Dict[str, Any] = Field(default_factory=dict, description="GeoJSON layers for Leaflet map overlay")
    coverage_summary: Dict[str, Any] = Field(default_factory=dict, description="Coverage summary for queried location")
    live_alerts_available: bool = Field(False, description="Whether live weather/alert push APIs are active")
    live_alerts_status: str = Field(
        "unavailable",
        description="Status message explaining live emergency alerts/radars are not configured; static/historical zoning is active.",
    )
    provenance_summary: Dict[str, Any] = Field(
        default_factory=lambda: {
            "seismic": {
                "source": "Bureau of Indian Standards (BIS IS 1893:2016)",
                "scope": "All-India Statutory Seismic Zones II to V",
                "type": "static_standard",
            },
            "flood": {
                "source": "Central Water Commission (CWC) & State Flood Control Departments",
                "scope": "Major River Basins (Ganga, Brahmaputra, Yamuna, Godavari, Krishna, Mahanadi)",
                "type": "historical_and_zonal",
            },
            "cyclone": {
                "source": "NDMA National Cyclone Risk Mitigation Project (NCRMP) & IMD",
                "scope": "13 Coastal States & Union Territories (East & West Coasts)",
                "type": "modeled_exposure",
            },
            "landslide": {
                "source": "Geological Survey of India (GSI) National Landslide Susceptibility Mapping",
                "scope": "Himalayan Arc, Western Ghats & Northeast Hills (17 States/UTs)",
                "type": "modeled_exposure",
            },
            "waterlogging": {
                "source": "Delhi Public Works Department (PWD) Chronic Waterlogging Inventory",
                "scope": "Surveyed Underpasses & Arterial Drainage Depressions (NCT of Delhi)",
                "type": "point_infrastructure",
            },
        }
    )
    disclaimers: List[str] = Field(
        default_factory=lambda: [
            "Hazard intelligence is grounded strictly in official government standards from BIS, CWC, NDMA, IMD, GSI, and PWD.",
            "Long-term structural exposure (e.g. BIS Seismic Zoning) is distinct from real-time meteorological warnings.",
            "Live emergency meteorological radars and Nowcast alerts are currently offline; all displayed data represents verified statutory standards and historical compendiums.",
            "NIVAS does not calculate a speculative composite 'disaster safety score'; each environmental threat is presented with its independent evidence.",
            "Absence of mapped hazard features in a dataset must NOT be interpreted as confirmed zero risk. Ground-level micro-drainage requires site-specific engineering due diligence."
        ]
    )
    error_message: Optional[str] = None


class DisasterCompareRequest(BaseOptimizedModel):
    location_a: Dict[str, Any] = Field(..., description="{ latitude, longitude, address }")
    location_b: Dict[str, Any] = Field(..., description="{ latitude, longitude, address }")


class DisasterCompareResponse(BaseOptimizedModel):
    status: str = Field(..., description="'active', 'partial_evidence', 'incomparable', 'fetch_failed'")
    location_a: DisasterLocationResponse
    location_b: DisasterLocationResponse
    comparative_analysis: List[Dict[str, Any]] = Field(default_factory=list)
    comparison_verdict: Optional[str] = Field(None, description="Objective statement on comparability and coverage completeness")
    disclaimers: List[str] = Field(default_factory=list)
