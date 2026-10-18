import React, { useState, useEffect, useRef } from 'react';
import {
  AlertTriangle,
  Flame,
  Waves,
  CloudRain,
  Activity,
  MapPin,
  Compass,
  Info,
  CheckCircle2,
  ExternalLink,
  Scale,
  RefreshCw,
  Search,
  Layers,
  ArrowRight,
  ShieldAlert,
  Loader2,
  ChevronDown,
  ChevronUp,
  RotateCcw,
} from 'lucide-react';
import PropertyLocationPicker from './PropertyLocationPicker';
import { fetchDisasterHazardData, compareDisasterLocations } from '../services/api';

const safeStorage = {
  getItem: (key) => {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        return window.localStorage.getItem(key);
      }
    } catch (e) {}
    return null;
  },
  setItem: (key, val) => {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.setItem(key, val);
      }
    } catch (e) {}
  },
};

export default function DisasterWorkspace({
  location: propLocation,
  onLocationChange: propOnLocationChange,
}) {
  const [internalLocation, setInternalLocation] = useState(() => {
    const saved = safeStorage.getItem('nivas_disaster_location');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (typeof parsed.latitude === 'number' && typeof parsed.longitude === 'number' && parsed.address) {
          return parsed;
        }
      } catch (e) {}
    }
    return {
      latitude: 28.5921,
      longitude: 77.0460,
      address: 'Dwarka Sector 12, South West Delhi, Delhi',
    };
  });

  const selectedLocation = propLocation || internalLocation;
  const setSelectedLocation = (newLoc) => {
    if (typeof propOnLocationChange === 'function') {
      propOnLocationChange(newLoc);
    } else {
      setInternalLocation(newLoc);
      safeStorage.setItem('nivas_disaster_location', JSON.stringify(newLoc));
    }
  };

  const [disasterMode, setDisasterMode] = useState(() => {
    const saved = safeStorage.getItem('nivas_disaster_mode');
    return saved === 'compare' ? 'compare' : 'single';
  });

  useEffect(() => {
    safeStorage.setItem('nivas_disaster_mode', disasterMode);
  }, [disasterMode]);

  // Single Location Hazard Telemetry State
  const [hazardData, setHazardData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryTrigger, setRetryTrigger] = useState(0);

  // Layer Toggles & Configuration Panel
  const [showFloodLayer, setShowFloodLayer] = useState(true);
  const [showWaterlogLayer, setShowWaterlogLayer] = useState(true);
  const [isLayersPanelOpen, setIsLayersPanelOpen] = useState(true);

  const totalLayersCount = 2;
  const activeLayersCount = (showFloodLayer ? 1 : 0) + (showWaterlogLayer ? 1 : 0);
  const isDefaultLayers = showFloodLayer && showWaterlogLayer;

  const handleResetLayers = () => {
    setShowFloodLayer(true);
    setShowWaterlogLayer(true);
  };

  // Compare Mode State (independent from single mode)
  const [candidateLocation, setCandidateLocation] = useState({
    latitude: 28.6650,
    longitude: 77.2400,
    address: 'Yamuna Bazar, North Delhi, Delhi',
  });
  const [compareResult, setCompareResult] = useState(null);
  const [isComparing, setIsComparing] = useState(false);
  const [compareError, setCompareError] = useState(null);

  const activeReqRef = useRef(0);

  // Fetch Single Location Hazard Data
  useEffect(() => {
    if (typeof selectedLocation.latitude !== 'number' || typeof selectedLocation.longitude !== 'number') {
      return;
    }

    const reqId = ++activeReqRef.current;
    const abortCtrl = new AbortController();

    setIsLoading(true);
    setError(null);

    fetchDisasterHazardData(
      {
        latitude: selectedLocation.latitude,
        longitude: selectedLocation.longitude,
        address: selectedLocation.address,
      },
      abortCtrl.signal
    )
      .then((data) => {
        if (activeReqRef.current === reqId) {
          setHazardData(data);
          setIsLoading(false);
          setError(null);
        }
      })
      .catch((err) => {
        if (activeReqRef.current === reqId) {
          if (err.name !== 'CanceledError' && err.name !== 'AbortError') {
            setError(err.message || 'Unable to retrieve disaster telemetry');
            setIsLoading(false);
          }
        }
      });

    return () => {
      abortCtrl.abort();
    };
  }, [selectedLocation.latitude, selectedLocation.longitude, selectedLocation.address, retryTrigger]);

  // Run Comparison when in Compare Mode
  const handleRunComparison = async () => {
    setIsComparing(true);
    setCompareError(null);
    try {
      const res = await compareDisasterLocations({
        location_a: selectedLocation,
        location_b: candidateLocation,
      });
      setCompareResult(res);
      setIsComparing(false);
    } catch (err) {
      setCompareError(err.message || 'Disaster comparison failed');
      setIsComparing(false);
    }
  };

  useEffect(() => {
    if (disasterMode === 'compare' && !compareResult && !isComparing) {
      handleRunComparison();
    }
  }, [disasterMode]);

  // Filtered GeoJSON spatial layers based on UI toggles
  const activeSpatialLayers = React.useMemo(() => {
    const layers = {};
    if (showFloodLayer && hazardData?.spatial_layers?.yamuna_flood_corridor) {
      layers.yamuna_flood_corridor = hazardData.spatial_layers.yamuna_flood_corridor;
    }
    if (showWaterlogLayer && hazardData?.spatial_layers?.waterlogging_hotspots) {
      layers.waterlogging_hotspots = hazardData.spatial_layers.waterlogging_hotspots;
    }
    return layers;
  }, [showFloodLayer, showWaterlogLayer, hazardData]);

  const hazards = hazardData?.hazards || [];

  return (
    <div className="disaster-workspace-root" data-testid="disaster-workspace">
      {/* 1. Header Bar */}
      <div className="livability-workspace-header">
        <div className="livability-header-badge">
          <Activity size={14} />
          <span>Disaster & Climate Hazard Workspace</span>
        </div>
        <h1 className="livability-header-title">Geological & Environmental Hazard Intelligence</h1>
        <p className="livability-header-subtitle">
          Authoritative structural hazard zoning, riverine floodplain exposure, and urban waterlogging vulnerability grounded in official BIS IS 1893:2016, CWC, and IMD records.
        </p>
      </div>

      {/* 2. Workspace Submode Bar */}
      <div className="livability-view-mode-bar" role="tablist" aria-label="Disaster Workspace Modes">
        <button
          type="button"
          role="tab"
          aria-selected={disasterMode === 'single'}
          className={`livability-view-tab ${disasterMode === 'single' ? 'active' : ''}`}
          onClick={() => setDisasterMode('single')}
          data-testid="tab-disaster-evidence"
        >
          <Activity size={14} />
          <span>Locality Hazard Evidence</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={disasterMode === 'compare'}
          className={`livability-view-tab ${disasterMode === 'compare' ? 'active' : ''}`}
          onClick={() => setDisasterMode('compare')}
          data-testid="tab-disaster-compare"
        >
          <Scale size={14} />
          <span>Relocation Candidate Compare</span>
        </button>
      </div>

      {disasterMode === 'single' ? (
        <div className="disaster-single-flow">
          {/* Main Map Panel with Hazard Overlays */}
          <section className="card livability-map-panel" data-testid="disaster-hazard-map-panel">
            <div className="map-panel-header" data-testid="disaster-map-header">
              <div className="map-header-title-wrap">
                <MapPin size={18} className="map-header-icon" />
                <div>
                  <h3 className="map-panel-title">GIS Hazard Zoning Explorer</h3>
                  <span className="map-panel-subtitle">Official CWC Floodplain Corridor & PWD Chronic Inundation Hotspots</span>
                </div>
              </div>

              <div className="map-coords-indicator">
                <span className="coords-indicator-label">Active Focus:</span>
                <span className="coords-indicator-val">
                  {selectedLocation.latitude.toFixed(4)}° N, {selectedLocation.longitude.toFixed(4)}° E
                </span>
              </div>
            </div>

            <div className="livability-map-container">
              <PropertyLocationPicker
                latitude={selectedLocation.latitude}
                longitude={selectedLocation.longitude}
                onLocationChange={setSelectedLocation}
                searchPlaceholder="Search locality or landmark in Delhi (e.g. Yamuna Bazar, Civil Lines, Dwarka)..."
                mapHeight={380}
                geoJsonLayers={activeSpatialLayers}
              >
                {/* Compact, Collapsible Map Layers Panel */}
                <div
                  className={`hazard-layers-panel ${isLayersPanelOpen ? 'expanded' : 'collapsed'}`}
                  data-testid="hazard-layers-panel"
                >
                  <div className="hazard-layers-toolbar">
                    <button
                      type="button"
                      className="hazard-layers-toggle-btn"
                      onClick={() => setIsLayersPanelOpen((prev) => !prev)}
                      aria-expanded={isLayersPanelOpen}
                      aria-controls="hazard-layers-content"
                      data-testid="toggle-layers-panel-btn"
                    >
                      <Layers size={14} className="layers-icon" />
                      <span className="layers-title">Map Hazard Overlays</span>
                      <span className="layers-active-badge" data-testid="layers-active-count">
                        {activeLayersCount} of {totalLayersCount} Active
                      </span>
                      {isLayersPanelOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>

                    <div className="hazard-layers-toolbar-actions">
                      {!isLayersPanelOpen && (
                        <div className="collapsed-layers-preview">
                          {showFloodLayer && (
                            <span className="layer-preview-chip flood">
                              <span className="legend-dot flood" /> Yamuna Floodplain
                            </span>
                          )}
                          {showWaterlogLayer && (
                            <span className="layer-preview-chip waterlog">
                              <span className="legend-dot waterlog" /> Waterlog Hotspots
                            </span>
                          )}
                          {activeLayersCount === 0 && (
                            <span className="layer-preview-chip none">No Overlays Active</span>
                          )}
                        </div>
                      )}

                      <button
                        type="button"
                        className={`layers-reset-btn ${isDefaultLayers ? 'disabled' : ''}`}
                        onClick={handleResetLayers}
                        disabled={isDefaultLayers}
                        title="Reset layer overlays to default (all enabled)"
                        data-testid="reset-layers-btn"
                      >
                        <RotateCcw size={12} />
                        <span>Reset to Default</span>
                      </button>
                    </div>
                  </div>

                  {isLayersPanelOpen && (
                    <div
                      id="hazard-layers-content"
                      className="hazard-layers-body"
                      role="region"
                      aria-label="Hazard Map Layers Configuration"
                    >
                      <div className="hazard-layers-grid">
                        {/* Layer 1: Riverine Inundation (Yamuna Floodplain) */}
                        <div className={`hazard-layer-item ${showFloodLayer ? 'active' : 'inactive'}`}>
                          <div className="layer-item-main">
                            <div className="layer-item-header">
                              <div className="layer-badge-wrap">
                                <span className="layer-category-pill flood">Riverine Inundation</span>
                                <span className="layer-status-pill">{showFloodLayer ? 'Visible' : 'Hidden'}</span>
                              </div>
                              <label className="hazard-toggle-switch" htmlFor="toggle-flood-layer">
                                <input
                                  id="toggle-flood-layer"
                                  type="checkbox"
                                  checked={showFloodLayer}
                                  onChange={(e) => setShowFloodLayer(e.target.checked)}
                                  data-testid="layer-toggle-flood"
                                  aria-label="Toggle Yamuna River Floodplain Corridor Layer"
                                />
                                <span className="slider-round flood" />
                              </label>
                            </div>

                            <div className="layer-item-content">
                              <div className="layer-item-title-row">
                                <span className="layer-swatch-indicator flood" />
                                <h4 className="layer-item-title">Yamuna River Floodplain Corridor</h4>
                              </div>
                              <p className="layer-item-desc">
                                Authoritative Central Water Commission (CWC) riverbed macro-corridor and NGT 25-year flood inundation boundary.
                              </p>
                            </div>

                            <div className="layer-item-footer">
                              <span className="layer-source-tag">Source: CWC & NGT 2015</span>
                              <span className="layer-visual-hint">Shaded red riverbed corridor</span>
                            </div>
                          </div>
                        </div>

                        {/* Layer 2: Surface Drainage (Waterlogging Hotspots) */}
                        <div className={`hazard-layer-item ${showWaterlogLayer ? 'active' : 'inactive'}`}>
                          <div className="layer-item-main">
                            <div className="layer-item-header">
                              <div className="layer-badge-wrap">
                                <span className="layer-category-pill waterlog">Surface Drainage</span>
                                <span className="layer-status-pill">{showWaterlogLayer ? 'Visible' : 'Hidden'}</span>
                              </div>
                              <label className="hazard-toggle-switch" htmlFor="toggle-waterlog-layer">
                                <input
                                  id="toggle-waterlog-layer"
                                  type="checkbox"
                                  checked={showWaterlogLayer}
                                  onChange={(e) => setShowWaterlogLayer(e.target.checked)}
                                  data-testid="layer-toggle-waterlog"
                                  aria-label="Toggle Chronic Monsoon Waterlogging Hotspots Layer"
                                />
                                <span className="slider-round waterlog" />
                              </label>
                            </div>

                            <div className="layer-item-content">
                              <div className="layer-item-title-row">
                                <span className="layer-swatch-indicator waterlog" />
                                <h4 className="layer-item-title">Chronic Monsoon Waterlogging Hotspots</h4>
                              </div>
                              <p className="layer-item-desc">
                                Delhi Public Works Department (PWD) chronic inundation underpasses, arterial intersections, and drainage culvert choke points.
                              </p>
                            </div>

                            <div className="layer-item-footer">
                              <span className="layer-source-tag">Source: Delhi PWD Compendium</span>
                              <span className="layer-visual-hint">Amber underpass markers</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </PropertyLocationPicker>
            </div>

            <div className="disaster-map-footer">
              <div className="legend-row">
                <span className={`legend-chip ${showFloodLayer ? '' : 'layer-off'}`}>
                  <span className="legend-dot flood" /> Yamuna Floodplain Corridor (NGT Inundation Boundary)
                </span>
                <span className={`legend-chip ${showWaterlogLayer ? '' : 'layer-off'}`}>
                  <span className="legend-dot waterlog" /> Chronic Monsoon Drainage Hotspots (PWD Underpasses)
                </span>
              </div>
            </div>
          </section>

          {/* Hazard Evidence Cards Grid */}
          <div className="disaster-evidence-section">
            <div className="section-title-wrap">
              <ShieldAlert size={18} className="section-icon" />
              <div>
                <h3>Documented Hazard Evidence ({hazards.length} Categories)</h3>
                <p className="section-subtitle">
                  Location: <strong>{selectedLocation.address || `${selectedLocation.latitude.toFixed(4)}° N, ${selectedLocation.longitude.toFixed(4)}° E`}</strong>
                </p>
              </div>
            </div>

            {/* Live Alerts Availability Banner */}
            <div className="card disaster-live-status-card" data-testid="disaster-live-alerts-banner">
              <div className="live-status-header">
                <div className="live-status-left">
                  <span className={`live-status-dot ${hazardData?.live_alerts_available ? 'online' : 'offline'}`} />
                  <span className="live-status-title">
                    Live Hazard Feeds: {hazardData?.live_alerts_available ? 'Online' : 'Offline / Unavailable'}
                  </span>
                </div>
                <span className="live-status-pill">Baseline Spatial GIS</span>
              </div>
              <p className="live-status-detail">
                Dynamic reservoir discharge, real-time Doppler radar feeds, and municipal emergency broadcast APIs are not integrated. All evaluations below represent authoritative statutory standards (BIS IS 1893:2016) and historical hydrological compendiums (CWC, PWD).
              </p>
            </div>

            {isLoading && (
              <div className="card loading-card">
                <Loader2 size={24} className="spin-icon" />
                <span>Retrieving official geological and flood telemetry...</span>
              </div>
            )}

            {error && (
              <div className="card error-card">
                <AlertTriangle size={18} />
                <span>{error}</span>
              </div>
            )}

            <div className="hazard-cards-grid">
              {hazards.map((hz, idx) => {
                const isCrit = hz.severity === 'critical';
                const isHigh = hz.severity === 'high';
                const isMod = hz.severity === 'moderate';

                return (
                  <div
                    key={idx}
                    className={`card hazard-item-card severity-${hz.severity}`}
                    data-testid={`hazard-card-${hz.hazard_type}`}
                  >
                    <div className="hazard-item-header">
                      <div className="hazard-title-wrap">
                        {hz.hazard_type === 'earthquake' && <Activity size={18} className="hz-icon" />}
                        {hz.hazard_type === 'flood' && <Waves size={18} className="hz-icon" />}
                        {hz.hazard_type === 'waterlogging' && <CloudRain size={18} className="hz-icon" />}
                        {hz.hazard_type === 'heatwave' && <Flame size={18} className="hz-icon" />}
                        {hz.hazard_type === 'rainfall' && <CloudRain size={18} className="hz-icon" />}
                        <h4 className="hazard-item-title">{hz.title}</h4>
                      </div>
                      <span className={`severity-badge sev-${hz.severity || 'info'}`}>
                        {(hz.severity || 'info').toUpperCase()} EXPOSURE
                      </span>
                    </div>

                    <div className="hazard-meta-badges">
                      {hz.evidence_type && (
                        <span className="hazard-badge-evidence" data-testid={`hazard-evidence-${hz.hazard_type}`}>
                          {hz.evidence_type.replace(/_/g, ' ')}
                        </span>
                      )}
                      {hz.data_freshness && (
                        <span className="hazard-badge-freshness">
                          Freshness: {hz.data_freshness.replace(/_/g, ' ')}
                        </span>
                      )}
                      {hz.geographic_resolution && (
                        <span className="hazard-badge-resolution">
                          Resolution: {hz.geographic_resolution.replace(/_/g, ' ')}
                        </span>
                      )}
                    </div>

                    <p className="hazard-desc">{hz.description}</p>

                    <div className="hazard-mitigation-box">
                      <span className="mitigation-label">Engineering / Due Diligence Guidance:</span>
                      <p className="mitigation-text">{hz.mitigation_notes}</p>
                    </div>

                    <div className="hazard-item-footer">
                      <span className="hazard-agency">Source: {hz.source_agency}</span>
                      <a href={hz.source_url} target="_blank" rel="noopener noreferrer" className="hazard-link">
                        <span>Source</span>
                        <ExternalLink size={12} />
                      </a>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Transparency Disclosures */}
          <div className="card safety-disclosures-card">
            <div className="disclosures-header">
              <Info size={18} style={{ color: 'var(--ink-deep)' }} />
              <h3>Disaster Telemetry Disclosures & Principles</h3>
            </div>
            <ul className="disclosures-list">
              <li>Structural hazard zoning (BIS IS 1893:2016) indicates long-term engineering design requirements, not short-term disaster predictions.</li>
              <li>NIVAS does not compute a composite 'disaster safety score'; each environmental threat is presented with its independent official evidence.</li>
              <li>Absence of recorded flood inundation on upland terrain does not eliminate the risk of extreme localized cloudburst pooling.</li>
            </ul>
          </div>
        </div>
      ) : (
        /* Relocation Candidate Compare Mode */
        <div className="disaster-compare-flow" data-testid="disaster-compare-flow">
          <div className="card disaster-compare-config-card">
            <div className="compare-config-header">
              <Scale size={20} style={{ color: 'var(--ink-deep)' }} />
              <div>
                <h3>Relocation Hazard Comparison</h3>
                <p className="section-subtitle">
                  Compare documented flood, seismic, and waterlogging exposures between your current locality and a potential relocation candidate.
                </p>
              </div>
            </div>

            <div className="compare-locations-grid">
              <div className="compare-loc-box">
                <span className="compare-loc-tag">Location A (Current / Baseline)</span>
                <span className="compare-loc-name">{selectedLocation.address}</span>
                <span className="compare-loc-coords">
                  {selectedLocation.latitude.toFixed(4)}° N, {selectedLocation.longitude.toFixed(4)}° E
                </span>
              </div>

              <div className="compare-arrow-wrap">
                <ArrowRight size={20} />
              </div>

              <div className="compare-loc-box">
                <span className="compare-loc-tag candidate">Location B (Relocation Candidate)</span>
                <input
                  type="text"
                  className="compare-candidate-input"
                  aria-label="Enter candidate locality address"
                  value={candidateLocation.address}
                  onChange={(e) => setCandidateLocation((prev) => ({ ...prev, address: e.target.value }))}
                  placeholder="Enter candidate locality (e.g. Mayur Vihar, Delhi)"
                />
                <div className="candidate-presets">
                  <span className="preset-label">Quick test:</span>
                  <button
                    type="button"
                    className="preset-btn"
                    onClick={() =>
                      setCandidateLocation({
                        latitude: 28.6650,
                        longitude: 77.2400,
                        address: 'Yamuna Bazar, North Delhi, Delhi',
                      })
                    }
                  >
                    Yamuna Bazar (Floodplain)
                  </button>
                  <button
                    type="button"
                    className="preset-btn"
                    onClick={() =>
                      setCandidateLocation({
                        latitude: 28.6280,
                        longitude: 77.0850,
                        address: 'Janakpuri, West Delhi, Delhi',
                      })
                    }
                  >
                    Janakpuri (Upland)
                  </button>
                </div>
              </div>
            </div>

            <div className="compare-action-row">
              <button
                type="button"
                className="btn-primary"
                onClick={handleRunComparison}
                disabled={isComparing}
              >
                {isComparing ? (
                  <>
                    <Loader2 size={15} className="spin-icon" />
                    <span>Evaluating Hazard Exposures...</span>
                  </>
                ) : (
                  <>
                    <Scale size={15} />
                    <span>Run Relocation Hazard Comparison</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {compareError && (
            <div className="card error-card">
              <AlertTriangle size={18} />
              <span>{compareError}</span>
            </div>
          )}

          {compareResult && (
            <div className="disaster-compare-results-section">
              {compareResult.status && compareResult.status !== 'active' && (
                <div className={`card compare-status-banner status-${compareResult.status}`} data-testid="compare-status-alert">
                  <div className="compare-status-header">
                    <AlertTriangle size={18} className="compare-status-icon" />
                    <h4>
                      {compareResult.status === 'incomparable'
                        ? 'Locations Incomparable — Missing Valid Coordinates'
                        : 'Partial Evidence Available'}
                    </h4>
                  </div>
                  <p className="compare-verdict-text">{compareResult.comparison_verdict}</p>
                </div>
              )}

              {compareResult.comparison_verdict && compareResult.status === 'active' && (
                <div className="card compare-verdict-card" data-testid="compare-verdict-card">
                  <div className="verdict-header">
                    <CheckCircle2 size={18} style={{ color: 'var(--brand-forest)' }} />
                    <h4>Comparison Evaluation</h4>
                  </div>
                  <p className="compare-verdict-text">{compareResult.comparison_verdict}</p>
                </div>
              )}

              {compareResult.comparative_analysis && compareResult.comparative_analysis.length > 0 && (
                <div className="card disaster-compare-table-card">
                  <div className="card-section-header">
                    <Activity size={18} className="section-icon" />
                    <div>
                      <h3>Side-by-Side Hazard Exposure Evidence</h3>
                      <p className="section-subtitle">
                        Contrasting documented evidence from official BIS, CWC, and PWD datasets.
                      </p>
                    </div>
                  </div>

                  <div className="compare-table-responsive">
                    <table className="disaster-compare-table">
                      <thead>
                        <tr>
                          <th>Hazard Exposure</th>
                          <th>{compareResult.location_a?.locality_name || 'Location A'}</th>
                          <th>{compareResult.location_b?.locality_name || 'Location B'}</th>
                          <th>Comparative Analysis</th>
                        </tr>
                      </thead>
                      <tbody>
                        {compareResult.comparative_analysis.map((row, idx) => (
                          <tr key={idx}>
                            <td className="hazard-title-cell">
                              <strong>{row.title}</strong>
                            </td>
                            <td>
                              <span className="verdict-tag">{row.location_a_verdict}</span>
                            </td>
                            <td>
                              <span className="verdict-tag">{row.location_b_verdict}</span>
                            </td>
                            <td className="summary-cell">{row.summary}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              <div className="card safety-disclosures-card">
                <div className="disclosures-header">
                  <Info size={18} style={{ color: 'var(--ink-deep)' }} />
                  <h3>Comparison Methodology Disclosures</h3>
                </div>
                <ul className="disclosures-list">
                  {compareResult.disclaimers?.map((d, i) => (
                    <li key={i}>{d}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
