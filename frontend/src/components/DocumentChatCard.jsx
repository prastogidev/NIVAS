import React, { useState } from 'react';
import {
  FileText,
  ChevronDown,
  ChevronRight,
  ShieldAlert,
  CheckCircle,
  AlertTriangle,
  Scale,
  Calendar,
  Building2,
  Users,
  DollarSign,
  FileCheck,
  Info,
} from 'lucide-react';

export default function DocumentChatCard({ documents = [], comparison = null, legalDisclaimer = null }) {
  const [expandedSections, setExpandedSections] = useState({
    summary: true,
    parties: true,
    property: false,
    financials: false,
    registration: false,
    comparison: true,
    warnings: true,
  });

  const toggleSection = (section) => {
    setExpandedSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  if (!documents || documents.length === 0) {
    return null;
  }

  return (
    <div className="chat-doc-card" data-testid="chat-doc-card">
      {/* Comparison Section if present */}
      {comparison && comparison.discrepancies && comparison.discrepancies.length > 0 && (
        <div className="chat-doc-comparison-block">
          <div
            className="chat-doc-section-header"
            onClick={() => toggleSection('comparison')}
            role="button"
            tabIndex={0}
            aria-expanded={expandedSections.comparison}
          >
            <div className="chat-doc-section-title">
              <Scale size={13} className="text-amber" />
              <span>Cross-Document Discrepancies ({comparison.discrepancies.length})</span>
            </div>
            {expandedSections.comparison ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </div>

          {expandedSections.comparison && (
            <div className="chat-doc-discrepancies-list">
              {comparison.discrepancies.map((disc, idx) => {
                const sevClass =
                  disc.severity === 'high'
                    ? 'chat-doc-severity-high'
                    : disc.severity === 'medium'
                    ? 'chat-doc-severity-medium'
                    : 'chat-doc-severity-low';

                return (
                  <div key={idx} className="chat-doc-discrepancy-card" data-testid="chat-discrepancy-card">
                    <div className="chat-doc-discrepancy-header">
                      <strong className="chat-doc-field-name">{disc.field_name}</strong>
                      <span className={`chat-doc-severity-badge ${sevClass}`}>
                        {disc.severity.toUpperCase()} SEVERITY
                      </span>
                    </div>
                    <p className="chat-doc-disc-desc">{disc.description}</p>

                    {disc.document_values && (
                      <div className="chat-doc-values-grid">
                        {Object.entries(disc.document_values).map(([docName, val], vIdx) => (
                          <div key={vIdx} className="chat-doc-val-row">
                            <span className="chat-doc-val-doc">{docName}:</span>
                            <span className="chat-doc-val-data">
                              {typeof val === 'object' ? JSON.stringify(val) : String(val || 'Not present')}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}

                    {disc.recommendation && (
                      <div className="chat-doc-disc-rec">
                        <Info size={11} />
                        <span>{disc.recommendation}</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Render Document Cards */}
      {documents.map((doc, docIdx) => {
        const isSynthetic =
          (doc.filename || '').toLowerCase().includes('sample') ||
          (doc.filename || '').toLowerCase().includes('synthetic') ||
          (doc.filename || '').toLowerCase().includes('demo');

        return (
          <div key={doc.document_id || docIdx} className="chat-single-doc-card">
            <div className="chat-doc-card-header">
              <div className="chat-doc-card-title">
                <FileText size={14} />
                <span title={doc.filename}>{doc.filename}</span>
              </div>
              <div className="chat-doc-header-badges">
                {isSynthetic && <span className="chat-doc-synthetic-pill">Synthetic Demo</span>}
                <span className="chat-doc-type-pill">{doc.document_type || 'Legal Document'}</span>
              </div>
            </div>

            <div className="chat-doc-card-body">
              {/* Executive Summary */}
              <div className="chat-doc-field-grid">
                <div className="chat-doc-field-row">
                  <span className="chat-doc-field-label">Document Overview</span>
                  <span className="chat-doc-field-val">
                    {doc.document_type} · {doc.page_count} {doc.page_count === 1 ? 'Page' : 'Pages'}
                  </span>
                </div>

                {/* Parties */}
                {doc.parties && doc.parties.length > 0 && (
                  <div className="chat-doc-field-row">
                    <span className="chat-doc-field-label">Extracted Parties</span>
                    <div className="chat-doc-parties-list">
                      {doc.parties.map((party, pIdx) => (
                        <div key={pIdx} className="chat-doc-party-entry">
                          <strong className="chat-party-name">{party.name}</strong>
                          <span className="chat-party-role">[{party.role}]</span>
                          {party.evidence?.page_number && (
                            <span className="chat-doc-page-cite">Page {party.evidence.page_number}</span>
                          )}
                          {party.evidence?.excerpt_text && (
                            <div className="chat-doc-evidence-excerpt">"{party.evidence.excerpt_text}"</div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Property Schedule */}
                {doc.property_details && (
                  <div className="chat-doc-field-row">
                    <span className="chat-doc-field-label">Property Schedule</span>
                    <span className="chat-doc-field-val">
                      {doc.property_details.plot_survey_number && (
                        <span>
                          Plot/Survey: <strong>{doc.property_details.plot_survey_number}</strong> ·{' '}
                        </span>
                      )}
                      {doc.property_details.address && <span>{doc.property_details.address}</span>}
                    </span>
                    {doc.property_details.evidence?.page_number && (
                      <span className="chat-doc-page-cite">Page {doc.property_details.evidence.page_number}</span>
                    )}
                  </div>
                )}

                {/* Financial Consideration */}
                {doc.financials && (
                  <div className="chat-doc-field-row">
                    <span className="chat-doc-field-label">Declared Consideration</span>
                    <span className="chat-doc-field-val">
                      <strong>
                        {doc.financials.numeric_amount
                          ? `₹${Number(doc.financials.numeric_amount).toLocaleString('en-IN')}`
                          : doc.financials.declared_consideration || 'Not explicitly stated'}
                      </strong>
                    </span>
                    {doc.financials.evidence?.page_number && (
                      <span className="chat-doc-page-cite">Page {doc.financials.evidence.page_number}</span>
                    )}
                  </div>
                )}

                {/* Registration */}
                {doc.registration && doc.registration.sub_registrar_office && (
                  <div className="chat-doc-field-row">
                    <span className="chat-doc-field-label">Registration / SRO Jurisdiction</span>
                    <span className="chat-doc-field-val">
                      {doc.registration.sub_registrar_office}
                      {doc.registration.registration_number && ` (Reg No: ${doc.registration.registration_number})`}
                    </span>
                  </div>
                )}
              </div>

              {/* Warnings if any */}
              {doc.warnings && doc.warnings.length > 0 && (
                <div className="chat-doc-warnings-box">
                  <div className="chat-doc-warning-title">
                    <AlertTriangle size={12} />
                    <span>Extraction Warnings & Notes</span>
                  </div>
                  <ul className="chat-doc-warning-list">
                    {doc.warnings.map((w, wIdx) => (
                      <li key={wIdx}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        );
      })}

      {/* Statutory Legal Disclaimer */}
      {legalDisclaimer && (
        <div className="chat-doc-legal-disclaimer">
          <ShieldAlert size={12} className="inline mr-1" />
          <span>{legalDisclaimer}</span>
        </div>
      )}
    </div>
  );
}
