import React, { useState } from 'react';
import {
  FileText,
  CheckCircle2,
  AlertCircle,
  Code2,
  ChevronUp,
  ChevronDown,
  RotateCcw,
  Building2,
  Clock,
  ShieldAlert,
  ArrowRight,
  Sparkles,
  ClipboardCheck,
} from 'lucide-react';

export default function ReportScreen({ result, onReset }) {
  const [showJson, setShowJson] = useState(false);

  if (!result) return null;

  const {
    report,
    overall_score,
    is_provisional,
    active_modules_count,
    score_weight_coverage,
    decision_insights,
    timestamp,
    location
  } = result;

  return (
    <div className="report-container">
      <div className="card report-card">
        <div className="card-header report-header">
          <FileText style={{ color: 'var(--ink-deep)' }} size={28} />
          <div>
            <h2>NIVAS Plain-Language Inspection Report</h2>
            <p className="card-subtitle">
              Locality: {location?.locality || 'Target Property'} &bull; Generated on {new Date(timestamp).toLocaleString()}
            </p>
          </div>
        </div>

        {/* Explainable Decision Verdict if available */}
        {decision_insights && (
          <div className="decision-verdict-card" style={{ marginTop: '1rem', marginBottom: '1.25rem' }}>
            <div className="decision-verdict-header">
              <div className="decision-verdict-title">
                <Sparkles size={22} style={{ color: 'var(--ink-deep)' }} />
                <div>
                  <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
                    Buyer Decision Verdict
                  </span>
                  <h3 style={{ fontSize: '1.15rem' }}>{decision_insights.verdict}</h3>
                </div>
              </div>
              <div className={`confidence-badge confidence-${decision_insights.confidence_level.toLowerCase()}`}>
                <span>{decision_insights.confidence_level} Confidence ({score_weight_coverage}% Coverage)</span>
              </div>
            </div>
            <p className="decision-summary-text" style={{ fontSize: '0.9rem', marginBottom: 0 }}>
              {decision_insights.overall_interpretation}
            </p>
          </div>
        )}

        {/* Executive Summary Box */}
        <div className="summary-section">
          <h3>Executive Summary</h3>
          <div className="summary-text-box">
            <p>{report?.summary || 'No plain-language summary available from inspection engine.'}</p>
          </div>
        </div>

        {/* Key Recommendations & Checks */}
        <div className="recommendations-section">
          <h3>Actionable Buyer Recommendations & Due Diligence</h3>
          {decision_insights?.recommended_checks && decision_insights.recommended_checks.length > 0 ? (
            <div className="recommendations-list">
              {decision_insights.recommended_checks.map((chk, idx) => (
                <div key={idx} className="recommendation-item">
                  <div className="rec-icon">
                    {chk.priority === 'high' ? (
                      <ShieldAlert size={18} style={{ color: 'var(--danger)' }} />
                    ) : (
                      <CheckCircle2 size={18} style={{ color: 'var(--success)' }} />
                    )}
                  </div>
                  <div className="rec-text">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                      <span className={`priority-tag priority-${chk.priority}`}>{chk.priority}</span>
                      <strong style={{ fontSize: '0.88rem' }}>{chk.action}</strong>
                    </div>
                    <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: 0 }}>{chk.rationale}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : report?.recommendations && report.recommendations.length > 0 ? (
            <div className="recommendations-list">
              {report.recommendations.map((rec, idx) => (
                <div key={idx} className="recommendation-item">
                  <div className="rec-icon">
                    {rec.toLowerCase().includes('critical') || rec.toLowerCase().includes('mold') || rec.toLowerCase().includes('damp') ? (
                      <ShieldAlert size={18} style={{ color: 'var(--danger)' }} />
                    ) : (
                      <CheckCircle2 size={18} style={{ color: 'var(--success)' }} />
                    )}
                  </div>
                  <div className="rec-text">{rec}</div>
                </div>
              ))}
            </div>
          ) : (
            <p className="no-rec-msg">No critical property recommendations flagged for current active module results.</p>
          )}
        </div>

        {/* Technical Data Transparency Section */}
        <div className="transparency-section">
          <h3>Inspection Score Breakdown</h3>
          <table className="score-table">
            <thead>
              <tr>
                <th>Module Name</th>
                <th>Evaluation Weight</th>
                <th>Status</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Location & Infrastructure</td>
                <td>25%</td>
                <td>
                  {result.location?.risk_score !== null ? (
                    <span className="status-badge status-active">Active</span>
                  ) : result.location?.fetch_status === 'fetch_failed' ? (
                    <span className="status-badge status-warning">Fetch Failed</span>
                  ) : (
                    <span className="status-badge status-null">Not assessed</span>
                  )}
                </td>
                <td>{result.location?.risk_score !== null ? `${Math.round(result.location.risk_score)} / 100` : 'N/A'}</td>
              </tr>
              <tr>
                <td>Price Benchmark</td>
                <td>25%</td>
                <td>{result.price?.fairness_score !== null ? <span className="status-badge status-active">Active</span> : <span className="status-badge status-null">Not assessed</span>}</td>
                <td>{result.price?.fairness_score !== null ? `${Math.round(result.price.fairness_score)} / 100` : 'N/A'}</td>
              </tr>
              <tr>
                <td>Computer Vision Wall Defect</td>
                <td>30%</td>
                <td>{result.cv?.structural_score !== null ? <span className="status-badge status-active">Active</span> : <span className="status-badge status-null">Not assessed</span>}</td>
                <td>{result.cv?.structural_score !== null ? `${Math.round(result.cv.structural_score)} / 100` : 'N/A'}</td>
              </tr>
              <tr>
                <td>Thermal Insulation & Sensor</td>
                <td>20%</td>
                <td>{result.thermal?.insulation_score !== null && result.thermal?.insulation_score !== undefined ? <span className="status-badge status-active">Active</span> : <span className="status-badge status-null">Not assessed</span>}</td>
                <td>{result.thermal?.insulation_score !== null && result.thermal?.insulation_score !== undefined ? `${Math.round(result.thermal.insulation_score)} / 100` : 'N/A'}</td>
              </tr>
              <tr>
                <td>Air Quality (AQI) Indicator</td>
                <td>Supplemental</td>
                <td>
                  {result.aqi?.environmental_score !== null && result.aqi?.environmental_score !== undefined ? (
                    <span className="status-badge status-active">Active</span>
                  ) : result.aqi_status === 'provider_not_configured' ? (
                    <span className="status-badge status-null">Provider not configured</span>
                  ) : result.aqi_status === 'fetch_failed' ? (
                    <span className="status-badge status-warning">Fetch Failed</span>
                  ) : result.aqi_status === 'data_unavailable' || result.aqi_status === 'station_unavailable' || result.aqi_status === 'unavailable' ? (
                    <span className="status-badge status-null">Data unavailable</span>
                  ) : (
                    <span className="status-badge status-null">Not assessed</span>
                  )}
                </td>
                <td>{result.aqi?.environmental_score !== null && result.aqi?.environmental_score !== undefined ? `${Math.round(result.aqi.environmental_score)} / 100` : 'N/A'}</td>
              </tr>
              <tr className="table-highlight">
                <td><strong>Overall Composite Score</strong></td>
                <td>
                  <strong>{score_weight_coverage ?? 0}% coverage</strong>
                  <br />
                  <small>{active_modules_count ?? 0} / 4 active modules</small>
                </td>
                <td>
                  <span className={`status-badge ${is_provisional ? 'status-null' : 'status-active'}`}>
                    {is_provisional ? 'PROVISIONAL' : 'FINAL'}
                  </span>
                </td>
                <td>
                  <strong>{overall_score !== null ? `${Math.round(overall_score)} / 100` : 'N/A'}</strong>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Footer Actions */}
        <div className="report-actions">
          <button className="btn-primary" onClick={onReset}>
            <RotateCcw size={18} />
            <span>Inspect New Property</span>
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
            <pre className="json-box">{JSON.stringify(result, null, 2)}</pre>
          </div>
        )}
      </div>
    </div>
  );
}
