import React, { useState, useEffect, useRef } from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  MapPin,
  Info,
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  TrendingUp,
  TrendingDown,
  Building2,
  Scale,
  Compass,
  Crosshair,
  Navigation,
  Loader2,
  RefreshCw,
  Globe,
  RotateCcw,
} from 'lucide-react';
import PropertyLocationPicker from './PropertyLocationPicker';
import { fetchSafetyData, fetchNationalSafetyOverview } from '../services/api';

export default function SafetyIntelligenceView({
  location,
  onLocationChange,
  radius = 1200,
  onRadiusChange,
  initialMode = 'overview',
}) {
  const [mapMode, setMapMode] = useState(initialMode); // 'overview' | 'inspect'
  const [safetyData, setSafetyData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryTrigger, setRetryTrigger] = useState(0);
  const [showProvenance, setShowProvenance] = useState(false);
  const [selectedYear, setSelectedYear] = useState('2022');
  const [selectedFacilityId, setSelectedFacilityId] = useState(null);

  // National overview data & state selection
  const [overviewData, setOverviewData] = useState(null);
  const [isOverviewLoading, setIsOverviewLoading] = useState(true);
  const [overviewError, setOverviewError] = useState(null);
  const [selectedStateProps, setSelectedStateProps] = useState(null);
  const [showInterpretGuide, setShowInterpretGuide] = useState(false);

  // Local actions & geolocation state
  const [isGeolocating, setIsGeolocating] = useState(false);
  const [geoNotice, setGeoNotice] = useState(null);

  const activeRequestRef = useRef(0);

  // Load national overview dataset on mount
  useEffect(() => {
    const abortController = new AbortController();
    setIsOverviewLoading(true);
    setOverviewError(null);

    fetchNationalSafetyOverview(abortController.signal)
      .then((data) => {
        setOverviewData(data);
        setIsOverviewLoading(false);
        // Default selected state to NCT of Delhi or first state
        if (data?.geojson?.features?.length > 0) {
          const delhiFeature = data.geojson.features.find((f) => f.properties?.state_code === 'IN-DL');
          setSelectedStateProps(delhiFeature ? delhiFeature.properties : data.geojson.features[0].properties);
        }
      })
      .catch((err) => {
        if (err.name !== 'CanceledError' && err.name !== 'AbortError') {
          setOverviewError(err.message || 'Failed to load national safety overview');
          setIsOverviewLoading(false);
        }
      });

    return () => {
      abortController.abort();
    };
  }, []);

  // Fetch localized district telemetry when coordinates or radius change
  useEffect(() => {
    if (typeof location.latitude !== 'number' || typeof location.longitude !== 'number') {
      return;
    }

    const reqId = ++activeRequestRef.current;
    const abortController = new AbortController();

    setIsLoading(true);
    setError(null);

    fetchSafetyData(
      {
        latitude: location.latitude,
        longitude: location.longitude,
        address: location.address,
        radius: radius,
      },
      abortController.signal
    )
      .then((data) => {
        if (activeRequestRef.current === reqId) {
          setSafetyData(data);
          setIsLoading(false);
          setError(null);
        }
      })
      .catch((err) => {
        if (activeRequestRef.current === reqId) {
          if (err.name !== 'CanceledError' && err.name !== 'AbortError') {
            setError(err.message || 'Failed to retrieve safety data');
            setIsLoading(false);
          }
        }
      });

    return () => {
      abortController.abort();
    };
  }, [location.latitude, location.longitude, location.address, radius, retryTrigger]);

  const matchedDistrict = safetyData?.matched_district;
  const categories = matchedDistrict?.categories_2022 || [];
  const historicalTrend = matchedDistrict?.historical_trend_ipc || {};
  const nearbyStations = safetyData?.nearby_police_stations || [];
  const nearestStations = safetyData?.nearest_police_stations?.length > 0
    ? safetyData.nearest_police_stations
    : (nearbyStations.length > 0 ? nearbyStations : []);
  const stateBenchmark = matchedDistrict?.state_ut_benchmark || {};
  const provenance = matchedDistrict?.provenance_details;

  // Combine station markers to display on local safety map
  const mapStationMarkers = (nearestStations.length > 0 ? nearestStations : nearbyStations).map((station, idx) => ({
    id: station.osm_id || `station_${idx}`,
    name: station.name,
    latitude: station.latitude,
    longitude: station.longitude,
    category: 'police',
    category_label: station.locality ? `Police Station (${station.locality})` : 'Police Station',
    color: '#0D9488',
    source: station.source || 'OpenStreetMap / Delhi Police Directory',
  }));

  // Geolocation handler
  const handleGeolocation = () => {
    if (!navigator.geolocation) {
      setGeoNotice('Geolocation is not supported by your browser.');
      return;
    }
    setIsGeolocating(true);
    setGeoNotice(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setIsGeolocating(false);
        const { latitude, longitude } = pos.coords;
        if (typeof onLocationChange === 'function') {
          onLocationChange({
            latitude,
            longitude,
            address: 'My Current Location',
          });
        }
      },
      (err) => {
        setIsGeolocating(false);
        setGeoNotice(`Geolocation unavailable (${err.message || 'permission denied'}).`);
      },
      { timeout: 10000, enableHighAccuracy: true }
    );
  };

  // Reset to default New Delhi coordinates
  const handleResetLocation = () => {
    setGeoNotice(null);
    if (typeof onLocationChange === 'function') {
      onLocationChange({
        latitude: 28.6139,
        longitude: 77.2090,
        address: 'Connaught Place, New Delhi',
      });
    }
  };

  return (
    <div className="safety-view-root" data-testid="safety-intelligence-view">
      {/* 1. Header Banner */}
      <div className="card safety-header-card">
        <div className="safety-header-top">
          <div className="safety-header-title-wrap">
            <div className="safety-badge">
              <ShieldCheck size={16} />
              <span>Civic Safety & Crime Intelligence</span>
            </div>
            <h2 className="safety-title">
              {matchedDistrict
                ? `${matchedDistrict.district_name} Crime Intelligence`
                : 'Delhi Police Historical Crime Intelligence'}
            </h2>
            <p className="safety-subtitle">
              Official First Information Report (FIR) compilations from the National Crime Records Bureau (NCRB) & Delhi Police. Individual incident addresses are not published to protect citizen privacy.
            </p>
          </div>

          <div className="safety-header-actions">
            <button
              type="button"
              className="btn-outline-sm"
              onClick={() => setShowProvenance(!showProvenance)}
              data-testid="toggle-provenance-btn"
              title="View source citations and data methodology"
            >
              <Info size={13} />
              <span>{showProvenance ? 'Hide Citations' : 'Source Details & Citations'}</span>
            </button>
            <button
              type="button"
              className="btn-secondary-sm"
              onClick={() => setRetryTrigger((r) => r + 1)}
              title="Refresh telemetry"
            >
              <RefreshCw size={13} className={isLoading ? 'spin-icon' : ''} />
              <span>Refresh</span>
            </button>
            <a
              href="https://ncrb.gov.in/crime-in-india.html"
              target="_blank"
              rel="noopener noreferrer"
              className="btn-outline-sm"
              title="View official government publication"
            >
              <span>NCRB Source</span>
              <ExternalLink size={13} />
            </a>
          </div>
        </div>

        {/* Expandable Traceable Provenance & Citation Details Panel */}
        {showProvenance && (
          <div className="provenance-details-panel" data-testid="provenance-panel">
            <div className="provenance-panel-header">
              <Info size={16} className="text-accent" />
              <h4>Traceable Data Provenance & Official Source Verification</h4>
            </div>
            <div className="provenance-grid">
              <div className="prov-item">
                <span className="prov-label">Authoritative Source Agency:</span>
                <span className="prov-val">{provenance?.source_agency || 'National Crime Records Bureau (NCRB) & Delhi Police'}</span>
              </div>
              <div className="prov-item">
                <span className="prov-label">Official Publication:</span>
                <span className="prov-val">{provenance?.publication || 'Crime in India (2018–2022) Annual Compendiums'}</span>
              </div>
              <div className="prov-item">
                <span className="prov-label">Official Table Citations:</span>
                <span className="prov-val">
                  {provenance?.official_table_state_ut || 'NCRB Crime in India Table 1A.1: Cognizable IPC Crimes in States/UTs'}
                  {' · '}
                  {provenance?.official_table_cities || 'Table 1B.1 (19 Metropolitan Cities)'}
                </span>
              </div>
              <div className="prov-item">
                <span className="prov-label">Official URLs:</span>
                <span className="prov-val">
                  <a href="https://ncrb.gov.in/crime-in-india.html" target="_blank" rel="noopener noreferrer" className="prov-link">
                    NCRB Crime in India Portal <ExternalLink size={11} />
                  </a>
                  {' · '}
                  <a href="https://delhipolice.gov.in/statistics" target="_blank" rel="noopener noreferrer" className="prov-link">
                    Delhi Police Statistics <ExternalLink size={11} />
                  </a>
                </span>
              </div>
              <div className="prov-item">
                <span className="prov-label">Geographic Resolution:</span>
                <span className="prov-val">{provenance?.geographic_resolution || 'NCT of Delhi State/UT Total with Police District Administrative Allocation'}</span>
              </div>
              <div className="prov-item">
                <span className="prov-label">Population Denominator Methodology:</span>
                <span className="prov-val">{provenance?.population_methodology || 'Census of India 2011 was conducted for Revenue Districts; Police District populations are derived projections used by Delhi Police.'}</span>
              </div>
              <div className="prov-item">
                <span className="prov-label">Boundary Mapping Integrity:</span>
                <span className="prov-val">{provenance?.boundary_disclaimer || 'Approximated Police District Jurisdictional Zone. Macro reference geometry for locality mapping; not an official cadastral survey boundary.'}</span>
              </div>
              <div className="prov-item">
                <span className="prov-label">e-FIR Legal Context:</span>
                <span className="prov-val">{provenance?.e_fir_theft_context || 'Over 74% of registered IPC crimes in Delhi constitute property and vehicle theft filed digitally via citizen e-FIR portals.'}</span>
              </div>
            </div>
          </div>
        )}

        {/* Status Indicators */}
        {isLoading && (
          <div className="safety-status-row loading">
            <Loader2 size={16} className="spin-icon" />
            <span>Loading official district telemetry for {location.address || 'selected location'}...</span>
          </div>
        )}

        {error && (
          <div className="safety-status-row error">
            <AlertTriangle size={16} />
            <span>Telemetry error: {error}. Map and coordinates remain active.</span>
          </div>
        )}

        {safetyData?.status === 'unknown_jurisdiction' && (
          <div className="safety-status-row warning">
            <Info size={16} />
            <span>{safetyData.error_message || 'Coordinates fall outside the National Capital Territory of Delhi.'}</span>
          </div>
        )}
      </div>

      {/* 2. Prominent Two-Mode Segmented Control */}
      <div className="safety-mode-segmented-bar" data-testid="safety-mode-bar">
        <div className="safety-mode-segmented-control" role="tablist" aria-label="Safety Intelligence Modes">
          <button
            type="button"
            role="tab"
            aria-selected={mapMode === 'overview'}
            className={`safety-mode-btn ${mapMode === 'overview' ? 'active' : ''}`}
            onClick={() => setMapMode('overview')}
            data-testid="mode-overview-btn"
          >
            <Globe size={15} />
            <span>India Safety Overview</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mapMode === 'inspect'}
            className={`safety-mode-btn ${mapMode === 'inspect' ? 'active' : ''}`}
            onClick={() => setMapMode('inspect')}
            data-testid="mode-inspect-btn"
          >
            <Crosshair size={15} />
            <span>Check My Location</span>
          </button>
        </div>
      </div>

      {/* =========================================================================
          MODE A: INDIA SAFETY OVERVIEW
          ========================================================================= */}
      {mapMode === 'overview' && (
        <div className="safety-overview-section" data-testid="safety-overview-section">
          {/* Visible Data Coverage Indicator */}
          <div className="card safety-coverage-banner" data-testid="safety-coverage-banner">
            <div className="coverage-badge-group">
              <span className="coverage-badge">
                <CheckCircle2 size={14} />
                <span>Statutory National Coverage</span>
              </span>
              <span className="coverage-status-tag">
                <strong>{overviewData?.coverage_summary?.states_with_statutory_data || 36}</strong> of {overviewData?.coverage_summary?.total_states_mapped || 36} States &amp; UTs (100% of National Jurisdiction)
              </span>
            </div>
            <div className="coverage-metrics-group">
              <div className="cov-metric">
                <span className="cov-label">Statutory Metric:</span>
                <span className="cov-val">Cognizable IPC Crime Rate per 100,000 Population</span>
              </div>
              <div className="cov-metric">
                <span className="cov-label">National Benchmark:</span>
                <span className="cov-val">
                  <strong>{overviewData?.national_benchmark_rate || 258.1}</strong> crimes/100k ({((overviewData?.total_all_india_ipc_cases || 3561379) / 1000000).toFixed(2)}M annual cases)
                </span>
              </div>
              <div className="cov-metric">
                <span className="cov-label">Authoritative Source:</span>
                <span className="cov-val">NCRB Crime in India 2022 (Table 1A.1)</span>
              </div>
            </div>
          </div>

          {/* Interactive Choropleth Map with Clear Thematic Legend */}
          <div className="card safety-map-panel" data-testid="safety-map-panel">
            <div className="safety-map-header">
              <div className="safety-map-title-wrap">
                <Globe size={18} className="section-icon" />
                <div>
                  <h3>India Statutory Safety & Crime Overview</h3>
                  <span className="map-subtitle">
                    Evidence-based statutory crime rates per 100,000 population across all 36 States &amp; Union Territories from NCRB Crime in India 2022 Table 1A.1. Click any State or Union Territory to inspect official data. Local emergency station pins are hidden to keep national map uncluttered.
                  </span>
                </div>
              </div>
            </div>

            <div className="safety-map-container">
              <PropertyLocationPicker
                latitude={location.latitude}
                longitude={location.longitude}
                onLocationChange={onLocationChange}
                mapHeight={450}
                mapMode="overview"
                thematicGeoJson={overviewData?.geojson}
                selectedStateCode={selectedStateProps?.state_code}
                onThematicFeatureClick={(props) => setSelectedStateProps(props)}
                hideSearch={true}
                showViewControls={false}
                showRadius={false}
                showSearchRadius={false}
              />
            </div>

            {/* Clear Thematic Risk Legend */}
            <div className="safety-thematic-legend" data-testid="safety-thematic-legend">
              <div className="thematic-legend-title">
                <Scale size={13} />
                <span>Statutory Classification &amp; Thresholds (NCRB Table 1A.1)</span>
              </div>
              <div className="thematic-legend-items">
                <div className="thematic-legend-chip">
                  <span className="thematic-color-swatch tier-lower" style={{ backgroundColor: '#10B981' }} />
                  <div className="thematic-chip-text">
                    <span className="thematic-chip-label">Lower Rate</span>
                    <span className="thematic-chip-range">&lt; 200 per 100k (22 States/UTs)</span>
                  </div>
                </div>
                <div className="thematic-legend-chip">
                  <span className="thematic-color-swatch tier-moderate" style={{ backgroundColor: '#F59E0B' }} />
                  <div className="thematic-chip-text">
                    <span className="thematic-chip-label">Moderate Rate</span>
                    <span className="thematic-chip-range">200–350 per 100k (10 States/UTs, National: 258.1)</span>
                  </div>
                </div>
                <div className="thematic-legend-chip">
                  <span className="thematic-color-swatch tier-higher" style={{ backgroundColor: '#EF4444' }} />
                  <div className="thematic-chip-text">
                    <span className="thematic-chip-label">Higher Recorded</span>
                    <span className="thematic-chip-range">&gt; 350 per 100k (4 States/UTs, e-FIR adoption)</span>
                  </div>
                </div>
              </div>
              <div className="thematic-legend-footnote">
                <span>Population denominators derived from 2022 Census RGI projections. Rates reflect official FIR registrations; higher reporting does not imply equivalent localized street danger.</span>
              </div>
            </div>
          </div>

          {/* Interactive State Inspection Card */}
          {selectedStateProps && (
            <div className="card state-inspection-card" data-testid="state-inspection-card">
              <div className="state-inspection-header">
                <div className="state-name-wrap">
                  <span
                    className="state-badge-pill"
                    style={{
                      backgroundColor: `${selectedStateProps.color}1F`,
                      color: selectedStateProps.color,
                      borderColor: selectedStateProps.color,
                    }}
                  >
                    {selectedStateProps.risk_tier === 'lower'
                      ? 'Lower (< 200)'
                      : selectedStateProps.risk_tier === 'moderate'
                      ? 'Moderate (200–350)'
                      : 'Higher (> 350)'}
                  </span>
                  <h3 className="state-inspection-title">{selectedStateProps.state_name}</h3>
                  <span className="state-code-tag">ISO: {selectedStateProps.state_code}</span>
                </div>
                <button
                  type="button"
                  className="btn-switch-to-location"
                  onClick={() => {
                    if (selectedStateProps.has_district_data) {
                      onLocationChange({
                        latitude: 28.6139,
                        longitude: 77.2090,
                        address: 'Connaught Place, New Delhi',
                      });
                    }
                    setMapMode('inspect');
                  }}
                  data-testid="inspect-state-btn"
                >
                  <Crosshair size={14} />
                  <span>Check Local Evidence in {selectedStateProps.state_name}</span>
                </button>
              </div>

              <div className="state-inspection-grid">
                <div className="si-item">
                  <span className="si-label">2022 Cognizable IPC Crimes</span>
                  <div className="si-val-wrap">
                    <span className="si-val">{selectedStateProps.total_ipc_cases?.toLocaleString()}</span>
                    <span className="si-unit">FIRs</span>
                  </div>
                  <span className="si-sub">Statutory State/UT aggregate (NCRB Table 1A.1)</span>
                </div>

                <div className="si-item">
                  <span className="si-label">State Crime Rate per 100k</span>
                  <div className="si-val-wrap">
                    <span className="si-val">
                      {selectedStateProps.crime_rate_per_lakh != null
                        ? selectedStateProps.crime_rate_per_lakh.toFixed(1)
                        : '—'}
                    </span>
                    <span className="si-unit">crimes/100k</span>
                  </div>
                  <span className="si-sub">
                    {selectedStateProps.crime_rate_per_lakh && overviewData?.national_benchmark_rate
                      ? `${(selectedStateProps.crime_rate_per_lakh / overviewData.national_benchmark_rate).toFixed(1)}x National Benchmark (258.1)`
                      : 'Based on 2022 Census RGI projected population'}
                  </span>
                </div>

                <div className="si-item">
                  <span className="si-label">Projected Population</span>
                  <div className="si-val-wrap">
                    <span className="si-val">
                      {selectedStateProps.projected_population_lakhs != null
                        ? selectedStateProps.projected_population_lakhs.toFixed(1)
                        : '—'}
                    </span>
                    <span className="si-unit">Lakh residents</span>
                  </div>
                  <span className="si-sub">Census of India RGI projection</span>
                </div>

                <div className="si-item">
                  <span className="si-label">Sub-District Telemetry</span>
                  <div className="si-val-wrap">
                    <span className="si-val-status">
                      {selectedStateProps.has_district_data ? 'Active (Sub-district polygons & stations)' : 'State Aggregate Only'}
                    </span>
                  </div>
                  <span className="si-sub">
                    {selectedStateProps.has_district_data ? '15 Police Districts mapped' : 'National 112 emergency coverage'}
                  </span>
                </div>
              </div>

              {selectedStateProps.e_fir_effect && (
                <div className="state-efir-note" data-testid="state-efir-note">
                  <Info size={15} />
                  <span>{selectedStateProps.e_fir_effect}</span>
                </div>
              )}
            </div>
          )}

          {/* Explanatory Guidance Accordion */}
          <div className="card how-to-interpret-card" data-testid="interpretability-guide-card">
            <button
              type="button"
              className="interpret-toggle-header"
              onClick={() => setShowInterpretGuide(!showInterpretGuide)}
              aria-expanded={showInterpretGuide}
              data-testid="toggle-interpret-guide-btn"
            >
              <div className="interpret-title-group">
                <Info size={16} className="text-accent" />
                <span className="interpret-title">How to Interpret This National Safety Map</span>
              </div>
              {showInterpretGuide ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>

            {showInterpretGuide && (
              <div className="interpret-content" data-testid="interpret-content">
                <div className="interpret-item">
                  <strong>1. Registration Volume vs. Street Victimization:</strong>
                  <p>
                    Official crime rates reflect First Information Reports (FIRs) registered by police authorities, not unmeasured victim surveys. Jurisdictions with greater public trust, accessible police stations, and digital portals register far more reports than jurisdictions where citizens encounter administrative friction in lodging complaints.
                  </p>
                </div>
                <div className="interpret-item">
                  <strong>2. Online e-FIR Portal Effect (Delhi &amp; Kerala):</strong>
                  <p>
                    In jurisdictions like Delhi, over 74% of all registered IPC offenses comprise motor vehicle and property theft filed digitally online by citizens through web and mobile apps. This inflates recorded statistical rates without reflecting heightened physical or violent street danger.
                  </p>
                </div>
                <div className="interpret-item">
                  <strong>3. Macro State Benchmark vs. Neighborhood Evidence:</strong>
                  <p>
                    State-level statutory aggregates cannot be directly extrapolated to individual property locations or residential neighborhoods. To inspect verified localized infrastructure and nearest police facilities, switch to the <strong>Check My Location</strong> mode.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* =========================================================================
          MODE B: CHECK MY LOCATION
          ========================================================================= */}
      {mapMode === 'inspect' && (
        <div className="safety-inspect-section" data-testid="safety-inspect-section">
          {/* Local Actions Toolbar */}
          <div className="safety-local-toolbar" data-testid="safety-local-toolbar">
            <div className="local-toolbar-left">
              <button
                type="button"
                className="btn-local-action"
                onClick={() => {
                  // Keep current coordinates confirmed
                }}
                data-testid="use-selected-point-btn"
                title="Confirm and inspect selected point coordinates"
              >
                <Crosshair size={14} />
                <span>Use selected point</span>
              </button>
              <button
                type="button"
                className="btn-local-action"
                onClick={handleGeolocation}
                disabled={isGeolocating}
                data-testid="use-my-location-btn"
                title="Detect current device location via browser GPS"
              >
                {isGeolocating ? <Loader2 size={14} className="spin-icon" /> : <Navigation size={14} />}
                <span>Use my location</span>
              </button>
              <button
                type="button"
                className="btn-local-action"
                onClick={handleResetLocation}
                data-testid="reset-location-btn"
                title="Reset location to New Delhi default coordinates"
              >
                <RotateCcw size={14} />
                <span>Reset location</span>
              </button>
            </div>
            <div className="local-toolbar-right">
              <button
                type="button"
                className="btn-local-action btn-return-overview"
                onClick={() => setMapMode('overview')}
                data-testid="return-overview-btn"
                title="Switch back to India-wide thematic safety overview"
              >
                <Globe size={14} />
                <span>Return to India Overview</span>
              </button>
            </div>
          </div>

          {geoNotice && (
            <div className="location-picker-notice notice-warning" role="status">
              <AlertTriangle size={13} />
              <span>{geoNotice}</span>
            </div>
          )}

          {/* Interactive Map with District Boundary & Real Police Stations */}
          <div className="card safety-map-panel" data-testid="safety-map-panel">
            <div className="safety-map-header">
              <div className="safety-map-title-wrap">
                <MapPin size={18} className="section-icon" />
                <div>
                  <h3>Police District Jurisdiction &amp; Emergency Infrastructure</h3>
                  <span className="map-subtitle">
                    Green boundary indicates indicative reference territory for {matchedDistrict ? matchedDistrict.district_name : 'Police District'} (spatial approximation; not an official cadastral boundary). Markers indicate verified physical police facilities.
                  </span>
                </div>
              </div>

              {matchedDistrict?.headquarters && (
                <div className="hq-indicator">
                  <span className="hq-label">District HQ:</span>
                  <span className="hq-val">{matchedDistrict.headquarters}</span>
                </div>
              )}
            </div>

            <div className="safety-map-container">
              <PropertyLocationPicker
                latitude={location.latitude}
                longitude={location.longitude}
                onLocationChange={onLocationChange}
                mapHeight={420}
                initialZoom={14}
                initialView="national"
                showViewControls={true}
                districtLabel={matchedDistrict?.district_name}
                radiusCircleMeters={radius}
                showRadius={false}
                showSearchRadius={false}
                selectedFacilityId={selectedFacilityId}
                onFacilitySelect={(fac) => setSelectedFacilityId(fac.id)}
                polygonCoords={matchedDistrict?.jurisdiction_polygon}
                polygonStyle={{
                  color: '#059669',
                  weight: 2.5,
                  opacity: 0.85,
                  fillColor: '#10B981',
                  fillOpacity: 0.12,
                }}
                overlayMarkers={mapStationMarkers}
                searchPlaceholder="Search address or locality in Delhi (e.g. Connaught Place, Dwarka, Rohini)..."
              />
            </div>

            {/* Unobtrusive Map GIS Legend */}
            <div className="safety-map-legend" data-testid="safety-map-legend">
              <span className="legend-chip">
                <span className="legend-swatch boundary-swatch" />
                <span>Police District Boundary (Indicative spatial approximation)</span>
              </span>
              <span className="legend-chip">
                <span className="legend-dot police-station-dot" />
                <span>Verified Physical Police Stations (OpenStreetMap)</span>
              </span>
              <span className="legend-chip">
                <span className="legend-dot user-pin-dot" />
                <span>Selected Search Location</span>
              </span>
            </div>

            <div className="safety-map-footer">
              <span className="safety-footer-text">
                Straight-line radius: <strong>{(radius / 1000).toFixed(1)} km</strong> · Physical facilities sourced from OpenStreetMap · No synthetic crime incident markers are plotted.
              </span>
            </div>
          </div>

          {/* Concise Location Evidence Assessment Card */}
          <div className="card location-evidence-card" data-testid="location-evidence-card">
            <div className="evidence-card-header">
              <div className="evidence-badge-group">
                <span className={`evidence-status-badge ${matchedDistrict ? 'status-active' : 'status-outside'}`}>
                  {matchedDistrict ? 'Verified District Telemetry Active' : 'Outside NCT of Delhi Telemetry'}
                </span>
                <span className="evidence-source-tag">NCRB &amp; OpenStreetMap Verified GIS</span>
              </div>
            </div>

            <div className="evidence-card-body">
              {matchedDistrict ? (
                <div className="evidence-summary-content">
                  <h4 className="evidence-title">
                    Selected Location: {location.address || `${location.latitude.toFixed(4)}° N, ${location.longitude.toFixed(4)}° E`}
                  </h4>
                  <div className="evidence-details-grid">
                    <div className="evidence-detail-item">
                      <span className="ed-label">Police Jurisdiction:</span>
                      <span className="ed-val">
                        <strong>{matchedDistrict.district_name}</strong> {matchedDistrict.headquarters ? `(HQ: ${matchedDistrict.headquarters})` : ''}
                      </span>
                    </div>
                    <div className="evidence-detail-item">
                      <span className="ed-label">Nearest Verified Station:</span>
                      <span className="ed-val">
                        {nearestStations.length > 0
                          ? <strong>{nearestStations[0].name} ({nearestStations[0].formatted_distance || `${nearestStations[0].distance_km} km`})</strong>
                          : 'Indexing operational stations...'}
                      </span>
                    </div>
                    <div className="evidence-detail-item">
                      <span className="ed-label">Emergency Infrastructure:</span>
                      <span className="ed-val">
                        {nearestStations.length} physical stations mapped · Dial <strong>112</strong> for national emergency dispatch
                      </span>
                    </div>
                    <div className="evidence-detail-item">
                      <span className="ed-label">Local Evidence Assessment:</span>
                      <span className="ed-val">
                        Sub-district jurisdictional reference geometry and verified police facilities loaded. No synthetic crime incident dots are fabricated.
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="evidence-summary-outside">
                  <h4 className="evidence-title">
                    Selected Location: {location.address || `${location.latitude.toFixed(4)}° N, ${location.longitude.toFixed(4)}° E`}
                  </h4>
                  <p className="outside-notice-p">
                    These coordinates fall outside the National Capital Territory of Delhi, where detailed sub-district police boundaries and localized station directories are currently active.
                  </p>
                  <p className="outside-notice-p">
                    Statutory State-level crime rates and benchmarks for this region are available in the <strong>India Safety Overview</strong> mode. For immediate emergency police assistance anywhere in India, dial <strong>112</strong>.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Official State/UT Baseline Benchmark Card (NCRB Table 1A.1) */}
          {safetyData?.official_state_crime && (
            <div className="card safety-official-benchmark-card" data-testid="official-state-benchmark">
              <div className="official-benchmark-header">
                <div className="benchmark-badge">
                  <Scale size={14} />
                  <span>Verified Official Benchmark (State/UT Level)</span>
                </div>
                <span className="benchmark-source">NCRB Crime in India 2022 · Table 1A.1</span>
              </div>
              <div className="official-benchmark-grid">
                <div className="ob-item">
                  <span className="ob-label">NCT of Delhi Total Cognizable IPC Cases</span>
                  <div className="ob-val-wrap">
                    <span className="ob-val">{safetyData.official_state_crime.total_ipc_cases?.toLocaleString()}</span>
                    <span className="ob-unit">cases (2022)</span>
                  </div>
                  <span className="ob-sub">Statutory State/UT aggregate from NCRB Table 1A.1</span>
                </div>
                <div className="ob-item">
                  <span className="ob-label">Official State Crime Rate per 100k</span>
                  <div className="ob-val-wrap">
                    <span className="ob-val">
                      {safetyData.official_state_crime.crime_rate_per_lakh != null
                        ? safetyData.official_state_crime.crime_rate_per_lakh.toFixed(1)
                        : '—'}
                    </span>
                    <span className="ob-unit">crimes/100k</span>
                  </div>
                  <span className="ob-sub">Based on 21.02M Census RGI projected population</span>
                </div>
                <div className="ob-item">
                  <span className="ob-label">Data Attribution &amp; Boundary Notice</span>
                  <div className="ob-val-wrap">
                    <span className="ob-val-text">NCRB State/UT Benchmark</span>
                  </div>
                  <span className="ob-sub">
                    District figures below are operational research estimates; Census denominators do not align with police districts.
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Key Crime Intelligence Metrics Row */}
          {matchedDistrict && (
            <div className="safety-metrics-grid" data-testid="safety-metrics-grid">
              <div className="card safety-metric-card">
                <div className="metric-header-row">
                  <span className="metric-label">2022 Reported IPC Crimes</span>
                  <span className="metric-derived-badge">Derived Estimate</span>
                </div>
                <div className="metric-value-wrap">
                  <span className="metric-num">{matchedDistrict.total_ipc_crimes_2022?.toLocaleString()}</span>
                  <span className="metric-unit">annual FIRs</span>
                </div>
                <span className="metric-foot">Operational research allocation ({matchedDistrict.district_name})</span>
              </div>

              <div className="card safety-metric-card">
                <div className="metric-header-row">
                  <span className="metric-label">Rate per 100k Population</span>
                  {matchedDistrict.crime_rate_per_lakh == null && (
                    <span className="metric-derived-badge">Suppressed</span>
                  )}
                </div>
                <div className="metric-value-wrap">
                  <span className="metric-num">
                    {matchedDistrict.crime_rate_per_lakh != null
                      ? matchedDistrict.crime_rate_per_lakh.toFixed(1)
                      : '—'}
                  </span>
                  <span className="metric-unit">
                    {matchedDistrict.crime_rate_per_lakh != null ? 'crimes/100k' : 'Unavailable'}
                  </span>
                </div>
                <span className="metric-foot">
                  {matchedDistrict.rate_unavailable_reason ||
                    (matchedDistrict.crime_rate_per_lakh != null
                      ? `Based on ${matchedDistrict.population_projection_2022?.toLocaleString()} projected residents`
                      : 'Census population denominators do not align with operational police districts')}
                </span>
              </div>

              <div className="card safety-metric-card">
                <div className="metric-header-row">
                  <span className="metric-label">Clearance / Charge-Sheet Rate</span>
                </div>
                <div className="metric-value-wrap">
                  <span className="metric-num">{matchedDistrict.clearance_rate_pct?.toFixed(1)}%</span>
                  <span className="metric-unit">disposed</span>
                </div>
                <span className="metric-foot">Police investigation completion</span>
              </div>

              <div className="card safety-metric-card">
                <div className="metric-header-row">
                  <span className="metric-label">Police Stations in Radius</span>
                </div>
                <div className="metric-value-wrap">
                  <span className="metric-num">{nearbyStations.length}</span>
                  <span className="metric-unit">within {(radius / 1000).toFixed(1)} km</span>
                </div>
                <span className="metric-foot">
                  {nearestStations.length > 0
                    ? `${nearestStations.length} nearest verified stations listed below`
                    : 'Real OpenStreetMap GIS facilities'}
                </span>
              </div>
            </div>
          )}

          {/* Categorical Breakdown Cards */}
          {categories.length > 0 && (
            <div className="card safety-categories-card">
              <div className="card-section-header">
                <Building2 size={18} className="section-icon" />
                <div>
                  <h3>Annual Crime Category Breakdown (2022)</h3>
                  <p className="section-subtitle">
                    Categorical distribution of registered Indian Penal Code (IPC) offenses for {matchedDistrict.district_name}.
                  </p>
                </div>
              </div>

              <div className="crime-categories-grid">
                {categories.map((cat, idx) => {
                  const countVal = cat.count ?? cat.reported_cases ?? 0;
                  const shareVal = cat.share_pct ?? cat.pct_of_total ?? 0;
                  const labelVal = cat.label ?? cat.category_name ?? `Category ${idx + 1}`;
                  const catId = cat.category_id ?? `cat_${idx}`;
                  return (
                    <div key={catId} className="crime-cat-item">
                      <div className="crime-cat-top">
                        <span className="crime-cat-label">{labelVal}</span>
                        <span className="crime-cat-count">
                          {typeof countVal === 'number' ? countVal.toLocaleString() : countVal} cases ({typeof shareVal === 'number' ? shareVal.toFixed(1) : shareVal}%)
                        </span>
                      </div>
                      <div className="crime-cat-bar-wrap">
                        <div
                          className={`crime-cat-bar-fill fill-${catId}`}
                          style={{ width: `${Math.min(100, Math.max(5, Number(shareVal) || 0))}%` }}
                        />
                      </div>
                      {cat.description && <p className="crime-cat-desc">{cat.description}</p>}
                    </div>
                  );
                })}
              </div>

              <div className="crime-theft-highlight-box">
                <Info size={16} />
                <div className="highlight-text">
                  <strong>High Motor Vehicle &amp; Property Theft Context:</strong> Over 70% of registered offenses in Delhi comprise motor vehicle and property theft, which are filed directly by citizens online through the Delhi Police web portal. Higher counts in commercial districts reflect digital reporting adoption rather than heightened violent physical danger.
                </div>
              </div>
            </div>
          )}

          {/* 5-Year Historical Trajectory (2018-2022) */}
          {Object.keys(historicalTrend).length > 0 && (
            <div className="card safety-trend-card">
              <div className="card-section-header">
                <TrendingUp size={18} className="section-icon" />
                <div>
                  <h3>5-Year Historical Crime Trajectory (2018–2022)</h3>
                  <p className="section-subtitle">
                    Annual registered IPC crime volume across official NCRB reporting compendiums. Click a year to inspect verified figures.
                  </p>
                </div>
              </div>

              <div className="trend-bars-container">
                {Object.entries(historicalTrend).map(([yr, cnt]) => {
                  const maxVal = Math.max(...Object.values(historicalTrend));
                  const heightPct = Math.round((cnt / maxVal) * 100);
                  const isSelected = selectedYear === yr;
                  return (
                    <div
                      key={yr}
                      className={`trend-bar-col ${isSelected ? 'selected' : ''}`}
                      onClick={() => setSelectedYear(yr)}
                      data-testid={`year-col-${yr}`}
                      style={{ cursor: 'pointer' }}
                      title={`Click to view ${yr} details`}
                    >
                      <div className="trend-bar-val">{cnt.toLocaleString()}</div>
                      <div className="trend-bar-track">
                        <div
                          className={`trend-bar-fill ${isSelected ? 'highlight' : ''}`}
                          style={{ height: `${heightPct}%` }}
                        />
                      </div>
                      <div className="trend-bar-label">
                        <strong>{yr}</strong>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Selected Year Breakdown & State/UT Benchmark Comparison */}
              {stateBenchmark[selectedYear] && (
                <div className="trend-year-focus-box" data-testid="trend-year-focus">
                  <span className="focus-badge">Year {selectedYear} Verified Telemetry</span>
                  <div className="focus-metrics-row">
                    <div className="focus-metric">
                      <span className="fm-label">{matchedDistrict.district_name} Allocation:</span>
                      <span className="fm-val">{(historicalTrend[selectedYear] || 0).toLocaleString()} IPC cases</span>
                    </div>
                    <div className="focus-metric">
                      <span className="fm-label">Official NCT of Delhi State/UT Total:</span>
                      <span className="fm-val">
                        {stateBenchmark[selectedYear].total_ipc_cases?.toLocaleString()} cases ({stateBenchmark[selectedYear].crime_rate_per_lakh} per 100k)
                      </span>
                    </div>
                    <div className="focus-metric">
                      <span className="fm-label">Official Source Table:</span>
                      <span className="fm-val">{stateBenchmark[selectedYear].source_table}</span>
                    </div>
                  </div>
                </div>
              )}

              <p className="trend-footnote">
                Notice: The lower count in 2020 reflects national COVID-19 mobility lockdowns under the Disaster Management Act. Trends resumed normalized baseline reporting in 2021–2022.
              </p>
            </div>
          )}

          {/* Genuine Nearest Police Stations Directory */}
          <div className="card safety-stations-card" data-testid="nearest-police-stations-card">
            <div className="card-section-header">
              <ShieldAlert size={18} className="section-icon" />
              <div className="section-header-text">
                <h3>Nearest Verified Police Stations Directory</h3>
                <p className="section-subtitle">
                  Verified operational police facilities sorted strictly by proximity to the selected location, distinguishing immediate neighborhood stations from regional facilities.
                </p>
              </div>
            </div>

            {nearestStations.length > 0 ? (
              <div className="police-stations-directory-grid" data-testid="police-stations-directory-grid">
                {nearestStations.map((station, idx) => {
                  const stationId = station.osm_id || `station_${idx}`;
                  const isSelected = selectedFacilityId === stationId;
                  const isWithin = Boolean(station.is_within_radius || (typeof station.distance_km === 'number' && station.distance_km <= (radius / 1000.0) + 0.005));
                  const distanceDisplay = station.formatted_distance || (station.distance_km != null ? `${station.distance_km.toFixed(1)} km` : 'Nearby');
                  const gmapsUrl = `https://www.google.com/maps/dir/?api=1&destination=${station.latitude},${station.longitude}`;

                  return (
                    <div
                      key={stationId}
                      className={`police-station-card ${isSelected ? 'selected' : ''}`}
                      data-testid={`station-card-${idx}`}
                    >
                      <div className="ps-card-main">
                        <div className="ps-header-row">
                          <div className="ps-name-group">
                            <div className={`ps-icon-badge ${isWithin ? 'in-radius' : 'out-radius'}`}>
                              <ShieldCheck size={16} />
                            </div>
                            <div className="ps-title-container">
                              <h4 className="ps-title" title={station.name}>{station.name}</h4>
                              <span className="ps-locality-text">
                                {station.locality || `${station.latitude.toFixed(4)}° N, ${station.longitude.toFixed(4)}° E`}
                              </span>
                            </div>
                          </div>

                          <div className="ps-distance-group">
                            <span className="ps-distance-badge">{distanceDisplay}</span>
                            <span className={`ps-radius-status ${isWithin ? 'status-within' : 'status-outside'}`}>
                              {isWithin ? `Within ${(radius / 1000).toFixed(1)} km` : `Outside ${(radius / 1000).toFixed(1)} km`}
                            </span>
                          </div>
                        </div>

                        <div className="ps-details-row">
                          <span className="ps-detail-item">
                            <MapPin size={11} />
                            <span>{station.latitude.toFixed(4)}° N, {station.longitude.toFixed(4)}° E</span>
                          </span>
                          <span className="ps-detail-source">{station.source || 'OpenStreetMap'}</span>
                        </div>

                        <div className="ps-card-actions">
                          <button
                            type="button"
                            className="btn-ps-action btn-ps-focus"
                            onClick={() => {
                              setSelectedFacilityId(stationId);
                              const mapEl = document.querySelector('.safety-map-panel');
                              if (mapEl) {
                                mapEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                              }
                            }}
                            title="Focus on map"
                          >
                            <Crosshair size={13} />
                            <span>Focus on Map</span>
                          </button>
                          <a
                            href={gmapsUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="btn-ps-action btn-ps-directions"
                            title="Open driving/transit directions in Google Maps"
                          >
                            <Navigation size={13} />
                            <span>Directions</span>
                            <ExternalLink size={11} />
                          </a>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="stations-fallback-notice" data-testid="stations-fallback-notice">
                <Info size={18} className="fallback-notice-icon" />
                <div className="fallback-notice-text">
                  <strong>Police facility directory temporarily unavailable.</strong>
                  <p>
                    Verified physical police stations are currently indexing for these coordinates.
                    In case of emergency in Delhi or anywhere across India, dial police control <strong>112</strong> immediately.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 3. Mandatory Transparency & Disclosures (Always Visible) */}
      <div className="card safety-disclosures-card">
        <div className="disclosures-header">
          <Info size={18} style={{ color: 'var(--ink-deep)' }} />
          <h3>Safety Data Integrity &amp; Methodology Disclosures</h3>
        </div>

        <ul className="disclosures-list">
          {safetyData?.transparency_notes?.map((note, i) => (
            <li key={i}>{note}</li>
          )) || (
            <>
              <li>Statistics represent official FIR registrations published by the National Crime Records Bureau and Delhi Police.</li>
              <li>Higher reported numbers frequently reflect higher citizen reporting willingness and e-FIR digital access rather than higher physical danger.</li>
              <li>Zero published incidents in an immediate radius must NOT be interpreted as confirmed zero crime.</li>
              <li>Coordinates reflect verified physical police stations; individual crime incident locations are never fabricated to protect privacy.</li>
            </>
          )}
        </ul>
      </div>
    </div>
  );
}
