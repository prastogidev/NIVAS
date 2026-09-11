import React, { useState, useEffect } from 'react';
import { AlertCircle, RefreshCw, ArrowLeft } from 'lucide-react';

export default function ProcessingScreen({ payload, error, isError, onRetry, onBack }) {
  // Determine availability of evidence from payload
  const hasConditionEvidence = Boolean(
    payload?.image_info?.image_base64 ||
    payload?.image_info?.video_base64 ||
    payload?.image_info?.image_url
  );

  const hasThermalEvidence = Boolean(
    payload?.image_info?.thermal_base64 ||
    payload?.image_info?.thermal_url ||
    (payload?.image_info?.image_type === 'Thermal' && (payload?.image_info?.image_base64 || payload?.image_info?.image_url))
  );

  // The 4 real analysis modules in specified order
  const modules = [
    {
      id: 'condition',
      name: 'Property Condition',
      description: 'Analyze uploaded photos/video',
      isAvailable: hasConditionEvidence,
    },
    {
      id: 'thermal',
      name: 'Thermal Analysis',
      description: 'Evaluate thermal evidence when available',
      isAvailable: hasThermalEvidence,
    },
    {
      id: 'location',
      name: 'Location Intelligence',
      description: 'Assess environmental and infrastructure context',
      isAvailable: true,
    },
    {
      id: 'price',
      name: 'Price Analysis',
      description: 'Compare available pricing data',
      isAvailable: true,
    },
  ];

  // List of available module IDs
  const availableModuleIds = modules
    .filter((m) => m.isAvailable)
    .map((m) => m.id);

  // Restrained index for currently active module among available ones
  const [activeAvailableIndex, setActiveAvailableIndex] = useState(0);

  useEffect(() => {
    if (availableModuleIds.length <= 1) return;

    // Calm, restrained cadence shifting active focus without claiming fake completions
    const interval = setInterval(() => {
      setActiveAvailableIndex((prev) => (prev + 1) % availableModuleIds.length);
    }, 2800);

    return () => clearInterval(interval);
  }, [availableModuleIds.length]);

  const currentActiveId = availableModuleIds[activeAvailableIndex] || availableModuleIds[0];

  const hasError = Boolean(error || isError);

  const handleBack = () => {
    if (onBack) {
      onBack();
    } else if (typeof window !== 'undefined' && window.history) {
      window.history.back();
    }
  };

  // If backend returns an error: clean error state
  if (hasError) {
    return (
      <div className="processing-screen">
        <div className="processing-screen-header">
          <div className="processing-brand-badge">
            <span className="brand-badge-name">NIVAS</span>
            <span className="brand-badge-divider">·</span>
            <span className="brand-badge-tag">Property Intelligence</span>
          </div>
          <h1 className="processing-title">Analyzing Your Property</h1>
          <p className="processing-subtitle">NIVAS is evaluating the available property evidence.</p>
        </div>

        <div className="processing-card-wrapper">
          <div className="card processing-card processing-error-card">
            <div className="processing-error-state">
              <div className="error-icon-wrapper">
                <AlertCircle size={32} className="error-icon" />
              </div>
              <h2 className="error-title">Analysis couldn't be completed.</h2>
              <p className="error-description">
                {typeof error === 'string'
                  ? error
                  : 'The inspection engine encountered an issue connecting to services. Please check your connection and try again.'}
              </p>
              <div className="error-actions">
                {onRetry && (
                  <button type="button" className="btn-primary btn-retry" onClick={onRetry}>
                    <RefreshCw size={15} />
                    <span>Try Again</span>
                  </button>
                )}
                <button type="button" className="btn-secondary btn-back" onClick={handleBack}>
                  <ArrowLeft size={15} />
                  <span>Back to Property Details</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="processing-screen">
      {/* Top Header */}
      <div className="processing-screen-header">
        <div className="processing-brand-badge">
          <span className="brand-badge-name">NIVAS</span>
          <span className="brand-badge-divider">·</span>
          <span className="brand-badge-tag">Property Intelligence</span>
        </div>
        <h1 className="processing-title">Analyzing Your Property</h1>
        <p className="processing-subtitle">NIVAS is evaluating the available property evidence.</p>
      </div>

      {/* Centered Analysis Card */}
      <div className="processing-card-wrapper">
        <div className="card processing-card">
          <div className="module-list">
            {modules.map((mod) => {
              let state = 'waiting'; // 'waiting' | 'analyzing' | 'complete' | 'unavailable' | 'error'

              if (!mod.isAvailable) {
                state = 'unavailable';
              } else if (mod.id === currentActiveId) {
                state = 'analyzing';
              } else {
                state = 'waiting';
              }

              const isAnalyzing = state === 'analyzing';

              return (
                <div
                  key={mod.id}
                  className={`module-row ${isAnalyzing ? 'module-active' : ''} ${state === 'unavailable' ? 'module-unavailable' : ''}`}
                >
                  <div className="module-details">
                    <div className="module-name">{mod.name}</div>
                    <div className="module-desc">{mod.description}</div>
                  </div>

                  <div className="module-status-wrapper">
                    {state === 'analyzing' && (
                      <span className="module-status-badge status-analyzing">
                        <span className="status-symbol pulse-dot">●</span> Analyzing
                      </span>
                    )}
                    {state === 'waiting' && (
                      <span className="module-status-badge status-waiting">
                        <span className="status-symbol">○</span> Waiting
                      </span>
                    )}
                    {state === 'unavailable' && (
                      <span className="module-status-badge status-unavailable">
                        <span className="status-symbol">—</span> Unavailable
                      </span>
                    )}
                    {state === 'complete' && (
                      <span className="module-status-badge status-complete">
                        <span className="status-symbol">✓</span> Complete
                      </span>
                    )}
                    {state === 'error' && (
                      <span className="module-status-badge status-error">
                        <span className="status-symbol">✕</span> Error
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Bottom of Card */}
          <div className="processing-card-footer">
            <p className="processing-footer-text">
              Analysis combines the evidence available for this property.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
