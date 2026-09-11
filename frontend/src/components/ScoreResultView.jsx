import React from 'react';
import { Activity, ShieldCheck, Cpu, Database, Code2, Clock } from 'lucide-react';

export default function ScoreResultView({ result }) {
  if (!result) {
    return (
      <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 320, textAlign: 'center', color: 'var(--text-muted)' }}>
        <Activity size={48} style={{ strokeWidth: 1.5, marginBottom: 12, opacity: 0.5, color: 'var(--color-primary, #8B1E2D)' }} />
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: '#2D2D2D', marginBottom: 6 }}>No API Data Loaded</h3>
        <p style={{ fontSize: '0.9rem', maxWidth: 320 }}>Submit property address above to receive live inspection scoring response from POST http://127.0.0.1:8000/api/score</p>
      </div>
    );
  }

  const modules = [
    { key: 'location', label: 'Location Risk Module', val: result.location },
    { key: 'aqi', label: 'Air Quality (AQI) Module', val: result.aqi },
    { key: 'price', label: 'Price Benchmark Module', val: result.price },
    { key: 'cv', label: 'Computer Vision Defect Model', val: result.cv },
    { key: 'thermal', label: 'Thermal Insulation Module', val: result.thermal },
    { key: 'overall_score', label: 'Overall Composite Score', val: result.overall_score },
    { key: 'report', label: 'Inspection Report Generator', val: result.report },
  ];

  return (
    <div className="card">
      <div className="card-header">
        <ShieldCheck style={{ color: 'var(--success)' }} size={24} />
        <h2>Live API Response</h2>
      </div>

      <div style={{ marginBottom: '1.25rem' }}>
        <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 6, marginBottom: '1rem' }}>
          <Clock size={14} />
          <span>Server Timestamp: {new Date(result.timestamp).toLocaleString()}</span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
          {modules.map((m) => (
            <div
              key={m.key}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.65rem 0.85rem',
                backgroundColor: '#F7F7F5',
                borderRadius: '8px',
                border: '1px solid #E8E8E4',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Cpu size={16} style={{ color: m.val !== null ? '#2E7D32' : '#999999' }} />
                <span style={{ fontSize: '0.9rem', fontWeight: 500, color: '#2D2D2D' }}>{m.label}</span>
              </div>

              {m.val === null ? (
                <span className="status-badge status-null">Not assessed</span>
              ) : (
                <span className="status-badge status-active">Connected ({JSON.stringify(m.val)})</span>
              )}
            </div>
          ))}
        </div>
      </div>

      <div style={{ marginTop: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: '0.5rem' }}>
          <Code2 size={16} style={{ color: 'var(--color-primary, #8B1E2D)' }} />
          <span style={{ fontSize: '0.875rem', fontWeight: 600, color: '#2D2D2D' }}>Raw JSON Response</span>
        </div>
        <pre className="json-box">{JSON.stringify(result, null, 2)}</pre>
      </div>
    </div>
  );
}
