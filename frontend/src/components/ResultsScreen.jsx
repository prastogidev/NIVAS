import React, { useState, useEffect, useCallback } from 'react';
import {
  ShieldCheck,
  AlertTriangle,
  MapPin,
  Tag,
  Camera,
  Flame,
  Wind,
  Code2,
  FileText,
  Building,
  Activity,
  Layers,
  Percent,
  ChevronDown,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
  Info,
  Sparkles,
  CheckCircle2,
  ShieldAlert,
  ClipboardCheck,
  Check,
  Maximize2,
  X,
  ZoomIn,
  Eye,
  Image as ImageIcon,
} from 'lucide-react';

export default function ResultsScreen({ result, onViewReport }) {
  const [showJson, setShowJson] = useState(false);
  const [activeEvidenceContext, setActiveEvidenceContext] = useState(null); // { list: [...], index: 0 }

  if (!result) return null;

  const {
    location,
    aqi,
    aqi_status,
    price,
    price_status,
    price_error,
    cv,
    thermal,
    overall_score,
    is_provisional,
    active_modules_count,
    score_weight_coverage,
    decision_insights,
    timestamp
  } = result;

  const getScoreColor = (score) => {
    if (score === null || score === undefined) return '#4A4A4A';
    if (score >= 80) return '#5A9B6F';
    if (score >= 60) return '#2E7D6B';
    return '#D64545';
  };

  const conditionScore = cv?.structural_score;
  const thermalScore = thermal?.insulation_score ?? thermal?.thermal_score;
  const locationScore = location?.risk_score;
  const priceScore = price?.fairness_score ?? price?.score;

  // Determine unavailable modules from real backend response data
  const unavailableModuleNames = [];
  if (conditionScore === null || conditionScore === undefined) unavailableModuleNames.push('visual condition');
  if (thermalScore === null || thermalScore === undefined) unavailableModuleNames.push('thermal');
  if (locationScore === null || locationScore === undefined) unavailableModuleNames.push('location');
  if (priceScore === null || priceScore === undefined) unavailableModuleNames.push('price');

  const activeCount = active_modules_count ?? (4 - unavailableModuleNames.length);
  const coveragePct = score_weight_coverage ?? (activeCount === 4 ? 100 : Math.round((activeCount / 4) * 100));

  let trustExplanation = '';
  if (unavailableModuleNames.length === 0) {
    trustExplanation = `This assessment uses all 4 of 4 available intelligence modules (${coveragePct}% assessment coverage). All core signals were successfully evaluated to produce a verified comprehensive rating.`;
  } else if (is_provisional) {
    const missingText = unavailableModuleNames.join(' and ');
    trustExplanation = `This assessment uses ${activeCount} of 4 available intelligence modules (${coveragePct}% assessment coverage). Results are provisional because ${missingText} data was unavailable. Unevaluated modules are excluded from weighting to avoid artificial score zeroing.`;
  } else {
    const missingText = unavailableModuleNames.join(' and ');
    trustExplanation = `This assessment uses ${activeCount} of 4 available intelligence modules (${coveragePct}% assessment coverage). Note that ${missingText} data was unavailable.`;
  }

  // ── Extract Key Concerns strictly from backend data ───────────────────────
  const rawRisks = decision_insights?.key_risks || [];
  // Exclude purely structural "coverage gap" items (e.g. missing thermal data) from physical concerns,
  // as explicitly required: "If thermal data is unavailable, do NOT turn that into a thermal concern;
  // simply preserve the unavailable state elsewhere."
  const filteredRisks = rawRisks.filter(
    (r) => r.category !== 'composite' && !r.title.toLowerCase().includes('coverage gap')
  );

  const keyConcerns = [...filteredRisks];

  // If decision_insights didn't flag CV defects, but CV model detected non-clean surface condition
  if (
    cv &&
    cv.predicted_class &&
    cv.predicted_class !== 'clean' &&
    !keyConcerns.some((c) => c.category === 'cv')
  ) {
    const detectedList = (cv.defects_detected || [])
      .filter((d) => d !== 'none' && !d.includes('blurry'));

    if (detectedList.length > 1) {
      detectedList.forEach((defect) => {
        keyConcerns.push({
          category: 'cv',
          severity: defect === 'mold' || defect === 'broken' ? 'high' : 'medium',
          title: `${defect.charAt(0).toUpperCase() + defect.slice(1)} Detected`,
          description: `Computer vision scan detected ${defect} surface condition on property wall imagery.`,
          evidence: { structural_score: cv.structural_score, defect },
        });
      });
    } else {
      keyConcerns.push({
        category: 'cv',
        severity: cv.predicted_class === 'mold' || cv.predicted_class === 'broken' ? 'high' : 'medium',
        title: `${cv.predicted_class.charAt(0).toUpperCase() + cv.predicted_class.slice(1)} Surface Detected`,
        description: `Computer vision scan detected ${cv.predicted_class} surface condition on property wall imagery.`,
        evidence: { structural_score: cv.structural_score },
      });
    }
  }

  // If thermal anomaly exists and not already flagged
  if (
    thermal &&
    (thermal.anomalies_detected_count > 0 || (thermal.thermal_anomaly_delta && thermal.thermal_anomaly_delta > 5)) &&
    !keyConcerns.some((c) => c.category === 'thermal')
  ) {
    keyConcerns.push({
      category: 'thermal',
      severity: 'medium',
      title: 'Localized Thermal Variance Detected',
      description: `Thermal scan registered ${thermal.anomalies_detected_count || 0} anomaly pixel(s) with local variance.`,
      evidence: { anomalies_detected_count: thermal.anomalies_detected_count },
    });
  }

  // ── Extract Strengths strictly from backend data ──────────────────────────
  const rawFactors = decision_insights?.positive_factors || [];
  const strengths = [...rawFactors];

  // If decision_insights didn't flag clean condition, but CV is cleanly verified
  if (
    cv &&
    cv.predicted_class === 'clean' &&
    cv.structural_score !== null &&
    cv.structural_score >= 80 &&
    !strengths.some((s) => s.category === 'cv')
  ) {
    strengths.push({
      category: 'cv',
      title: 'Sound Wall Surface Condition',
      description: 'Visual scan confirmed clean wall surfaces without dampness, algae, mold, or broken sections.',
      evidence: { structural_score: cv.structural_score },
    });
  }

  // ── Visual Evidence Extraction ─────────────────────────────────────────
  const visualEvidenceList = Array.isArray(cv?.visual_evidence) ? cv.visual_evidence : [];
  const issueEvidence = visualEvidenceList.filter(
    (item) => item.predicted_class && item.predicted_class.toLowerCase() !== 'clean'
  );
  const cleanEvidence = visualEvidenceList.filter(
    (item) => item.predicted_class && item.predicted_class.toLowerCase() === 'clean'
  );

  // ── Due Diligence Recommendations ─────────────────────────────────────────
  const recommendedChecks = decision_insights?.recommended_checks || [];
  const reportRecommendations = result.report?.recommendations || [];

  // ── Lightbox Navigation Handlers ─────────────────────────────────────────
  const currentEvidence =
    activeEvidenceContext && activeEvidenceContext.list
      ? activeEvidenceContext.list[activeEvidenceContext.index]
      : null;

  const totalEvidenceCount = activeEvidenceContext?.list?.length || 0;
  const currentEvidenceIndex = activeEvidenceContext?.index ?? 0;

  const handlePrevEvidence = useCallback(() => {
    setActiveEvidenceContext((prev) => {
      if (!prev || !prev.list || prev.list.length <= 1) return prev;
      const nextIndex = prev.index > 0 ? prev.index - 1 : prev.list.length - 1;
      return { ...prev, index: nextIndex };
    });
  }, []);

  const handleNextEvidence = useCallback(() => {
    setActiveEvidenceContext((prev) => {
      if (!prev || !prev.list || prev.list.length <= 1) return prev;
      const nextIndex = prev.index < prev.list.length - 1 ? prev.index + 1 : 0;
      return { ...prev, index: nextIndex };
    });
  }, []);

  const handleCloseLightbox = useCallback(() => {
    setActiveEvidenceContext(null);
  }, []);

  useEffect(() => {
    if (!activeEvidenceContext) return;

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        handleCloseLightbox();
      } else if (e.key === 'ArrowLeft') {
        handlePrevEvidence();
      } else if (e.key === 'ArrowRight') {
        handleNextEvidence();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeEvidenceContext, handleCloseLightbox, handlePrevEvidence, handleNextEvidence]);

  return (
    <div className="results-container">
      {/* ── 1. HERO SCORE & 2. SCORE CONTEXT ───────────────────────── */}
      <div className="card assessment-hero-card">
        <div className="assessment-hero-header">
          <div>
            <span className="assessment-hero-tag">NIVAS PROPERTY ASSESSMENT</span>
            <h1 className="assessment-hero-title">Property Assessment</h1>
          </div>
          {location?.locality && (
            <div className="assessment-hero-location">
              <MapPin size={14} />
              <span>{location.locality}</span>
            </div>
          )}
        </div>

        <div className="assessment-score-row">
          <div className="assessment-score-main">
            <span className="assessment-score-number">
              {overall_score !== null && overall_score !== undefined
                ? Math.round(overall_score * 10) / 10
                : 'N/A'}
            </span>
            <span className="assessment-score-denom">/ 100</span>
          </div>

          <div className="assessment-status-badge-wrapper">
            {is_provisional ? (
              <span className="assessment-badge badge-provisional">
                PROVISIONAL
              </span>
            ) : (
              <span className="assessment-badge badge-verified">
                VERIFIED COMPREHENSIVE
              </span>
            )}
          </div>
        </div>

        {/* Existing Decision / Summary from Backend */}
        {(decision_insights?.verdict || decision_insights?.overall_interpretation || result.report?.summary) && (
          <div className="assessment-hero-summary">
            {decision_insights?.verdict && (
              <strong className="hero-verdict-highlight">{decision_insights.verdict}: </strong>
            )}
            <span className="hero-verdict-desc">
              {decision_insights?.overall_interpretation || result.report?.summary}
            </span>
          </div>
        )}

        {/* Score Context */}
        <div className="assessment-context-bar">
          <span className="context-metric">
            <strong>{activeCount} of 4</strong> modules available
          </span>
          <span className="context-separator">·</span>
          <span className="context-metric">
            <strong>{coveragePct}%</strong> assessment coverage
          </span>
        </div>
      </div>

      {/* ── 3. MODULE SCORE CARDS ──────────────────────────────────── */}
      <div className="assessment-modules-grid">
        {/* CONDITION CARD */}
        <div className={`card assessment-module-card ${conditionScore === null || conditionScore === undefined ? 'card-unavailable' : ''}`}>
          <div className="module-card-top">
            <span className="module-card-label">CONDITION</span>
            <span className="module-card-status">
              {conditionScore !== null && conditionScore !== undefined ? 'Available' : 'Unavailable'}
            </span>
          </div>
          <div className="module-card-score">
            {conditionScore !== null && conditionScore !== undefined ? (
              <>
                <span className="module-score-num">{Math.round(conditionScore * 10) / 10}</span>
                <span className="module-score-denom">/ 100</span>
              </>
            ) : (
              <span className="module-unavailable-text">Unavailable</span>
            )}
          </div>
          <p className="module-card-explanation">
            {conditionScore !== null && conditionScore !== undefined
              ? (cv.defects_detected && cv.defects_detected.filter(d => d !== 'none' && !d.includes('blurry')).length > 0
                  ? `${cv.defects_detected.filter(d => d !== 'none' && !d.includes('blurry')).map(d => d.charAt(0).toUpperCase() + d.slice(1)).join(' / ')} detected`
                  : (cv.predicted_class ? `Visible condition (${cv.predicted_class})` : 'Visible surface condition'))
              : 'No visual evidence'}
          </p>
        </div>

        {/* THERMAL CARD */}
        <div className={`card assessment-module-card ${thermalScore === null || thermalScore === undefined ? 'card-unavailable' : ''}`}>
          <div className="module-card-top">
            <span className="module-card-label">THERMAL</span>
            <span className="module-card-status">
              {thermalScore !== null && thermalScore !== undefined ? 'Available' : 'Unavailable'}
            </span>
          </div>
          <div className="module-card-score">
            {thermalScore !== null && thermalScore !== undefined ? (
              <>
                <span className="module-score-num">{Math.round(thermalScore * 10) / 10}</span>
                <span className="module-score-denom">/ 100</span>
              </>
            ) : (
              <span className="module-unavailable-text">Unavailable</span>
            )}
          </div>
          <p className="module-card-explanation">
            {thermalScore !== null && thermalScore !== undefined
              ? (thermal.sensor_status || (thermal.anomalies_detected_count !== undefined ? `${thermal.anomalies_detected_count} anomalies detected` : 'Thermal insulation evaluated'))
              : 'No thermal data'}
          </p>
        </div>

        {/* LOCATION CARD */}
        <div className={`card assessment-module-card ${locationScore === null || locationScore === undefined ? (location?.fetch_status === 'fetch_failed' ? 'card-warning' : 'card-unavailable') : ''}`}>
          <div className="module-card-top">
            <span className="module-card-label">LOCATION</span>
            <span className={`module-card-status ${location?.fetch_status === 'fetch_failed' ? 'status-warning' : ''}`}>
              {locationScore !== null && locationScore !== undefined ? 'Available' : (location?.fetch_status === 'fetch_failed' ? 'Fetch Failed' : 'Unavailable')}
            </span>
          </div>
          <div className="module-card-score">
            {locationScore !== null && locationScore !== undefined ? (
              <>
                <span className="module-score-num">{Math.round(locationScore * 10) / 10}</span>
                <span className="module-score-denom">/ 100</span>
              </>
            ) : location?.fetch_status === 'fetch_failed' ? (
              <span className="module-unavailable-text" style={{ color: '#B45309' }}>API Timeout</span>
            ) : (
              <span className="module-unavailable-text">Unavailable</span>
            )}
          </div>
          <p className="module-card-explanation">
            {locationScore !== null && locationScore !== undefined
              ? (location.locality ? `Location intelligence (${location.locality})` : 'Location intelligence')
              : location?.fetch_status === 'fetch_failed'
              ? 'Address resolved, but civic infrastructure timed out'
              : 'Location data unavailable'}
          </p>
        </div>

        {/* PRICE CARD */}
        <div className={`card assessment-module-card ${priceScore === null || priceScore === undefined ? (price_status === 'fetch_failed' ? 'card-warning' : 'card-unavailable') : ''}`}>
          <div className="module-card-top">
            <span className="module-card-label">PRICE</span>
            <span className={`module-card-status ${price_status === 'fetch_failed' ? 'status-warning' : ''}`}>
              {priceScore !== null && priceScore !== undefined
                ? 'Available'
                : price_status === 'provider_not_configured'
                ? 'Provider Not Configured'
                : price_status === 'fetch_failed'
                ? 'Fetch Failed'
                : price_status === 'data_unavailable'
                ? 'Data Unavailable'
                : 'Unavailable'}
            </span>
          </div>
          <div className="module-card-score">
            {priceScore !== null && priceScore !== undefined ? (
              <>
                <span className="module-score-num">{Math.round(priceScore * 10) / 10}</span>
                <span className="module-score-denom">/ 100</span>
              </>
            ) : price_status === 'provider_not_configured' ? (
              <span className="module-unavailable-text" style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Config Missing</span>
            ) : price_status === 'fetch_failed' ? (
              <span className="module-unavailable-text" style={{ color: '#B45309' }}>API Error</span>
            ) : (
              <span className="module-unavailable-text">Unavailable</span>
            )}
          </div>
          <p className="module-card-explanation">
            {priceScore !== null && priceScore !== undefined
              ? (price.delhi_circle_category ? `Price alignment (${price.delhi_circle_category})` : 'Price alignment')
              : price_status === 'provider_not_configured'
              ? (price_error || 'Propstack API key required for live valuation outside cached demo zones')
              : price_status === 'fetch_failed'
              ? (price_error || 'Propstack valuation API connection failed')
              : price_status === 'data_unavailable'
              ? (price_error || 'No benchmark data available for this locality')
              : 'Price data unavailable'}
          </p>
        </div>
      </div>

      {/* ── 5. TRUST / TRANSPARENCY SECTION ───────────────────────── */}
      <div className="card assessment-coverage-card">
        <div className="assessment-coverage-header">
          <Info size={16} className="coverage-icon" />
          <h4>Assessment coverage</h4>
        </div>
        <p className="assessment-coverage-text">{trustExplanation}</p>
      </div>

      {/* ── Action Buttons: Executive Report & Raw JSON ────────────── */}
      <div className="assessment-hero-actions">
        <button className="btn-primary btn-report-action" onClick={onViewReport}>
          <FileText size={17} />
          <span>View Executive Report & Recommendations</span>
        </button>

        <button
          className="btn-secondary btn-json-action"
          onClick={() => setShowJson(!showJson)}
        >
          <Code2 size={16} />
          <span>{showJson ? 'Hide Raw JSON' : 'Inspect Raw JSON Response'}</span>
          {showJson ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </button>
      </div>

      {showJson && (
        <div className="json-container">
          <pre className="json-box">{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}

      {/* ── 'What We Found' / Key Findings Section ────────────────── */}
      <div className="findings-section">
        <div className="findings-header">
          <span className="findings-badge">FINDINGS SUMMARY</span>
          <h2 className="findings-title">What We Found</h2>
          <p className="findings-subtitle">
            Key observations from the available property evidence.
          </p>
        </div>

        {/* Two-Column Layout: Key Concerns & Strengths */}
        <div className="findings-grid">
          {/* 1. KEY CONCERNS */}
          <div className="card findings-column concerns-card">
            <div className="findings-col-header">
              <div className="findings-col-title-wrap">
                <ShieldAlert size={20} className="findings-icon-concern" />
                <h3 className="findings-col-title">Key Concerns</h3>
              </div>
              <span className="findings-count-badge count-concerns">
                {keyConcerns.length}
              </span>
            </div>

            <div className="findings-items-list">
              {keyConcerns.length > 0 ? (
                keyConcerns.map((concern, idx) => {
                  const isCvConcern = concern.category === 'cv';
                  // Find issue evidence matching this concern's detected defects or classes
                  const matchingEvidence = isCvConcern
                    ? issueEvidence.filter((item) => {
                        const pClass = item.predicted_class?.toLowerCase();
                        const titleLower = concern.title?.toLowerCase() || '';
                        const descLower = concern.description?.toLowerCase() || '';
                        return (
                          (pClass && (titleLower.includes(pClass) || descLower.includes(pClass))) ||
                          (cv?.predicted_class && pClass === cv.predicted_class.toLowerCase())
                        );
                      })
                    : [];

                  return (
                    <div key={idx} className="finding-item finding-concern-item">
                      <div className="finding-item-top">
                        <span className="finding-item-title">{concern.title}</span>
                        {concern.severity && (
                          <span className={`severity-tag severity-${concern.severity.toLowerCase()}`}>
                            {concern.severity}
                          </span>
                        )}
                      </div>
                      <p className="finding-item-desc">{concern.description}</p>
                      {concern.category && (
                        <span className="finding-item-category">
                          Source: {concern.category.toUpperCase()}
                        </span>
                      )}

                      {/* Visual Evidence Previews for CV Concerns */}
                      {isCvConcern && (
                        <div className="evidence-preview-section">
                          <div className="evidence-preview-header">
                            <Camera size={14} className="evidence-preview-header-icon" />
                            <span className="evidence-preview-label">Visual Evidence</span>
                          </div>

                          {matchingEvidence.length > 0 ? (
                            <div className="evidence-gallery">
                              {matchingEvidence.map((ev, evIdx) => {
                                const imgSrc = ev.image_base64 || ev.image_url;
                                if (!imgSrc) return null;
                                return (
                                  <button
                                    type="button"
                                    key={evIdx}
                                    className="evidence-thumbnail-card"
                                    onClick={() => setActiveEvidenceContext({ list: matchingEvidence, index: evIdx })}
                                    aria-label={`View full inspection evidence for ${ev.predicted_class} (${ev.file_name || 'image'})`}
                                  >
                                    <div className="evidence-img-wrap">
                                      <img
                                        src={imgSrc}
                                        alt={ev.file_name ? `Inspection image ${ev.file_name} showing ${ev.predicted_class}` : `Inspection evidence showing ${ev.predicted_class}`}
                                        className="evidence-thumbnail"
                                      />
                                      <div className="evidence-img-overlay">
                                        <ZoomIn size={16} className="evidence-zoom-icon" />
                                      </div>
                                    </div>
                                    <div className="evidence-meta">
                                      <span className="evidence-class-tag tag-defect">
                                        {ev.predicted_class.charAt(0).toUpperCase() + ev.predicted_class.slice(1)}
                                      </span>
                                      {ev.confidence !== null && ev.confidence !== undefined && (
                                        <span className="evidence-conf-tag">
                                          Model confidence · {Math.round(ev.confidence * 100)}%
                                        </span>
                                      )}
                                      {ev.file_name && (
                                        <span className="evidence-file-name" title={ev.file_name}>
                                          {ev.file_name}
                                        </span>
                                      )}
                                    </div>
                                  </button>
                                );
                              })}
                            </div>
                          ) : (
                            <p className="evidence-empty-note">
                              No issue-specific visual evidence available.
                            </p>
                          )}

                          {/* Video Frame Limitation Note */}
                          {cv?.is_video && !matchingEvidence.length && (
                            <p className="evidence-limitation-note">
                              Frame-to-issue temporal association is not saved during video analysis.
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })
              ) : (
                <div className="finding-empty-state">
                  <p className="finding-empty-text">
                    No significant concerns identified in the available evidence.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* 2. STRENGTHS */}
          <div className="card findings-column strengths-card">
            <div className="findings-col-header">
              <div className="findings-col-title-wrap">
                <CheckCircle2 size={20} className="findings-icon-strength" />
                <h3 className="findings-col-title">Strengths</h3>
              </div>
              <span className="findings-count-badge count-strengths">
                {strengths.length}
              </span>
            </div>

            <div className="findings-items-list">
              {strengths.length > 0 ? (
                strengths.map((strength, idx) => {
                  const isCvStrength = strength.category === 'cv';
                  return (
                    <div key={idx} className="finding-item finding-strength-item">
                      <div className="finding-item-top">
                        <span className="finding-item-title">{strength.title}</span>
                        <Check size={14} className="finding-strength-check" />
                      </div>
                      <p className="finding-item-desc">{strength.description}</p>
                      {strength.category && (
                        <span className="finding-item-category">
                          Signal: {strength.category.toUpperCase()}
                        </span>
                      )}

                      {/* Supporting Visual Evidence for Clean Verified Surface */}
                      {isCvStrength && cleanEvidence.length > 0 && (
                        <div className="evidence-preview-section">
                          <div className="evidence-preview-header">
                            <Camera size={14} style={{ color: 'var(--success)' }} />
                            <span className="evidence-preview-label" style={{ color: 'var(--success)' }}>
                              Supporting Visual Evidence
                            </span>
                          </div>
                          <div className="evidence-gallery">
                            {cleanEvidence.map((ev, evIdx) => {
                              const imgSrc = ev.image_base64 || ev.image_url;
                              if (!imgSrc) return null;
                              return (
                                <button
                                  type="button"
                                  key={evIdx}
                                  className="evidence-thumbnail-card card-clean"
                                  onClick={() => setActiveEvidenceContext({ list: cleanEvidence, index: evIdx })}
                                  aria-label={`View full inspection evidence for clean wall (${ev.file_name || 'image'})`}
                                >
                                  <div className="evidence-img-wrap">
                                    <img
                                      src={imgSrc}
                                      alt={ev.file_name ? `Clean wall inspection image ${ev.file_name}` : 'Clean wall inspection evidence'}
                                      className="evidence-thumbnail"
                                    />
                                    <div className="evidence-img-overlay">
                                      <ZoomIn size={16} className="evidence-zoom-icon" />
                                    </div>
                                  </div>
                                  <div className="evidence-meta">
                                    <span className="evidence-class-tag tag-clean">
                                      Clean Wall
                                    </span>
                                    {ev.confidence !== null && ev.confidence !== undefined && (
                                      <span className="evidence-conf-tag">
                                        Model confidence · {Math.round(ev.confidence * 100)}%
                                      </span>
                                    )}
                                    {ev.file_name && (
                                      <span className="evidence-file-name" title={ev.file_name}>
                                        {ev.file_name}
                                      </span>
                                    )}
                                  </div>
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })
              ) : (
                <div className="finding-empty-state">
                  <p className="finding-empty-text">
                    Additional evidence is needed to establish strengths in this area.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 3. BEFORE YOU DECIDE: DUE-DILIGENCE CHECKLIST */}
        {(recommendedChecks.length > 0 || reportRecommendations.length > 0) && (
          <div className="card due-diligence-card">
            <div className="due-diligence-header">
              <div className="due-diligence-title-wrap">
                <ClipboardCheck size={20} style={{ color: 'var(--ink-deep)' }} />
                <div>
                  <h3 className="due-diligence-title">Before You Decide</h3>
                  <p className="due-diligence-subtitle">
                    Recommended due-diligence actions based on identified risks and missing signals.
                  </p>
                </div>
              </div>
            </div>

            <div className="due-diligence-list">
              {recommendedChecks.length > 0
                ? recommendedChecks.map((check, idx) => (
                    <div key={idx} className="due-diligence-item">
                      <div className="due-diligence-item-header">
                        {check.priority && (
                          <span className={`priority-tag priority-${check.priority.toLowerCase()}`}>
                            {check.priority} Priority
                          </span>
                        )}
                        {check.category && (
                          <span className="due-diligence-category">
                            {check.category}
                          </span>
                        )}
                      </div>
                      <p className="due-diligence-action">{check.action}</p>
                      {check.rationale && (
                        <p className="due-diligence-rationale">{check.rationale}</p>
                      )}
                    </div>
                  ))
                : reportRecommendations.map((rec, idx) => (
                    <div key={idx} className="due-diligence-item">
                      <p className="due-diligence-action">{rec}</p>
                    </div>
                  ))}
            </div>
          </div>
        )}
      </div>

      {/* Grid of Module Breakdown Cards */}
      <h3 className="section-title">Individual Module Breakdown</h3>
      <div className="modules-grid">

        {/* 1. Location Risk Module (25% Weight) */}
        <div className={`card module-card ${!location || location.risk_score === null ? 'module-disabled' : ''}`}>
          <div className="module-card-header">
            <div className="module-title">
              <MapPin size={22} style={{ color: 'var(--ink-deep)' }} />
              <div>
                <h4>Location & Infrastructure</h4>
                <span className="module-weight">Weight: 25%</span>
              </div>
            </div>
            {location && location.risk_score !== null ? (
              <div className="module-score-badge" style={{ backgroundColor: `${getScoreColor(location.risk_score)}18`, color: getScoreColor(location.risk_score) }}>
                {Math.round(location.risk_score)} / 100
              </div>
            ) : location?.fetch_status === 'fetch_failed' ? (
              <div className="fetch-error-badge-wrap">
                <span className="status-badge status-warning">Fetch Failed</span>
                <span className="fetch-error-subtext">API Timeout</span>
              </div>
            ) : (
              <span className="status-badge status-null">Not assessed</span>
            )}
          </div>

          <div className="module-card-body">
            {location && location.risk_score !== null ? (
              <>
                <div className="info-row">
                  <span className="info-lbl">Locality:</span>
                  <span className="info-val">{location.locality || 'Unknown'}</span>
                </div>
                <div className="info-row">
                  <span className="info-lbl">Coordinates:</span>
                  <span className="info-val">
                    {location.latitude?.toFixed(4)}, {location.longitude?.toFixed(4)}
                  </span>
                </div>
                {location.infrastructure && (
                  <>
                    <div className="infra-grid">
                      {location.infrastructure.schools_count > 0 && <div className="infra-tag">🏫 Schools: {location.infrastructure.schools_count}</div>}
                      {location.infrastructure.hospitals_count > 0 && <div className="infra-tag">🏥 Hospitals: {location.infrastructure.hospitals_count}</div>}
                      {location.infrastructure.clinics_count > 0 && <div className="infra-tag">🩺 Clinics: {location.infrastructure.clinics_count}</div>}
                      {location.infrastructure.pharmacies_count > 0 && <div className="infra-tag">💊 Pharmacies: {location.infrastructure.pharmacies_count}</div>}
                      {location.infrastructure.police_stations_count > 0 && <div className="infra-tag">🚔 Police: {location.infrastructure.police_stations_count}</div>}
                      {location.infrastructure.fire_stations_count > 0 && <div className="infra-tag">🚒 Fire: {location.infrastructure.fire_stations_count}</div>}
                      {location.infrastructure.public_transport_count > 0 && <div className="infra-tag">🚌 Transport: {location.infrastructure.public_transport_count}</div>}
                      {location.infrastructure.railway_stations_count > 0 && <div className="infra-tag">🚉 Metro/Rail: {location.infrastructure.railway_stations_count}</div>}
                      {location.infrastructure.major_roads_count > 0 && <div className="infra-tag">🛣️ Roads: {location.infrastructure.major_roads_count}</div>}
                    </div>
                    {location.infrastructure.nearby_places && location.infrastructure.nearby_places.length > 0 && (
                      <div className="info-row" style={{ marginTop: '0.5rem' }}>
                        <span className="info-lbl">Landmarks:</span>
                        <span className="info-val" style={{ fontSize: '0.8rem', color: '#2D2D2D' }}>
                          {location.infrastructure.nearby_places.slice(0, 3).join(', ')}
                        </span>
                      </div>
                    )}
                  </>
                )}
              </>
            ) : location?.fetch_status === 'fetch_failed' ? (
              <div className="fetch-error-alert-banner" style={{ marginTop: '0.25rem' }}>
                ⚠️ <strong>Live Infrastructure Unavailable:</strong> Address was resolved to {location.locality || 'coordinates'}{location.latitude ? ` (${location.latitude.toFixed(4)}, ${location.longitude.toFixed(4)})` : ''}, but live civic amenities could not be retrieved from OpenStreetMap mirrors (request timed out).
              </div>
            ) : (
              <p className="disconnected-msg">Location risk module data unavailable or geocoding unfulfilled.</p>
            )}
          </div>
        </div>

        {/* 2. Price Benchmark Module (25% Weight) */}
        <div className={`card module-card ${!price || price.fairness_score === null ? 'module-disabled' : ''}`}>
          <div className="module-card-header">
            <div className="module-title">
              <Tag size={22} style={{ color: 'var(--ink-deep)' }} />
              <div>
                <h4>Price Valuation Benchmark</h4>
                <span className="module-weight">Weight: 25%</span>
              </div>
            </div>
            {price && price.fairness_score !== null ? (
              <div className="module-score-badge" style={{ backgroundColor: `${getScoreColor(price.fairness_score)}18`, color: getScoreColor(price.fairness_score) }}>
                {Math.round(price.fairness_score)} / 100
              </div>
            ) : price_status === 'provider_not_configured' ? (
              <span className="status-badge status-null">Provider not configured</span>
            ) : price_status === 'fetch_failed' ? (
              <span className="status-badge status-warning">Fetch Failed</span>
            ) : price_status === 'data_unavailable' ? (
              <span className="status-badge status-null">Data unavailable</span>
            ) : (
              <span className="status-badge status-null">Not assessed</span>
            )}
          </div>

          <div className="module-card-body">
            {price && price.fairness_score !== null ? (
              <>
                <div className="info-row">
                  <span className="info-lbl">Est. Price / sqft:</span>
                  <span className="info-val">
                    ₹{price.estimated_price_per_sqft?.toLocaleString() || 'N/A'}
                  </span>
                </div>
                {price.delhi_circle_category && (
                  <div className="info-row">
                    <span className="info-lbl">Circle Rate Category:</span>
                    <span className="info-val">{price.delhi_circle_category}</span>
                  </div>
                )}
                <div className="info-row">
                  <span className="info-lbl">Data Source:</span>
                  <span className="info-val" style={{ fontSize: '0.8rem', maxWidth: '60%', textAlign: 'right' }}>
                    {price.source || 'Property Cache'}
                  </span>
                </div>
                <div className="info-row">
                  <span className="info-lbl">Listings Sampled:</span>
                  <span className="info-val">{price.sample_count ?? price.actual_listings?.length ?? 0} benchmark records</span>
                </div>
                {price.actual_listings && price.actual_listings.length > 0 && (
                  <div style={{ marginTop: '0.6rem', borderTop: '1px solid #E8E8E4', paddingTop: '0.4rem' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.3rem', fontWeight: 600 }}>Sample Benchmark Listings:</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                      {price.actual_listings.slice(0, 2).map((item, i) => (
                        <div key={i} style={{ fontSize: '0.78rem', color: '#2D2D2D', display: 'flex', justifyContent: 'space-between' }}>
                          <span>{item.address} ({item.property_type})</span>
                          <strong>₹{item.price_per_sqft?.toLocaleString()}/sqft</strong>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <p className="disconnected-msg">
                {price_status === 'provider_not_configured'
                  ? (price_error || 'Live property valuation requires PROPSTACK_API_KEY in backend environment. Local circle rate benchmarks are active for Dwarka, Rohini, and Lajpat Nagar.')
                  : price_status === 'fetch_failed'
                  ? (price_error || 'Propstack valuation API connection failed or timed out.')
                  : price_status === 'data_unavailable'
                  ? (price_error || 'No price listings or benchmark data available for this locality.')
                  : 'Price valuation module not assessed.'}
              </p>
            )}
          </div>
        </div>

        {/* 3. Computer Vision Defect Model (30% Weight) */}
        <div className={`card module-card ${!cv || cv.structural_score === null ? 'module-disabled' : ''}`}>
          <div className="module-card-header">
            <div className="module-title">
              <Camera size={22} style={{ color: 'var(--ink-deep)' }} />
              <div>
                <h4>Computer Vision Defect Scan</h4>
                <span className="module-weight">Weight: 30%</span>
              </div>
            </div>
            {cv && cv.structural_score !== null ? (
              <div className="module-score-badge" style={{ backgroundColor: `${getScoreColor(cv.structural_score)}18`, color: getScoreColor(cv.structural_score) }}>
                {Math.round(cv.structural_score)} / 100
              </div>
            ) : (
              <span className="status-badge status-null">Not assessed</span>
            )}
          </div>

          <div className="module-card-body">
            {cv && cv.structural_score !== null ? (
              <>
                <div className="info-row">
                  <span className="info-lbl">Predicted Class:</span>
                  <span className="info-val" style={{ textTransform: 'capitalize', fontWeight: 600, color: cv.predicted_class === 'clean' ? '#2E7D32' : '#B45309' }}>
                    {cv.predicted_class || 'Clean'}
                  </span>
                </div>
                <div className="info-row">
                  <span className="info-lbl">Model Confidence:</span>
                  <span className="info-val">
                    {cv.confidence !== undefined && cv.confidence !== null ? `${(cv.confidence * 100).toFixed(1)}%` : 'N/A'}
                  </span>
                </div>
                {cv.defects_detected && cv.defects_detected.length > 0 && (
                  <div className="info-row">
                    <span className="info-lbl">Defects Flagged:</span>
                    <span className="info-val" style={{ color: 'var(--danger)' }}>{cv.defects_detected.join(', ')}</span>
                  </div>
                )}
                {cv.defect_coverage_ratio !== undefined && cv.defect_coverage_ratio !== null && (
                  <div className="info-row">
                    <span className="info-lbl">Defect Coverage:</span>
                    <span className="info-val">{(cv.defect_coverage_ratio * 100).toFixed(1)}% of surface</span>
                  </div>
                )}
                {cv.is_blurry && (
                  <div className="warning-chip">
                    <AlertTriangle size={14} /> Image blurriness threshold exceeded; score adjusted safely.
                  </div>
                )}
              </>
            ) : (
              <p className="disconnected-msg">No property wall image provided or CV model unfulfilled.</p>
            )}
          </div>
        </div>

        {/* 4. Thermal Insulation Module (20% Weight) */}
        <div className={`card module-card ${!thermal || thermal.insulation_score === null ? 'module-disabled' : ''}`}>
          <div className="module-card-header">
            <div className="module-title">
              <Flame size={22} style={{ color: 'var(--ink-deep)' }} />
              <div>
                <h4>Thermal Insulation & Sensor</h4>
                <span className="module-weight">Weight: 20%</span>
              </div>
            </div>
            {thermal && thermal.insulation_score !== null ? (
              <div className="module-score-badge" style={{ backgroundColor: `${getScoreColor(thermal.insulation_score)}18`, color: getScoreColor(thermal.insulation_score) }}>
                {Math.round(thermal.insulation_score)} / 100
              </div>
            ) : (
              <span className="status-badge status-null">Not assessed</span>
            )}
          </div>

          <div className="module-card-body">
            {thermal && thermal.insulation_score !== null ? (
              <>
                <div className="info-row">
                  <span className="info-lbl">Mean Temperature:</span>
                  <span className="info-val">{thermal.mean_temp?.toFixed(1)} °C</span>
                </div>
                <div className="info-row">
                  <span className="info-lbl">Temp Range (Min / Max):</span>
                  <span className="info-val">{thermal.min_temp?.toFixed(1)} °C - {thermal.max_temp?.toFixed(1)} °C</span>
                </div>
                {thermal.thermal_anomaly_delta !== undefined && thermal.thermal_anomaly_delta !== null && (
                  <div className="info-row">
                    <span className="info-lbl">Global Delta (Max-Min):</span>
                    <span className="info-val">{thermal.thermal_anomaly_delta?.toFixed(1)} °C</span>
                  </div>
                )}
                {thermal.max_local_variation_delta !== undefined && thermal.max_local_variation_delta !== null && (
                  <div className="info-row">
                    <span className="info-lbl">Max Local Median Variation:</span>
                    <span className="info-val">{thermal.max_local_variation_delta?.toFixed(1)} °C</span>
                  </div>
                )}
                <div className="info-row">
                  <span className="info-lbl">Thermal Anomalies:</span>
                  <span className="info-val">{thermal.anomalies_detected_count ?? 0} anomalous pixels</span>
                </div>
                {thermal.sensor_status && (
                  <div className="info-row">
                    <span className="info-lbl">Hardware Status:</span>
                    <span className="info-val" style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{thermal.sensor_status}</span>
                  </div>
                )}
              </>
            ) : (
              <p className="disconnected-msg">MLX90640 hardware sensor disconnected or thermal scan unfulfilled.</p>
            )}
          </div>
        </div>

        {/* 5. Air Quality (AQI) Module (Supplemental) */}
        <div className={`card module-card ${!aqi || aqi.environmental_score === null ? 'module-disabled' : ''}`}>
          <div className="module-card-header">
            <div className="module-title">
              <Wind size={22} style={{ color: 'var(--ink-deep)' }} />
              <div>
                <h4>Air Quality (AQI) Indicator</h4>
                <span className="module-weight">Supplemental</span>
              </div>
            </div>
            {aqi && aqi.environmental_score !== null ? (
              <div className="module-score-badge" style={{ backgroundColor: `${getScoreColor(aqi.environmental_score)}18`, color: getScoreColor(aqi.environmental_score) }}>
                {Math.round(aqi.environmental_score)} / 100
              </div>
            ) : aqi_status === 'provider_not_configured' ? (
              <span className="status-badge status-null">Provider not configured</span>
            ) : aqi_status === 'fetch_failed' ? (
              <span className="status-badge status-warning">Fetch Failed</span>
            ) : aqi_status === 'station_unavailable' || aqi_status === 'unavailable' ? (
              <span className="status-badge status-null">Station unavailable</span>
            ) : (
              <span className="status-badge status-null">Not assessed</span>
            )}
          </div>

          <div className="module-card-body">
            {aqi && aqi.environmental_score !== null ? (
              <>
                <div className="info-row">
                  <span className="info-lbl">AQI Index:</span>
                  <span className="info-val">
                    {aqi.aqi_value} ({aqi.category || 'Standard'})
                    {aqi.scale && <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginLeft: 6 }}>[{aqi.scale}]</span>}
                  </span>
                </div>
                <div className="info-row">
                  <span className="info-lbl">Source:</span>
                  <span className="info-val" style={{ fontSize: '0.8rem', maxWidth: '65%', textAlign: 'right' }}>
                    {aqi.source || aqi.station_name || 'Air Quality Provider'}
                  </span>
                </div>
                {aqi.components && Object.keys(aqi.components).length > 0 && (
                  <div style={{ marginTop: '0.6rem', borderTop: '1px solid #E8E8E4', paddingTop: '0.4rem' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.3rem', fontWeight: 600 }}>
                      Pollutant Concentrations (µg/m³):
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(90px, 1fr))', gap: '0.4rem' }}>
                      {aqi.components.pm2_5 !== undefined && (
                        <div style={{ background: 'var(--bg-subtle)', padding: '0.25rem 0.4rem', borderRadius: '4px', fontSize: '0.75rem' }}>
                          <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.7rem' }}>PM2.5</span>
                          <strong>{aqi.components.pm2_5.toFixed(1)}</strong>
                        </div>
                      )}
                      {aqi.components.pm10 !== undefined && (
                        <div style={{ background: 'var(--bg-subtle)', padding: '0.25rem 0.4rem', borderRadius: '4px', fontSize: '0.75rem' }}>
                          <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.7rem' }}>PM10</span>
                          <strong>{aqi.components.pm10.toFixed(1)}</strong>
                        </div>
                      )}
                      {aqi.components.no2 !== undefined && (
                        <div style={{ background: 'var(--bg-subtle)', padding: '0.25rem 0.4rem', borderRadius: '4px', fontSize: '0.75rem' }}>
                          <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.7rem' }}>NO2</span>
                          <strong>{aqi.components.no2.toFixed(1)}</strong>
                        </div>
                      )}
                      {aqi.components.o3 !== undefined && (
                        <div style={{ background: 'var(--bg-subtle)', padding: '0.25rem 0.4rem', borderRadius: '4px', fontSize: '0.75rem' }}>
                          <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.7rem' }}>O3</span>
                          <strong>{aqi.components.o3.toFixed(1)}</strong>
                        </div>
                      )}
                      {aqi.components.so2 !== undefined && (
                        <div style={{ background: 'var(--bg-subtle)', padding: '0.25rem 0.4rem', borderRadius: '4px', fontSize: '0.75rem' }}>
                          <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.7rem' }}>SO2</span>
                          <strong>{aqi.components.so2.toFixed(1)}</strong>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <p className="disconnected-msg">
                {aqi_status === 'provider_not_configured'
                  ? 'Air quality provider not configured: OPENWEATHER_API_KEY / AQICN_TOKEN missing from backend environment.'
                  : aqi_status === 'fetch_failed'
                  ? 'Air quality data fetch failed: Unable to retrieve air pollution readings from provider.'
                  : aqi_status === 'data_unavailable' || aqi_status === 'station_unavailable' || aqi_status === 'unavailable'
                  ? 'Air pollution data unavailable for this location.'
                  : 'Property address coordinates could not be resolved for air quality assessment.'}
              </p>
            )}
          </div>
        </div>

      </div>

      {/* ── Visual Evidence Lightbox Modal (Step 7 Enhanced) ──────────────────────── */}
      {currentEvidence && (
        <div
          className="evidence-lightbox-overlay"
          onClick={handleCloseLightbox}
          role="dialog"
          aria-modal="true"
          aria-label="Visual Evidence Inspector"
        >
          <div
            className="evidence-lightbox-modal"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header: “Visual Evidence” + Pagination + Close button */}
            <div className="lightbox-header">
              <div className="lightbox-title-wrap">
                <Camera size={18} style={{ color: 'var(--ink-deep)' }} />
                <h3 className="lightbox-title">Visual Evidence</h3>
                {totalEvidenceCount > 1 && (
                  <span className="lightbox-counter">
                    {currentEvidenceIndex + 1} of {totalEvidenceCount} evidence images
                  </span>
                )}
              </div>
              <button
                type="button"
                className="lightbox-close-btn"
                onClick={handleCloseLightbox}
                aria-label="Close visual evidence dialog"
              >
                <X size={20} />
              </button>
            </div>

            {/* Main Stage: Left/Right Arrow Controls + Large Image */}
            <div className="lightbox-stage">
              {totalEvidenceCount > 1 && (
                <button
                  type="button"
                  className="lightbox-nav-btn nav-prev"
                  onClick={handlePrevEvidence}
                  aria-label="Previous evidence image"
                  title="Previous image (Left arrow)"
                >
                  <ChevronLeft size={24} />
                </button>
              )}

              <div className="lightbox-image-container">
                <img
                  src={currentEvidence.image_base64 || currentEvidence.image_url}
                  alt={
                    currentEvidence.file_name
                      ? `Inspection evidence ${currentEvidence.file_name} showing ${currentEvidence.predicted_class}`
                      : `Inspection evidence showing ${currentEvidence.predicted_class}`
                  }
                  className="lightbox-img"
                />
              </div>

              {totalEvidenceCount > 1 && (
                <button
                  type="button"
                  className="lightbox-nav-btn nav-next"
                  onClick={handleNextEvidence}
                  aria-label="Next evidence image"
                  title="Next image (Right arrow)"
                >
                  <ChevronRight size={24} />
                </button>
              )}
            </div>

            {/* Detail Panel: Classification, Confidence, Source Transparency, Filename, Concise Explanation */}
            <div className="lightbox-details-panel">
              <div className="lightbox-meta-row">
                {/* Defect / Condition Class Tag */}
                <div className="lightbox-class-block">
                  <span
                    className={`evidence-class-tag lightbox-class-pill ${
                      currentEvidence.predicted_class?.toLowerCase() === 'clean'
                        ? 'tag-clean'
                        : 'tag-defect'
                    }`}
                  >
                    {currentEvidence.predicted_class?.toUpperCase() || 'UNSPECIFIED'}
                  </span>

                  {/* Confidence strictly formatted */}
                  {currentEvidence.confidence !== null && currentEvidence.confidence !== undefined && (
                    <span className="lightbox-confidence-text">
                      Model confidence · {Math.round(currentEvidence.confidence * 100)}%
                    </span>
                  )}
                </div>

                {/* Source Transparency: Clearly AI Visual Classification */}
                <div className="lightbox-transparency-pill">
                  <span className="transparency-dot"></span>
                  <span>AI visual classification</span>
                </div>
              </div>

              {/* Source Filename */}
              <div className="lightbox-source-row">
                <span className="source-label">Source:</span>
                <span className="source-filename">
                  {currentEvidence.file_name || 'Uploaded property inspection image'}
                </span>
              </div>

              {/* Concise Explanation based strictly on backend results */}
              <div className="lightbox-explanation-box">
                <p className="lightbox-explanation-text">
                  {currentEvidence.predicted_class?.toLowerCase() === 'clean'
                    ? 'Visual condition classified as clean.'
                    : `Visual condition classified as ${currentEvidence.predicted_class?.toLowerCase()}.`}
                </p>
                {currentEvidence.is_video_frame && (
                  <p className="lightbox-video-limitation">
                    Note: Frame sampled from uploaded property video. Frame-to-issue temporal association is not saved during video analysis.
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
