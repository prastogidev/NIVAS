from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import Field
from backend.models.score import BaseOptimizedModel


class DisasterHazardItem(BaseOptimizedModel):
    hazard_type: str = Field(..., description="Hazard key: 'earthquake', 'flood', 'waterlogging', 'heatwave', 'rainfall', 'air_quality'")
    title: str = Field(..., description="User-facing title")
    severity: str = Field(..., description="Severity indicator: 'critical', 'high', 'moderate', 'low', 'info'")
    category: str = Field(..., description="Category: 'static_zonal', 'historical_vulnerability', 'current_alert', 'forecast'")
    evidence_type: str = Field("static_zonal", description="Evidence type: 'static_zonal', 'historical_vulnerability', 'current_alert', 'forecast'")
    data_freshness: str = Field("static_standard", description="Data freshness: 'static_standard', 'historical_compendium', 'live_feed', 'unavailable'")
    geographic_resolution: str = Field("regional_statutory_standard", description="Resolution: 'regional_statutory_standard', 'macro_riverbed_corridor', 'point_infrastructure'")
    source_agency: str = Field(..., description="Authoritative source agency, e.g. BIS, CWC, IMD, NDMA")
    source_url: str = Field(..., description="Permanent documentation or source link")
    description: str = Field(..., description="Evidence-backed description of the hazard exposure")
    mitigation_notes: str = Field(..., description="Standard engineering or relocation due-diligence guidance")
    is_applicable: bool = Field(True, description="Whether this locality is exposed to this hazard")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Quantitative thresholds (e.g. seismic zone factor, flood level)")


class DisasterLocationResponse(BaseOptimizedModel):
    status: str = Field(..., description="Status: 'active', 'data_unavailable', 'fetch_failed'")
    latitude: float
    longitude: float
    address: Optional[str] = None
    locality_name: Optional[str] = None
    retrieved_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    hazards: List[DisasterHazardItem] = Field(default_factory=list)
    active_alerts_count: int = 0
    spatial_layers: Dict[str, Any] = Field(default_factory=dict, description="GeoJSON layers for Leaflet map overlay")
    live_alerts_available: bool = Field(False, description="Whether live weather/alert push APIs are active")
    live_alerts_status: str = Field(
        "unavailable",
        description="Status message explaining live emergency alerts/radars are not configured; static/historical zoning is active.",
    )
    provenance_summary: Dict[str, Any] = Field(
        default_factory=lambda: {
            "seismic": {
                "source": "Bureau of Indian Standards (BIS IS 1893:2016)",
                "scope": "Uniform statutory zoning for NCT of Delhi (Zone IV)",
                "type": "static_standard",
            },
            "flood": {
                "source": "Central Water Commission (CWC) & Delhi I&FC Department",
                "scope": "Yamuna River Old Railway Bridge gauge & active floodplain lowlands",
                "type": "historical_and_zonal",
            },
            "waterlogging": {
                "source": "Delhi Public Works Department (PWD) Chronic Waterlogging Inventory",
                "scope": "Underpasses and arterial road drainage depressions",
                "type": "historical_monsoon_vulnerability",
            },
        }
    )
    disclaimers: List[str] = Field(
        default_factory=lambda: [
            "Hazard intelligence is grounded in official government standards from BIS, CWC, and PWD.",
            "Long-term structural exposure (e.g. Seismic Zone IV) is distinct from real-time meteorological warnings.",
            "Live emergency meteorological radars/alerts are currently unavailable; all displayed data represents verified static standards and historical compendiums.",
            "NIVAS does not calculate a speculative composite 'disaster safety score'; each hazard is presented with its independent evidence.",
            "Absence of historical flood data in an unmapped depression does NOT guarantee absolute safety from extreme localized cloudbursts."
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
