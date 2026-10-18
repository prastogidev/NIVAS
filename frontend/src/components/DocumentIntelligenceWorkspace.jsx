import React, { useState, useRef } from 'react';
import {
  FileText,
  Upload,
  AlertTriangle,
  CheckCircle2,
  AlertCircle,
  FileCode,
  Shield,
  Layers,
  Sparkles,
  Download,
  Trash2,
  ExternalLink,
  ChevronRight,
  HelpCircle,
  Eye,
  X,
  FileCheck2,
  RefreshCw,
  Info,
} from 'lucide-react';
import { analyzeDocuments, fetchSampleDocuments } from '../services/api';

export default function DocumentIntelligenceWorkspace() {
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [activeDocIndex, setActiveDocIndex] = useState(0);
  const [error, setError] = useState(null);
  const [loadingSamples, setLoadingSamples] = useState(false);
  const [evidenceModal, setEvidenceModal] = useState(null); // { title, snippet, page, docName }
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;

    // Validate size (10MB)
    const valid = [];
    const oversized = [];
    files.forEach((f) => {
      if (f.size > 10 * 1024 * 1024) {
        oversized.push(f.name);
      } else {
        valid.push(f);
      }
    });

    if (oversized.length > 0) {
      setError(`Files exceeding 10MB limit were skipped: ${oversized.join(', ')}`);
    } else {
      setError(null);
    }

    setSelectedFiles((prev) => [...prev, ...valid]);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleRemoveFile = (index) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleClearAll = () => {
    setSelectedFiles([]);
    setAnalysisResult(null);
    setError(null);
    setActiveDocIndex(0);
  };

  const handleAnalyze = async () => {
    if (!selectedFiles.length) {
      setError('Please select or drag at least one PDF or TXT document to analyze.');
      return;
    }

    setAnalyzing(true);
    setError(null);
    try {
      const data = await analyzeDocuments(selectedFiles);
      setAnalysisResult(data);
      setActiveDocIndex(0);
    } catch (err) {
      console.error('Document analysis error:', err);
      let msg = 'Failed to analyze documents. Please check file format and try again.';
      if (err.response?.data?.detail) {
        msg = typeof err.response.data.detail === 'string'
          ? err.response.data.detail
          : JSON.stringify(err.response.data.detail);
      } else if (err.message) {
        msg = err.message;
      }
      setError(msg);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleLoadSamples = async () => {
    setLoadingSamples(true);
    setError(null);
    try {
      const res = await fetchSampleDocuments();
      if (res.samples && res.samples.length >= 2) {
        // Create synthetic File objects from sample content
        const file1 = new File([res.samples[0].content], res.samples[0].filename, { type: 'text/plain' });
        const file2 = new File([res.samples[1].content], res.samples[1].filename, { type: 'text/plain' });
        setSelectedFiles([file1, file2]);
      }
    } catch (err) {
      console.error('Failed to load sample documents:', err);
      setError('Could not load sample documents from backend.');
    } finally {
      setLoadingSamples(false);
    }
  };

  const handleExportJSON = () => {
    if (!analysisResult) return;
    const blob = new Blob([JSON.stringify(analysisResult, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `nivas-document-intelligence-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const activeDoc = analysisResult?.documents?.[activeDocIndex];

  return (
    <div className="doc-intel-container" style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px 16px' }}>
      {/* Header Banner */}
      <div className="doc-intel-header" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
          <div style={{
            background: 'linear-gradient(135deg, var(--forest-deep, #1b4332), var(--forest-mid, #2d6a4f))',
            color: '#fff',
            padding: '10px',
            borderRadius: '10px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <FileText size={24} />
          </div>
          <div>
            <h1 style={{ fontSize: '1.65rem', fontWeight: 700, margin: 0, color: 'var(--ink-deep, #1a1a1a)' }}>
              Document Intelligence & Legal Extraction
            </h1>
            <p style={{ margin: '4px 0 0 0', color: 'var(--ink-muted, #555)', fontSize: '0.92rem' }}>
              Automated extraction of real estate deed terms, parties, property schedules, and cross-instrument discrepancy verification.
            </p>
          </div>
        </div>

        {/* Status Pills */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginTop: '12px' }}>
          <div style={{
            background: 'rgba(234, 179, 8, 0.1)',
            border: '1px solid rgba(234, 179, 8, 0.3)',
            borderRadius: '6px',
            padding: '6px 12px',
            fontSize: '0.8rem',
            color: '#854d0e',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}>
            <Shield size={14} />
            <span><strong>Decision Support Only:</strong> Not a legal title opinion or registrar check.</span>
          </div>

          <div style={{
            background: 'rgba(59, 130, 246, 0.1)',
            border: '1px solid rgba(59, 130, 246, 0.25)',
            borderRadius: '6px',
            padding: '6px 12px',
            fontSize: '0.8rem',
            color: '#1e40af',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}>
            <Info size={14} />
            <span><strong>Sub-Registrar DB:</strong> Live API Unavailable (Requires Advocate Search).</span>
          </div>
        </div>
      </div>

      {/* Upload & Staging Card */}
      {!analysisResult && (
        <div style={{
          background: '#fff',
          border: '1px solid var(--border-color, #e5e7eb)',
          borderRadius: '12px',
          padding: '28px',
          marginBottom: '24px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
        }}>
          <div style={{
            border: '2px dashed #cbd5e1',
            borderRadius: '10px',
            padding: '36px 20px',
            textAlign: 'center',
            background: '#f8fafc',
            cursor: 'pointer',
          }}
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const files = Array.from(e.dataTransfer.files || []);
            if (files.length) {
              const valid = files.filter(f => f.size <= 10 * 1024 * 1024);
              setSelectedFiles(prev => [...prev, ...valid]);
            }
          }}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              multiple
              accept=".pdf,.txt,.text"
              style={{ display: 'none' }}
            />
            <Upload size={38} style={{ color: 'var(--forest-mid, #2d6a4f)', margin: '0 auto 12px auto' }} />
            <h3 style={{ fontSize: '1.15rem', fontWeight: 600, margin: '0 0 6px 0' }}>
              Drag and drop property instruments here
            </h3>
            <p style={{ color: '#64748b', fontSize: '0.88rem', margin: '0 0 16px 0' }}>
              Supported formats: <strong>PDF (Text-based)</strong> and <strong>TXT</strong> up to 10MB each (max 50 pages).
            </p>
            <button
              type="button"
              className="btn-primary"
              style={{ padding: '8px 20px', fontSize: '0.9rem' }}
              onClick={(e) => {
                e.stopPropagation();
                fileInputRef.current?.click();
              }}
            >
              Browse Files
            </button>
          </div>

          {/* Sample Bundles helper */}
          <div style={{
            marginTop: '20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '12px',
            padding: '12px 16px',
            background: '#f1f5f9',
            borderRadius: '8px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.86rem', color: '#334155' }}>
              <Sparkles size={16} style={{ color: '#0284c7' }} />
              <span>Want to test immediately without uploading confidential documents?</span>
            </div>
            <button
              type="button"
              onClick={handleLoadSamples}
              disabled={loadingSamples}
              style={{
                background: '#fff',
                border: '1px solid #cbd5e1',
                padding: '6px 14px',
                borderRadius: '6px',
                fontSize: '0.85rem',
                fontWeight: 500,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              {loadingSamples ? <RefreshCw size={14} className="spin" /> : <FileCode size={14} />}
              Load Pre-Baked Delhi Sample Bundle
            </button>
          </div>

          {/* Staged Files List */}
          {selectedFiles.length > 0 && (
            <div style={{ marginTop: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600 }}>
                  Selected Documents ({selectedFiles.length})
                </h4>
                <button
                  type="button"
                  onClick={handleClearAll}
                  style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '0.82rem' }}
                >
                  Clear Selection
                </button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {selectedFiles.map((file, idx) => (
                  <div
                    key={`${file.name}-${idx}`}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '10px 14px',
                      background: '#f8fafc',
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <FileText size={18} style={{ color: '#64748b' }} />
                      <div>
                        <span style={{ fontSize: '0.88rem', fontWeight: 500, color: '#1e293b' }}>{file.name}</span>
                        <span style={{ fontSize: '0.78rem', color: '#94a3b8', marginLeft: '10px' }}>
                          {(file.size / 1024).toFixed(1)} KB
                        </span>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemoveFile(idx)}
                      style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '4px' }}
                      title="Remove"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>

              <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={handleAnalyze}
                  disabled={analyzing}
                  style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 24px', fontSize: '0.95rem' }}
                >
                  {analyzing ? (
                    <>
                      <RefreshCw size={16} className="spin" />
                      <span>Parsing & Extracting Clauses...</span>
                    </>
                  ) : (
                    <>
                      <FileCheck2 size={16} />
                      <span>Analyze & Cross-Verify Documents</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {error && (
            <div style={{
              marginTop: '16px',
              padding: '12px 16px',
              background: '#fef2f2',
              border: '1px solid #fecaca',
              borderRadius: '8px',
              color: '#991b1b',
              fontSize: '0.88rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}>
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}
        </div>
      )}

      {/* Analysis Results View */}
      {analysisResult && (
        <div className="doc-intel-results">
          {/* Action bar */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '20px',
            flexWrap: 'wrap',
            gap: '10px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ fontSize: '0.9rem', color: '#64748b' }}>
                Analyzed <strong>{analysisResult.documents.length}</strong> document(s)
              </span>
            </div>
            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                type="button"
                onClick={handleExportJSON}
                style={{
                  background: '#fff',
                  border: '1px solid #cbd5e1',
                  borderRadius: '6px',
                  padding: '7px 14px',
                  fontSize: '0.85rem',
                  fontWeight: 500,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  cursor: 'pointer',
                }}
              >
                <Download size={14} />
                Export Audit JSON
              </button>
              <button
                type="button"
                onClick={handleClearAll}
                style={{
                  background: 'none',
                  border: '1px solid #cbd5e1',
                  borderRadius: '6px',
                  padding: '7px 14px',
                  fontSize: '0.85rem',
                  fontWeight: 500,
                  color: '#475569',
                  cursor: 'pointer',
                }}
              >
                Upload New Documents
              </button>
            </div>
          </div>

          {/* Cross-Document Comparison Card (when >= 2 documents) */}
          {analysisResult.comparison && (
            <div style={{
              background: '#fff',
              border: '1px solid #e2e8f0',
              borderRadius: '12px',
              padding: '24px',
              marginBottom: '28px',
              boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Layers size={20} style={{ color: 'var(--forest-mid, #2d6a4f)' }} />
                  <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0 }}>
                    Cross-Document Reconciliation Matrix
                  </h2>
                </div>
                {/* Risk Level Badge */}
                <div style={{
                  padding: '4px 12px',
                  borderRadius: '20px',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  background: analysisResult.comparison.overall_risk_level === 'high'
                    ? '#fee2e2'
                    : analysisResult.comparison.overall_risk_level === 'medium'
                    ? '#fef3c7'
                    : '#dcfce7',
                  color: analysisResult.comparison.overall_risk_level === 'high'
                    ? '#991b1b'
                    : analysisResult.comparison.overall_risk_level === 'medium'
                    ? '#92400e'
                    : '#166534',
                }}>
                  {analysisResult.comparison.overall_risk_level} Risk Discrepancies
                </div>
              </div>

              <p style={{ color: '#475569', fontSize: '0.92rem', marginBottom: '20px' }}>
                {analysisResult.comparison.summary}
              </p>

              {/* Matching Parameters */}
              {analysisResult.comparison.matches?.length > 0 && (
                <div style={{ marginBottom: '20px' }}>
                  <h4 style={{ fontSize: '0.88rem', fontWeight: 600, color: '#166534', margin: '0 0 10px 0' }}>
                    Consistent Terms Across Documents ({analysisResult.comparison.matches.length})
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {analysisResult.comparison.matches.map((match, i) => (
                      <div key={i} style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        background: '#f0fdf4',
                        border: '1px solid #bbf7d0',
                        borderRadius: '6px',
                        padding: '8px 12px',
                        fontSize: '0.86rem',
                        color: '#15803d',
                      }}>
                        <CheckCircle2 size={16} />
                        <span>{match}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Discrepancies */}
              {analysisResult.comparison.discrepancies?.length > 0 && (
                <div>
                  <h4 style={{ fontSize: '0.88rem', fontWeight: 600, color: '#991b1b', margin: '0 0 12px 0' }}>
                    Identified Discrepancies & Conflict Points ({analysisResult.comparison.discrepancies.length})
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    {analysisResult.comparison.discrepancies.map((disc, idx) => (
                      <div key={idx} style={{
                        background: '#fff',
                        border: disc.severity === 'high' ? '1px solid #fca5a5' : '1px solid #fcd34d',
                        borderRadius: '8px',
                        padding: '16px',
                        borderLeft: disc.severity === 'high' ? '5px solid #dc2626' : '5px solid #d97706',
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                          <span style={{ fontWeight: 600, fontSize: '0.95rem', color: '#1e293b' }}>
                            {disc.field_name}
                          </span>
                          <span style={{
                            fontSize: '0.76rem',
                            fontWeight: 600,
                            padding: '2px 8px',
                            borderRadius: '4px',
                            background: disc.severity === 'high' ? '#fee2e2' : '#fef3c7',
                            color: disc.severity === 'high' ? '#b91c1c' : '#b45309',
                            textTransform: 'uppercase',
                          }}>
                            {disc.severity} severity
                          </span>
                        </div>
                        <p style={{ margin: '0 0 12px 0', fontSize: '0.88rem', color: '#475569' }}>
                          {disc.description}
                        </p>

                        {/* Values Table */}
                        <div style={{
                          background: '#f8fafc',
                          borderRadius: '6px',
                          padding: '10px 14px',
                          marginBottom: '12px',
                          fontSize: '0.84rem',
                        }}>
                          {Object.entries(disc.document_values).map(([fname, val]) => (
                            <div key={fname} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px dashed #e2e8f0' }}>
                              <span style={{ fontWeight: 500, color: '#334155' }}>{fname}:</span>
                              <span style={{ color: '#0f172a', fontWeight: 600 }}>
                                {Array.isArray(val) ? val.join(', ') : String(val)}
                              </span>
                            </div>
                          ))}
                        </div>

                        {/* Recommendation */}
                        <div style={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: '8px',
                          background: '#fdf4ff',
                          border: '1px solid #f5d0fe',
                          padding: '8px 12px',
                          borderRadius: '6px',
                          fontSize: '0.82rem',
                          color: '#86198f',
                        }}>
                          <HelpCircle size={15} style={{ flexShrink: 0, marginTop: '2px' }} />
                          <span><strong>Action Recommendation:</strong> {disc.recommendation}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Individual Document Extraction Tabs */}
          <div style={{ marginBottom: '16px' }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 700, margin: '0 0 12px 0', color: '#1e293b' }}>
              Extracted Legal Terms & Document Cards
            </h3>

            {/* Document Tabs */}
            <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid #e2e8f0', paddingBottom: '8px', overflowX: 'auto' }}>
              {analysisResult.documents.map((doc, idx) => (
                <button
                  key={doc.document_id}
                  type="button"
                  onClick={() => setActiveDocIndex(idx)}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '8px',
                    border: '1px solid',
                    borderColor: activeDocIndex === idx ? 'var(--forest-mid, #2d6a4f)' : '#cbd5e1',
                    background: activeDocIndex === idx ? 'var(--forest-mid, #2d6a4f)' : '#fff',
                    color: activeDocIndex === idx ? '#fff' : '#475569',
                    fontSize: '0.88rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    whiteSpace: 'nowrap',
                  }}
                >
                  <FileText size={15} />
                  <span>{doc.filename}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Active Document Details */}
          {activeDoc && (
            <div style={{
              background: '#fff',
              border: '1px solid #e2e8f0',
              borderRadius: '12px',
              padding: '24px',
              boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
            }}>
              {/* Doc Summary Header */}
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                flexWrap: 'wrap',
                gap: '12px',
                paddingBottom: '16px',
                borderBottom: '1px solid #e2e8f0',
                marginBottom: '20px',
              }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span style={{ fontSize: '1.2rem', fontWeight: 700, color: '#1e293b' }}>
                      {activeDoc.document_type}
                    </span>
                    <span style={{
                      fontSize: '0.75rem',
                      background: '#f1f5f9',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      color: '#475569',
                      fontWeight: 600,
                    }}>
                      {Math.round(activeDoc.document_type_confidence * 100)}% match
                    </span>
                  </div>
                  <div style={{ fontSize: '0.82rem', color: '#64748b', marginTop: '4px' }}>
                    File: <strong>{activeDoc.filename}</strong> &bull; {activeDoc.page_count} page(s) &bull; {(activeDoc.file_size_bytes / 1024).toFixed(1)} KB
                  </div>
                </div>

                {activeDoc.is_scanned_or_empty && (
                  <div style={{
                    background: '#fef3c7',
                    border: '1px solid #fde68a',
                    borderRadius: '6px',
                    padding: '6px 12px',
                    fontSize: '0.8rem',
                    color: '#92400e',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}>
                    <AlertTriangle size={15} />
                    <span>Scanned or unreadable text detected.</span>
                  </div>
                )}
              </div>

              {/* Extraction Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px' }}>
                {/* 1. Transacting Parties */}
                <div style={{
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: '10px',
                  padding: '16px',
                }}>
                  <h4 style={{ fontSize: '0.92rem', fontWeight: 700, color: '#1e293b', margin: '0 0 12px 0' }}>
                    1. Transacting Parties ({activeDoc.parties?.length || 0})
                  </h4>
                  {activeDoc.parties?.length ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {activeDoc.parties.map((p, idx) => (
                        <div key={idx} style={{
                          background: '#fff',
                          border: '1px solid #e2e8f0',
                          borderRadius: '6px',
                          padding: '10px',
                        }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontWeight: 600, fontSize: '0.88rem', color: '#0f172a' }}>
                              {p.name}
                            </span>
                            {p.evidence && (
                              <button
                                type="button"
                                onClick={() => setEvidenceModal({
                                  title: `Party: ${p.name}`,
                                  snippet: p.evidence.excerpt_text,
                                  page: p.evidence.page_number,
                                  docName: activeDoc.filename,
                                  line: p.evidence.line_number,
                                })}
                                style={{
                                  background: 'none',
                                  border: 'none',
                                  color: 'var(--forest-mid, #2d6a4f)',
                                  fontSize: '0.76rem',
                                  cursor: 'pointer',
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '3px',
                                  fontWeight: 600,
                                }}
                              >
                                <Eye size={12} />
                                <span>Page {p.evidence.page_number}</span>
                              </button>
                            )}
                          </div>
                          <span style={{ fontSize: '0.78rem', color: '#64748b', display: 'block', marginTop: '2px' }}>
                            {p.role}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p style={{ fontSize: '0.84rem', color: '#94a3b8', fontStyle: 'italic' }}>
                      No explicit parties detected in text.
                    </p>
                  )}
                </div>

                {/* 2. Property Schedule & Plot */}
                <div style={{
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: '10px',
                  padding: '16px',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <h4 style={{ fontSize: '0.92rem', fontWeight: 700, color: '#1e293b', margin: 0 }}>
                      2. Property Identification
                    </h4>
                    {activeDoc.property_details?.evidence && (
                      <button
                        type="button"
                        onClick={() => setEvidenceModal({
                          title: 'Property Identification Schedule',
                          snippet: activeDoc.property_details.evidence.excerpt_text,
                          page: activeDoc.property_details.evidence.page_number,
                          docName: activeDoc.filename,
                          line: activeDoc.property_details.evidence.line_number,
                        })}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: 'var(--forest-mid, #2d6a4f)',
                          fontSize: '0.76rem',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '3px',
                          fontWeight: 600,
                        }}
                      >
                        <Eye size={12} />
                        <span>Page {activeDoc.property_details.evidence.page_number}</span>
                      </button>
                    )}
                  </div>

                  <div style={{ fontSize: '0.85rem', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <div>
                      <span style={{ color: '#64748b', display: 'block', fontSize: '0.78rem' }}>Plot / Survey Number</span>
                      <strong style={{ color: '#0f172a' }}>
                        {activeDoc.property_details?.plot_survey_number || 'Not explicitly stated'}
                      </strong>
                    </div>

                    <div>
                      <span style={{ color: '#64748b', display: 'block', fontSize: '0.78rem' }}>Address Description</span>
                      <span style={{ color: '#0f172a' }}>
                        {activeDoc.property_details?.address || 'Not explicitly stated'}
                      </span>
                    </div>

                    <div>
                      <span style={{ color: '#64748b', display: 'block', fontSize: '0.78rem' }}>Area / Measurement</span>
                      <span style={{ color: '#0f172a' }}>
                        {activeDoc.property_details?.area_sqft || 'Not specified'}
                      </span>
                    </div>

                    {activeDoc.property_details?.boundaries && (
                      <div style={{ marginTop: '4px' }}>
                        <span style={{ color: '#64748b', display: 'block', fontSize: '0.78rem' }}>Schedule Boundaries:</span>
                        <div style={{ background: '#fff', padding: '6px 10px', borderRadius: '4px', fontSize: '0.78rem', marginTop: '4px' }}>
                          {Object.entries(activeDoc.property_details.boundaries).map(([dir, b]) => (
                            <div key={dir}><strong>{dir}:</strong> {b}</div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* 3. Financial Terms */}
                <div style={{
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: '10px',
                  padding: '16px',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <h4 style={{ fontSize: '0.92rem', fontWeight: 700, color: '#1e293b', margin: 0 }}>
                      3. Financial Consideration
                    </h4>
                    {activeDoc.financials?.evidence && (
                      <button
                        type="button"
                        onClick={() => setEvidenceModal({
                          title: 'Consideration & Stamp Duty Clause',
                          snippet: activeDoc.financials.evidence.excerpt_text,
                          page: activeDoc.financials.evidence.page_number,
                          docName: activeDoc.filename,
                          line: activeDoc.financials.evidence.line_number,
                        })}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: 'var(--forest-mid, #2d6a4f)',
                          fontSize: '0.76rem',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '3px',
                          fontWeight: 600,
                        }}
                      >
                        <Eye size={12} />
                        <span>Page {activeDoc.financials.evidence.page_number}</span>
                      </button>
                    )}
                  </div>

                  <div style={{ fontSize: '0.85rem', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <div>
                      <span style={{ color: '#64748b', display: 'block', fontSize: '0.78rem' }}>Declared Sale Price</span>
                      <strong style={{ fontSize: '1.05rem', color: '#0f172a' }}>
                        {activeDoc.financials?.declared_consideration || 'Unstated / Not found'}
                      </strong>
                    </div>

                    <div>
                      <span style={{ color: '#64748b', display: 'block', fontSize: '0.78rem' }}>Stamp Duty Paid</span>
                      <span style={{ color: '#0f172a' }}>
                        {activeDoc.financials?.stamp_duty || 'Not specified'}
                      </span>
                    </div>

                    <div>
                      <span style={{ color: '#64748b', display: 'block', fontSize: '0.78rem' }}>Registration Fees</span>
                      <span style={{ color: '#0f172a' }}>
                        {activeDoc.financials?.registration_fee || 'Not specified'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* 4. Dates & Sub-Registrar References */}
                <div style={{
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: '10px',
                  padding: '16px',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <h4 style={{ fontSize: '0.92rem', fontWeight: 700, color: '#1e293b', margin: 0 }}>
                      4. Registration & Dates
                    </h4>
                    {activeDoc.registration?.evidence && (
                      <button
                        type="button"
                        onClick={() => setEvidenceModal({
                          title: 'Registration Citation Clause',
                          snippet: activeDoc.registration.evidence.excerpt_text,
                          page: activeDoc.registration.evidence.page_number,
                          docName: activeDoc.filename,
                          line: activeDoc.registration.evidence.line_number,
                        })}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: 'var(--forest-mid, #2d6a4f)',
                          fontSize: '0.76rem',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '3px',
                          fontWeight: 600,
                        }}
                      >
                        <Eye size={12} />
                        <span>Page {activeDoc.registration.evidence.page_number}</span>
                      </button>
                    )}
                  </div>

                  <div style={{ fontSize: '0.85rem', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <div>
                      <span style={{ color: '#64748b', display: 'block', fontSize: '0.78rem' }}>Execution Date</span>
                      <strong style={{ color: '#0f172a' }}>
                        {activeDoc.dates?.execution_date || 'Not stated'}
                      </strong>
                    </div>

                    <div>
                      <span style={{ color: '#64748b', display: 'block', fontSize: '0.78rem' }}>Sub-Registrar Office (SRO)</span>
                      <span style={{ color: '#0f172a' }}>
                        {activeDoc.registration?.sub_registrar_office || 'Not stated'}
                      </span>
                    </div>

                    <div>
                      <span style={{ color: '#64748b', display: 'block', fontSize: '0.78rem' }}>Document / Registration No.</span>
                      <span style={{ color: '#0f172a' }}>
                        {activeDoc.registration?.registration_number || 'Not stated'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Warnings List */}
              {activeDoc.warnings?.length > 0 && (
                <div style={{
                  marginTop: '20px',
                  padding: '12px 16px',
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: '8px',
                }}>
                  <h5 style={{ margin: '0 0 6px 0', fontSize: '0.82rem', fontWeight: 600, color: '#475569' }}>
                    Extraction Transparency & Observations:
                  </h5>
                  <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '0.8rem', color: '#64748b' }}>
                    {activeDoc.warnings.map((w, idx) => (
                      <li key={idx} style={{ marginTop: '2px' }}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Legal Disclaimer Box */}
          <div style={{
            marginTop: '24px',
            padding: '16px',
            background: '#fafafa',
            border: '1px solid #e5e5e5',
            borderRadius: '8px',
            fontSize: '0.8rem',
            color: '#737373',
            lineHeight: 1.5,
          }}>
            <strong>Legal Notice:</strong> {analysisResult.legal_disclaimer}
          </div>
        </div>
      )}

      {/* Grounded Evidence Modal / Popover */}
      {evidenceModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.45)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '16px',
        }}
        onClick={() => setEvidenceModal(null)}
        >
          <div style={{
            background: '#fff',
            borderRadius: '12px',
            padding: '24px',
            maxWidth: '600px',
            width: '100%',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
          }}
          onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <FileCheck2 size={20} style={{ color: 'var(--forest-mid, #2d6a4f)' }} />
                <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 600 }}>
                  {evidenceModal.title}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setEvidenceModal(null)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}
              >
                <X size={18} />
              </button>
            </div>

            <div style={{
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
              borderRadius: '8px',
              padding: '14px',
              fontSize: '0.88rem',
              color: '#334155',
              fontFamily: 'monospace',
              lineHeight: 1.6,
              marginBottom: '16px',
            }}>
              "{evidenceModal.snippet}"
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: '#64748b' }}>
              <span>Document: <strong>{evidenceModal.docName}</strong></span>
              <span>Cited Page: <strong>Page {evidenceModal.page}</strong></span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
