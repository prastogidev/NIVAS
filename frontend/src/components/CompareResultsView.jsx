import React, { useState } from 'react';
import {
  Trophy,
  Scale,
  ShieldCheck,
  AlertTriangle,
  MapPin,
  Tag,
  Camera,
  Flame,
  Wind,
  Code2,
  ChevronDown,
  ChevronUp,
  RotateCcw,
  CheckCircle2,
  HelpCircle,
  FileText
} from 'lucide-react';

export default function CompareResultsView({ compareResult, onReset }) {
  const [showJson, setShowJson] = useState(false);

  if (!compareResult) return null;

  const {
    property_a,
    property_b,
    label_a,
    label_b,
    overall_score_a,
    overall_score_b,
    overall_delta,
    overall_winner,
    coverage_a,
    coverage_b,
    active_modules_a,
    active_modules_b,
    comparison_confidence,
    asymmetric_warning,
    module_differences,
    comparison_summary,
    key_takeaways,
  } = compareResult;

  const locA = property_a?.location;
  const locB = property_b?.location;

  const getScoreColor = (score) => {
    if (score === null || score === undefined) return '#4A4A4A';
    if (score >= 80) return '#5A9B6F';
    if (score >= 60) return '#2E7D6B';
    return '#D64545';
  };

  const getModuleIcon = (key) => {
    switch (key) {
      case 'location': return MapPin;
      case 'price': return Tag;
      case 'cv': return Camera;
      case 'thermal': return Flame;
      case 'aqi': return Wind;
      default: return Scale;
    }
  };

  const MODULE_ORDER = ['price', 'aqi', 'location', 'cv', 'thermal'];
  const orderedModuleDiffs = [...(module_differences || [])].sort((a, b) => {
    const idxA = MODULE_ORDER.indexOf(a.module_key);
    const idxB = MODULE_ORDER.indexOf(b.module_key);
    return (idxA === -1 ? 99 : idxA) - (idxB === -1 ? 99 : idxB);
  });

  const covA = coverage_a ?? property_a?.score_weight_coverage ?? 0;
  const covB = coverage_b ?? property_b?.score_weight_coverage ?? 0;
  const countA = active_modules_a ?? property_a?.active_modules_count ?? 0;
  const countB = active_modules_b ?? property_b?.active_modules_count ?? 0;
  const isAsymmetricCoverage = covA !== covB;
  const isProvisionalCompare = property_a?.is_provisional || property_b?.is_provisional;

  return (
    <div className="results-container">
      {/* Asymmetric Coverage Warning Banner */}
      {isAsymmetricCoverage && (
        <div
          className="coverage-warning-banner"
          style={{
            backgroundColor: 'rgba(180, 83, 9, 0.08)',
            border: '1px solid rgba(180, 83, 9, 0.3)',
            color: '#B45309',
            padding: '1rem 1.25rem',
            borderRadius: '12px',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '0.85rem',
          }}
        >
          <AlertTriangle size={22} style={{ flexShrink: 0, marginTop: '2px', color: '#B45309' }} />
          <div>
            <h4 style={{ fontWeight: 700, fontSize: '0.95rem', marginBottom: '0.25rem', color: '#B45309' }}>
              Limited Confidence: Asymmetric Assessment Coverage Warning
            </h4>
            <p style={{ fontSize: '0.875rem', lineHeight: '1.5', color: '#2D2D2D', margin: 0 }}>
              Property A was evaluated with <strong>{covA}%</strong> weight coverage ({countA}/4 core modules active), whereas Property B was evaluated with <strong>{covB}%</strong> weight coverage ({countB}/4 core modules active). Because each composite rating is derived from a different combination of available modules, this comparison is <strong>provisional</strong> and should not be treated as a fully equivalent valuation comparison.
            </p>
          </div>
        </div>
      )}

      {!isAsymmetricCoverage && isProvisionalCompare && (
        <div
          className="coverage-warning-banner"
          style={{
            backgroundColor: '#FAF6F6',
            border: '1px solid #F0DCDC',
            color: '#8B1E2D',
            padding: '0.85rem 1.25rem',
            borderRadius: '12px',
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
          }}
        >
          <AlertTriangle size={18} style={{ flexShrink: 0, color: '#8B1E2D' }} />
          <span style={{ fontSize: '0.875rem', color: '#2D2D2D' }}>
            <strong>Provisional Assessment:</strong> Both properties are evaluated on equal partial coverage (<strong>{covA}%</strong>). Missing modules are excluded from weighting without score penalty.
          </span>
        </div>
      )}

      {/* Top Banner: Dual Composite Gauge Comparison */}
      <div className="card score-hero-card">
        <div className="comparison-hero-grid">
          {/* Property A Circle Gauge */}
          <div className="gauge-column">
            <span className="prop-badge prop-badge-a">Property A</span>
            <div
              className="gauge-circle"
              style={{
                borderColor: getScoreColor(overall_score_a),
              }}
            >
              <span className="gauge-value" style={{ color: getScoreColor(overall_score_a) }}>
                {overall_score_a !== null ? Math.round(overall_score_a) : 'N/A'}
              </span>
              <span className="gauge-label">
                {overall_score_a !== null ? '/ 100' : 'Disconnected'}
              </span>
            </div>
            <h4 className="prop-gauge-title">{label_a}</h4>
            <div className="prop-status-row">
              {property_a.is_provisional ? (
                <span className="badge badge-warning">PROVISIONAL ({property_a.score_weight_coverage}%)</span>
              ) : (
                <span className="badge badge-success">FINAL (100%)</span>
              )}
            </div>
          </div>

          {/* Versus & Winner Column */}
          <div className="winner-column">
            <div className="versus-circle">VS</div>
            <div className="winner-box">
              <Trophy size={28} style={{ color: '#B45309', marginBottom: 4 }} />
              <div className="winner-label">
                {isAsymmetricCoverage
                  ? 'Provisional Advantage (Asymmetric Coverage)'
                  : isProvisionalCompare
                  ? 'Provisional Advantage'
                  : 'Overall Advantage'}
              </div>
              <div className="winner-name">{overall_winner}</div>
              {overall_delta !== null && (
                <div className="delta-chip">+ {overall_delta} Score Delta</div>
              )}
              {isAsymmetricCoverage && (
                <div style={{ marginTop: '0.4rem', fontSize: '0.72rem', color: '#B45309', fontWeight: 600 }}>
                  ⚠️ Limited Confidence (Coverage: {covA}% vs {covB}%)
                </div>
              )}
            </div>
          </div>

          {/* Property B Circle Gauge */}
          <div className="gauge-column">
            <span className="prop-badge prop-badge-b">Property B</span>
            <div
              className="gauge-circle"
              style={{
                borderColor: getScoreColor(overall_score_b),
              }}
            >
              <span className="gauge-value" style={{ color: getScoreColor(overall_score_b) }}>
                {overall_score_b !== null ? Math.round(overall_score_b) : 'N/A'}
              </span>
              <span className="gauge-label">
                {overall_score_b !== null ? '/ 100' : 'Disconnected'}
              </span>
            </div>
            <h4 className="prop-gauge-title">{label_b}</h4>
            <div className="prop-status-row">
              {property_b.is_provisional ? (
                <span className="badge badge-warning">PROVISIONAL ({property_b.score_weight_coverage}%)</span>
              ) : (
                <span className="badge badge-success">FINAL (100%)</span>
              )}
            </div>
          </div>
        </div>

        <div className="hero-actions">
          <button className="btn-primary" onClick={onReset}>
            <RotateCcw size={18} />
            <span>New Comparison</span>
          </button>

          <button
            className="btn-secondary"
            onClick={() => setShowJson(!showJson)}
          >
            <Code2 size={18} />
            <span>{showJson ? 'Hide Raw JSON' : 'Inspect Raw JSON Response'}</span>
            {showJson ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>

        {showJson && (
          <div className="json-container">
            <pre className="json-box">{JSON.stringify(compareResult, null, 2)}</pre>
          </div>
        )}
      </div>

      {/* Comparative Summary & Grounded Takeaways */}
      <div className="card report-card" style={{ marginBottom: '2rem' }}>
        <div className="card-header report-header">
          <FileText style={{ color: 'var(--ink-deep)' }} size={26} />
          <div>
            <h2>Comparative Executive Summary</h2>
            <p className="card-subtitle">Grounded plain-language comparison of real inspection scores</p>
          </div>
        </div>

        <div className="summary-text-box" style={{ marginBottom: '1.5rem' }}>
          <p>{comparison_summary}</p>
        </div>

        <h3>Key Comparative Takeaways & Difference Reasons</h3>
        <div className="recommendations-list">
          {key_takeaways.map((item, idx) => (
            <div key={idx} className="recommendation-item">
              <div className="rec-icon">
                <CheckCircle2 size={18} style={{ color: 'var(--success)' }} />
              </div>
              <div className="rec-text">{item}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Module-by-Module Side-by-Side Comparison */}
      <h3 className="section-title">Module-by-Module Score Breakdown</h3>
      <div className="compare-modules-list">
        {orderedModuleDiffs.map((diff) => {
          const Icon = getModuleIcon(diff.module_key);
          const isWinnerA = diff.advantage === 'Property A';
          const isWinnerB = diff.advantage === 'Property B';

          return (
            <div key={diff.module_key} className="card compare-module-card">
              <div className="compare-module-header">
                <div className="module-title">
                  <Icon size={22} style={{ color: 'var(--ink-deep)' }} />
                  <div>
                    <h4>{diff.module_label}</h4>
                    <span className="module-weight">Weight: {diff.weight_pct}</span>
                  </div>
                </div>

                <div className="advantage-badge-box">
                  {isWinnerA ? (
                    <span className="badge badge-success">Advantage: Property A</span>
                  ) : isWinnerB ? (
                    <span className="badge badge-success">Advantage: Property B</span>
                  ) : diff.advantage === 'Tie' ? (
                    <span className="badge badge-warning">Tie / Equal Score</span>
                  ) : (
                    <span className="status-badge status-null">Incomparable</span>
                  )}
                </div>
              </div>

              <div className="compare-module-scores-grid">
                {/* Score A Box */}
                <div className={`score-sub-box ${isWinnerA ? 'score-winner-box' : ''}`}>
                  <span className="sub-box-lbl">Property A Score</span>
                  {diff.score_a !== null ? (
                    <span className="sub-box-val" style={{ color: getScoreColor(diff.score_a) }}>
                      {Math.round(diff.score_a)} / 100
                    </span>
                  ) : diff.status_a === 'provider_not_configured' ? (
                    <span className="status-badge status-null">Provider not configured</span>
                  ) : diff.status_a === 'data_unavailable' ? (
                    <span className="status-badge status-null">Data unavailable</span>
                  ) : diff.fetch_failed_a || diff.status_a === 'fetch_failed' ? (
                    <div className="fetch-error-badge-wrap">
                      <span className="status-badge status-warning">Fetch Failed</span>
                      <span className="fetch-error-subtext">API Timeout</span>
                    </div>
                  ) : (
                    <span className="status-badge status-null">Not assessed</span>
                  )}
                </div>

                {/* Delta Chip */}
                <div className="delta-center-chip">
                  <span className="delta-lbl">Delta</span>
                  <span className="delta-val">
                    {diff.score_delta !== null ? `${diff.score_delta} pts` : 'N/A'}
                  </span>
                </div>

                {/* Score B Box */}
                <div className={`score-sub-box ${isWinnerB ? 'score-winner-box' : ''}`}>
                  <span className="sub-box-lbl">Property B Score</span>
                  {diff.score_b !== null ? (
                    <span className="sub-box-val" style={{ color: getScoreColor(diff.score_b) }}>
                      {Math.round(diff.score_b)} / 100
                    </span>
                  ) : diff.status_b === 'provider_not_configured' ? (
                    <span className="status-badge status-null">Provider not configured</span>
                  ) : diff.status_b === 'data_unavailable' ? (
                    <span className="status-badge status-null">Data unavailable</span>
                  ) : diff.fetch_failed_b || diff.status_b === 'fetch_failed' ? (
                    <div className="fetch-error-badge-wrap">
                      <span className="status-badge status-warning">Fetch Failed</span>
                      <span className="fetch-error-subtext">API Timeout</span>
                    </div>
                  ) : (
                    <span className="status-badge status-null">Not assessed</span>
                  )}
                </div>
              </div>

              {(diff.fetch_failed_a || diff.fetch_failed_b) && (
                <div className="fetch-error-alert-banner">
                  {diff.fetch_failed_a && (
                    <div>⚠️ <strong>Property A:</strong> {diff.error_message_a || 'Live data could not be fetched from API mirrors (request timed out).'}</div>
                  )}
                  {diff.fetch_failed_b && (
                    <div>⚠️ <strong>Property B:</strong> {diff.error_message_b || 'Live data could not be fetched from API mirrors (request timed out).'}</div>
                  )}
                </div>
              )}

              {diff.explanation && (
                <div className="module-explanation-box">
                  <strong>Dimensional Analysis:</strong> {diff.explanation}
                </div>
              )}

              <div className="module-reason-box">
                <strong>Metric Summary:</strong> {diff.reason}
              </div>

              {/* Side-by-Side Location Maps for Both Properties */}
              {diff.module_key === 'location' && (locA || locB) && (
                <div className="compare-location-maps-grid">
                  {/* Property A Map */}
                  <div className="compare-location-map-card">
                    <div className="compare-map-card-header">
                      <div className="compare-map-card-title">
                        <span className="prop-badge prop-badge-a">Property A</span>
                        <span className="compare-map-loc-name">
                          {locA?.locality || label_a || 'Property A Location'}
                        </span>
                      </div>
                      {locA?.latitude && locA?.longitude && (
                        <span className="compare-coords-tag">
                          {locA.latitude.toFixed(3)}°N, {locA.longitude.toFixed(3)}°E
                        </span>
                      )}
                    </div>
                    {locA?.latitude && locA?.longitude ? (
                      <div className="compare-map-frame-wrap">
                        <iframe
                          title={`OpenStreetMap - ${locA.locality || 'Property A'}`}
                          className="location-map-frame"
                          src={`https://www.openstreetmap.org/export/embed.html?bbox=${locA.longitude - 0.009}%2C${locA.latitude - 0.006}%2C${locA.longitude + 0.009}%2C${locA.latitude + 0.006}&layer=mapnik&marker=${locA.latitude}%2C${locA.longitude}`}
                          loading="lazy"
                        />
                      </div>
                    ) : (
                      <div className="compare-map-fallback">
                        <MapPin size={20} className="fallback-map-pin" />
                        <span>Coordinates unavailable for Property A map</span>
                      </div>
                    )}
                  </div>

                  {/* Property B Map */}
                  <div className="compare-location-map-card">
                    <div className="compare-map-card-header">
                      <div className="compare-map-card-title">
                        <span className="prop-badge prop-badge-b">Property B</span>
                        <span className="compare-map-loc-name">
                          {locB?.locality || label_b || 'Property B Location'}
                        </span>
                      </div>
                      {locB?.latitude && locB?.longitude && (
                        <span className="compare-coords-tag">
                          {locB.latitude.toFixed(3)}°N, {locB.longitude.toFixed(3)}°E
                        </span>
                      )}
                    </div>
                    {locB?.latitude && locB?.longitude ? (
                      <div className="compare-map-frame-wrap">
                        <iframe
                          title={`OpenStreetMap - ${locB.locality || 'Property B'}`}
                          className="location-map-frame"
                          src={`https://www.openstreetmap.org/export/embed.html?bbox=${locB.longitude - 0.009}%2C${locB.latitude - 0.006}%2C${locB.longitude + 0.009}%2C${locB.latitude + 0.006}&layer=mapnik&marker=${locB.latitude}%2C${locB.longitude}`}
                          loading="lazy"
                        />
                      </div>
                    ) : (
                      <div className="compare-map-fallback">
                        <MapPin size={20} className="fallback-map-pin" />
                        <span>Coordinates unavailable for Property B map</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {(diff.provenance_a || diff.provenance_b) && (
                <div className="module-provenance-row">
                  <div className="provenance-item">
                    <strong>Property A Source:</strong>
                    <span>{diff.provenance_a || 'Unavailable'}</span>
                  </div>
                  <div className="provenance-item">
                    <strong>Property B Source:</strong>
                    <span>{diff.provenance_b || 'Unavailable'}</span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
