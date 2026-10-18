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
  TrendingUp,
  TrendingDown,
  Building2,
  Scale,
  Compass,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import PropertyLocationPicker from './PropertyLocationPicker';
import { fetchSafetyData } from '../services/api';

export default function SafetyIntelligenceView({
  location,
  onLocationChange,
  radius = 1200,
  onRadiusChange,
}) {
  const [safetyData, setSafetyData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryTrigger, setRetryTrigger] = useState(0);
  const [showProvenance, setShowProvenance] = useState(false);
  const [selectedYear, setSelectedYear] = useState('2022');

  const activeRequestRef = useRef(0);

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
  const policeStations = safetyData?.nearby_police_stations || [];
  const stateBenchmark = matchedDistrict?.state_ut_benchmark || {};
  const provenance = matchedDistrict?.provenance_details;

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

      {/* 2. Official State/UT Baseline Benchmark Card (NCRB Table 1A.1) */}
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
              <span className="ob-label">Data Attribution & Boundary Notice</span>
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

      {/* 3. Key Metrics Row */}
      {matchedDistrict && (
        <div className="safety-metrics-grid">
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
            <span className="metric-label">Clearance / Charge-Sheet Rate</span>
            <div className="metric-value-wrap">
              <span className="metric-num">{matchedDistrict.clearance_rate_pct?.toFixed(1)}%</span>
              <span className="metric-unit">disposed</span>
            </div>
            <span className="metric-foot">Police investigation completion</span>
          </div>

          <div className="card safety-metric-card">
            <span className="metric-label">Verified Police Stations in Radius</span>
            <div className="metric-value-wrap">
              <span className="metric-num">{policeStations.length}</span>
              <span className="metric-unit">within {(radius / 1000).toFixed(1)} km</span>
            </div>
            <span className="metric-foot">Real OpenStreetMap GIS facilities</span>
          </div>
        </div>
      )}

      {/* 4. Interactive Map with District Boundary & Real Police Stations */}
      <div className="card safety-map-panel">
        <div className="safety-map-header">
          <div className="safety-map-title-wrap">
            <MapPin size={18} className="section-icon" />
            <div>
              <h3>Police District Jurisdiction & Emergency Infrastructure</h3>
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

        <div className="safety-map-container" style={{ height: 340 }}>
          <PropertyLocationPicker
            latitude={location.latitude}
            longitude={location.longitude}
            onLocationChange={onLocationChange}
            mapHeight={340}
            radiusCircleMeters={radius}
            polygonCoords={matchedDistrict?.jurisdiction_polygon}
            polygonStyle={{
              color: '#059669',
              weight: 2.5,
              opacity: 0.85,
              fillColor: '#10B981',
              fillOpacity: 0.12,
            }}
            overlayMarkers={policeStations}
          />
        </div>

        <div className="safety-map-footer">
          <span className="safety-footer-text">
            Straight-line radius: <strong>{(radius / 1000).toFixed(1)} km</strong> · Physical facilities sourced from OpenStreetMap · No synthetic crime incident markers are plotted.
          </span>
        </div>
      </div>

      {/* 4. Categorical Breakdown Cards */}
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
              <strong>High Motor Vehicle & Property Theft Context:</strong> Over 70% of registered offenses in Delhi comprise motor vehicle and property theft, which are filed directly by citizens online through the Delhi Police web portal. Higher counts in commercial districts reflect digital reporting adoption rather than heightened violent physical danger.
            </div>
          </div>
        </div>
      )}

      {/* 5. 5-Year Historical Trajectory (2018-2022) */}
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

      {/* 6. Verified Nearby Police Stations Directory */}
      <div className="card safety-stations-card">
        <div className="card-section-header">
          <ShieldAlert size={18} className="section-icon" />
          <div>
            <h3>Verified Nearby Police Stations ({policeStations.length})</h3>
            <p className="section-subtitle">
              Physical police stations within the selected {(radius / 1000).toFixed(1)} km radius from OpenStreetMap GIS.
            </p>
          </div>
        </div>

        {policeStations.length > 0 ? (
          <div className="police-stations-list">
            {policeStations.map((station, idx) => (
              <div key={idx} className="police-station-row">
                <div className="station-icon-wrap">
                  <ShieldCheck size={18} className="station-icon" />
                </div>
                <div className="station-info">
                  <span className="station-name">{station.name}</span>
                  <span className="station-coords">
                    {station.latitude.toFixed(4)}° N, {station.longitude.toFixed(4)}° E · Verified OpenStreetMap facility
                  </span>
                </div>
                <div className="station-distance-badge">
                  <span>{station.formatted_distance || `${station.distance_km?.toFixed(2)} km`}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="stations-empty-state">
            <p>0 police stations mapped within {(radius / 1000).toFixed(1)} km in OpenStreetMap. Expand search radius to detect regional stations.</p>
          </div>
        )}
      </div>

      {/* 7. Mandatory Transparency & Disclosures */}
      <div className="card safety-disclosures-card">
        <div className="disclosures-header">
          <Info size={18} style={{ color: 'var(--ink-deep)' }} />
          <h3>Safety Data Integrity & Methodology Disclosures</h3>
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
