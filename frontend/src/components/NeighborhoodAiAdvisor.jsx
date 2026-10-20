import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
  MessageSquare,
  Send,
  Loader2,
  Paperclip,
  X,
  FileText,
  FileCheck2,
  MapPin,
  Info,
  AlertCircle,
  Sparkles,
} from 'lucide-react';
import DocumentChatCard from './DocumentChatCard';
import {
  validateDocumentFiles,
  formatFileSize,
  isNeighborhoodQuery,
  isDocumentQuery,
  generateDocumentFollowUpReply,
} from '../services/documentChatHelper';
import {
  sendLivabilityChatMessage,
  analyzeDocuments,
  compareExtractedDocuments,
} from '../services/api';

export const DEFAULT_SUGGESTED_PROMPTS = [
  'Neighborhoods in South Delhi with best metro connectivity',
  'What healthcare facilities are nearby?',
  'How far away is the nearest mapped transit facility?',
  'What infrastructure is available in this area?',
  'What does the available air-quality data tell us?',
  'What information is missing for this locality?',
];

export default function NeighborhoodAiAdvisor({
  isOpen: propIsOpen,
  initialOpen = false,
  onOpenChange,
  location,
  locationContext,
  initialFiles,
  onClearInitialFiles,
  className = '',
}) {
  const isControlled = propIsOpen !== undefined;
  const [internalIsOpen, setInternalIsOpen] = useState(initialOpen);
  const isOpen = isControlled ? propIsOpen : internalIsOpen;

  const handleSetOpen = useCallback((nextOpen) => {
    if (!isControlled) {
      setInternalIsOpen(nextOpen);
    }
    if (typeof onOpenChange === 'function') {
      onOpenChange(nextOpen);
    }
  }, [isControlled, onOpenChange]);

  const [chatInput, setChatInput] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [chatError, setChatError] = useState(null);
  const [attachedFiles, setAttachedFiles] = useState([]);
  const [activeDocuments, setActiveDocuments] = useState([]);
  const [fileValidationErrors, setFileValidationErrors] = useState([]);
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const chatAbortControllerRef = useRef(null);

  const [messages, setMessages] = useState([
    {
      id: 1,
      sender: 'assistant',
      text: 'Welcome to the NIVAS Neighborhood AI Advisor. I answer questions about your selected location using verified OpenStreetMap civic infrastructure and atmospheric telemetry.\n\nYou can also attach property documents (Sale Deeds, Conveyance, Agreements) using the paperclip icon for legal entity extraction and cross-instrument discrepancy analysis.',
      time: 'Ready',
      sources: ['OpenStreetMap Overpass API', 'NIVAS Document Intelligence'],
      isAiGenerated: false,
      providerConfigured: false,
    },
  ]);

  // Sync initialFiles from navigation/bridge
  useEffect(() => {
    if (initialFiles && initialFiles.length > 0) {
      handleSetOpen(true);
      const { validFiles, errors } = validateDocumentFiles(initialFiles, attachedFiles.length);
      if (errors.length > 0) {
        setFileValidationErrors(errors);
      }
      if (validFiles.length > 0) {
        setAttachedFiles((prev) => {
          const combined = [...prev, ...validFiles];
          return combined.slice(0, 10);
        });
      }
      if (typeof onClearInitialFiles === 'function') {
        onClearInitialFiles();
      }
    }
  }, [initialFiles, attachedFiles.length, handleSetOpen, onClearInitialFiles]);

  // Scroll to bottom when new messages arrive or when panel opens
  useEffect(() => {
    if (isOpen && typeof messagesEndRef.current?.scrollIntoView === 'function') {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isOpen]);

  // Track location updates, abort in-flight queries, and append system notice
  const prevLocRef = useRef(location);
  useEffect(() => {
    const prev = prevLocRef.current;
    const hasChanged = prev && (
      location?.latitude !== prev?.latitude ||
      location?.longitude !== prev?.longitude ||
      location?.address !== prev?.address
    );

    if (hasChanged) {
      if (chatAbortControllerRef.current) {
        chatAbortControllerRef.current.abort();
        chatAbortControllerRef.current = null;
      }
      setIsChatLoading(false);
      setChatError(null);

      const addressLabel = location?.address || 'Selected Map Location';
      setMessages((m) => [
        ...m,
        {
          id: `loc-${Date.now()}`,
          sender: 'system',
          text: `Exploration focus updated: ${addressLabel}`,
          time: 'Pin Updated',
        },
      ]);
    }
    prevLocRef.current = location;
  }, [location?.latitude, location?.longitude, location?.address]);

  // Clean up abort controller on unmount
  useEffect(() => {
    return () => {
      if (chatAbortControllerRef.current) {
        chatAbortControllerRef.current.abort();
      }
    };
  }, []);

  const handleFileAttachClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
      fileInputRef.current.click();
    }
  };

  const handleFileInputChange = (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    const { validFiles, errors } = validateDocumentFiles(files, attachedFiles.length);
    if (errors.length > 0) {
      setFileValidationErrors(errors);
    } else {
      setFileValidationErrors([]);
    }
    if (validFiles.length > 0) {
      setAttachedFiles((prev) => {
        const combined = [...prev, ...validFiles];
        return combined.slice(0, 10);
      });
    }
  };

  const handleRemoveAttachedFile = (idxToRemove) => {
    setAttachedFiles((prev) => prev.filter((_, idx) => idx !== idxToRemove));
    setFileValidationErrors([]);
  };

  const handleClearAllAttachments = () => {
    setAttachedFiles([]);
    setFileValidationErrors([]);
  };

  const handleRemoveActiveDoc = (docId) => {
    setActiveDocuments((prev) => prev.filter((d) => (d.document_id || d.filename) !== docId));
  };

  const handleClearAllActiveDocs = () => {
    setActiveDocuments([]);
  };

  const activeSuggestedPrompts = useMemo(() => {
    if (activeDocuments.length === 1) {
      return [
        'Who are the buyer and seller in this deed?',
        'What is the declared sale consideration?',
        'What is the plot and khasra number?',
        'What are the registration and execution dates?',
        'What steps should a lawyer take to verify this deed?',
        'Does this document match the active map location?',
      ];
    }
    if (activeDocuments.length >= 2) {
      return [
        'Compare the 2 documents for discrepancies',
        'Are the plot numbers consistent across both deeds?',
        'Check for consideration differences',
        'Who are all the parties across both documents?',
        'Verify seller chain of ownership',
      ];
    }
    return DEFAULT_SUGGESTED_PROMPTS;
  }, [activeDocuments.length]);

  const handlePromptSelect = (promptText) => {
    setChatInput(promptText);
  };

  const handleSend = async (e) => {
    if (e) e.preventDefault();
    const query = chatInput.trim();
    if ((!query && attachedFiles.length === 0) || isChatLoading) return;

    if (chatAbortControllerRef.current) {
      chatAbortControllerRef.current.abort();
    }
    const abortController = new AbortController();
    chatAbortControllerRef.current = abortController;

    const activeLoc = location || {
      latitude: 28.5921,
      longitude: 77.0460,
      address: 'Dwarka Sector 12, South West Delhi, Delhi',
    };

    // FLOW 1: Document Upload & Analysis
    if (attachedFiles.length > 0) {
      const stagedFiles = [...attachedFiles];
      const previousChatInput = chatInput;
      const userMsgText = query || (stagedFiles.length === 1
        ? `Analyze uploaded document: ${stagedFiles[0].name}`
        : `Analyze ${stagedFiles.length} uploaded documents for legal review and comparison`);

      const userMsg = {
        id: Date.now(),
        sender: 'user',
        text: userMsgText,
        time: 'Just now',
        locationName: activeLoc.address || 'Selected Map Location',
        attachments: stagedFiles.map((f) => ({ name: f.name, size: f.size })),
      };

      setMessages((prev) => [...prev, userMsg]);
      setChatInput('');
      setAttachedFiles([]);
      setFileValidationErrors([]);
      setIsChatLoading(true);
      setChatError(null);

      try {
        const response = await analyzeDocuments(stagedFiles, abortController.signal);

        if (chatAbortControllerRef.current === abortController) {
          const newDocs = response.documents || [];
          let comparison = response.comparison || null;

          // Merge newly extracted documents with active context
          const existingIds = new Set(activeDocuments.map((d) => d.document_id || d.filename));
          const filteredNew = newDocs.filter((d) => !existingIds.has(d.document_id || d.filename));
          const combinedDocs = [...activeDocuments, ...filteredNew];

          if (!comparison && combinedDocs.length >= 2) {
            const isCompIntent = query && (
              query.toLowerCase().includes('compar') ||
              query.toLowerCase().includes('discrepan') ||
              query.toLowerCase().includes('conflict') ||
              query.toLowerCase().includes('differenc') ||
              query.toLowerCase().includes('reconcil') ||
              query.toLowerCase().includes('both')
            );
            if (stagedFiles.length >= 2 || isCompIntent) {
              try {
                comparison = await compareExtractedDocuments(combinedDocs, abortController.signal);
              } catch (cErr) {
                console.warn('Cross-document comparison call error:', cErr);
              }
            }
          }

          setActiveDocuments(combinedDocs);

          let replyText = '';
          if (comparison && comparison.discrepancies && comparison.discrepancies.length > 0) {
            replyText = `Document Intelligence compared ${combinedDocs.length} instruments ("${combinedDocs.map((d) => d.filename).join('", "')}") and identified ${comparison.discrepancies.length} discrepancy(ies) between declared terms. Cross-instrument reconciliation results and page citations are shown below.`;
          } else if (newDocs.length === 1 && activeDocuments.length === 0) {
            replyText = `Document Intelligence analyzed "${newDocs[0].filename}". Extracted legal metadata, parties, property schedule, and registration citations are shown below.`;
          } else {
            replyText = `Document Intelligence analyzed ${combinedDocs.length} documents. Extracted legal metadata, parties, property schedule, and cross-document reconciliation results are shown below.`;
          }

          const sources = (comparison && combinedDocs.length >= 2 ? combinedDocs : newDocs).map((d) => `${d.filename} (Page-grounded extraction)`);

          if (query && !isNeighborhoodQuery(query) && (!comparison || !query.toLowerCase().includes('compar'))) {
            const followUp = generateDocumentFollowUpReply(query, combinedDocs, activeLoc);
            if (followUp && followUp.text) {
              replyText = `${replyText}\n\n${followUp.text}`;
              if (followUp.sources) {
                sources.push(...followUp.sources);
              }
            }
          }

          const assistantMsg = {
            id: Date.now() + 1,
            sender: 'assistant',
            text: replyText,
            time: 'Just now',
            isDocumentAnalysis: true,
            analysisData: {
              documents: comparison && combinedDocs.length >= 2 ? combinedDocs : newDocs,
              comparison: comparison,
              legal_disclaimer: response.legal_disclaimer,
              registry_verification_status: response.registry_verification_status,
            },
            sources: Array.from(new Set(sources)),
            isAiGenerated: false,
          };

          setMessages((prev) => [...prev, assistantMsg]);
          setIsChatLoading(false);
          chatAbortControllerRef.current = null;
        }
      } catch (err) {
        if (err.name !== 'CanceledError' && err.name !== 'AbortError' && err?.code !== 'ERR_CANCELED') {
          if (chatAbortControllerRef.current === abortController) {
            setAttachedFiles(stagedFiles);
            setChatInput(previousChatInput);
            const errMsg = {
              id: Date.now() + 1,
              sender: 'assistant',
              text: `Document analysis failed: ${err.response?.data?.detail || err.message || 'Service unreachable'}. Your staged files have been preserved so you can retry.`,
              time: 'Error',
              isError: true,
            };
            setMessages((prev) => [...prev, errMsg]);
            setChatError(err.response?.data?.detail || err.message || 'Error uploading document');
            setIsChatLoading(false);
            chatAbortControllerRef.current = null;
          }
        }
      }
      return;
    }

    // FLOW 2: Document Context Follow-up Query
    const hasActiveDocs = activeDocuments.length > 0;
    const isDocQ = isDocumentQuery(query, false, activeDocuments.length);
    const isNeighQ = isNeighborhoodQuery(query);

    if (hasActiveDocs && (isDocQ || !isNeighQ)) {
      const userMsg = {
        id: Date.now(),
        sender: 'user',
        text: query,
        time: 'Just now',
        locationName: activeLoc.address || 'Selected Map Location',
      };
      setMessages((prev) => [...prev, userMsg]);
      setChatInput('');
      setIsChatLoading(true);
      setChatError(null);

      const followUp = generateDocumentFollowUpReply(query, activeDocuments, activeLoc);

      const replyMsg = {
        id: Date.now() + 1,
        sender: 'assistant',
        text: followUp.text,
        time: 'Just now',
        sources: followUp.sources || ['NIVAS Document Intelligence', 'Extracted Legal Clauses'],
        isAiGenerated: false,
        providerConfigured: false,
        locationName: activeLoc.address || 'Selected Map Location',
      };
      setMessages((prev) => [...prev, replyMsg]);
      setIsChatLoading(false);
      chatAbortControllerRef.current = null;
      return;
    }

    // FLOW 3: Spatial & Neighborhood Telemetry Query
    const userMsg = {
      id: Date.now(),
      sender: 'user',
      text: query,
      time: 'Just now',
      locationName: activeLoc.address || 'Selected Map Location',
    };

    setMessages((prev) => [...prev, userMsg]);
    setChatInput('');
    setIsChatLoading(true);
    setChatError(null);

    const currentContext = locationContext || {
      latitude: activeLoc.latitude,
      longitude: activeLoc.longitude,
      address: activeLoc.address,
      locality: activeLoc.address ? activeLoc.address.split(',')[0].trim() : null,
      search_radius_meters: 1200,
      facilities: [],
    };

    try {
      const response = await sendLivabilityChatMessage(
        {
          query,
          latitude: activeLoc.latitude,
          longitude: activeLoc.longitude,
          address: activeLoc.address,
          context: currentContext,
        },
        abortController.signal
      );

      if (chatAbortControllerRef.current === abortController) {
        const replyMsg = {
          id: Date.now() + 1,
          sender: 'assistant',
          text: response.reply,
          time: 'Just now',
          sources: response.sources || [],
          isAiGenerated: Boolean(response.is_ai_generated),
          providerConfigured: Boolean(response.provider_configured),
          providerName: response.provider_name,
          locationName: activeLoc.address || 'Selected Map Location',
        };
        setMessages((prev) => [...prev, replyMsg]);
        setIsChatLoading(false);
        chatAbortControllerRef.current = null;
      }
    } catch (err) {
      if (err.name !== 'CanceledError' && err.name !== 'AbortError' && err?.code !== 'ERR_CANCELED') {
        if (chatAbortControllerRef.current === abortController) {
          const errMsg = {
            id: Date.now() + 1,
            sender: 'assistant',
            text: `Unable to retrieve advisor response: ${err.message || 'Service unreachable'}. Coordinates and map navigation remain active.`,
            time: 'Error',
            isError: true,
          };
          setMessages((prev) => [...prev, errMsg]);
          setChatError(err.message || 'Error communicating with advisor');
          setIsChatLoading(false);
          chatAbortControllerRef.current = null;
        }
      }
    }
  };

  return (
    <div className={`global-ai-advisor-container ${className}`}>
      {/* Floating Expandable Neighborhood AI Advisor Panel */}
      {isOpen ? (
        <aside
          className="floating-advisor-panel livability-chat-panel"
          role="dialog"
          aria-label="Neighborhood AI Advisor Chat"
          data-testid="floating-advisor-panel"
        >
          <div className="chat-panel-header">
            <div className="chat-header-title-wrap">
              <img
                src="/neighborhood-ai-logo.svg"
                alt="Neighborhood AI Advisor logo"
                className="advisor-logo-img"
                width="52"
                height="52"
                onError={(e) => {
                  e.currentTarget.onerror = null;
                  e.currentTarget.src = '/neighborhood-ai-logo.png';
                }}
              />
              <div className="chat-header-title-text">
                <h3 className="chat-panel-title" data-testid="chat-panel-title">Neighborhood AI Advisor</h3>
                <span className="chat-panel-status">Interactive Preview · Document Intelligence</span>
              </div>
            </div>
            <div className="chat-header-actions">
              <span className="chat-mode-pill">AI Discovery</span>
              <button
                type="button"
                className="chat-minimize-btn"
                onClick={() => handleSetOpen(false)}
                aria-label="Minimize Advisor Chat"
                title="Minimize Advisor"
                data-testid="minimize-advisor-btn"
              >
                <X size={16} />
              </button>
            </div>
          </div>

          {/* Active Document Context Pill Strip */}
          {activeDocuments.length > 0 && (
            <div className="chat-active-docs-bar" data-testid="chat-active-docs-bar">
              <span className="chat-active-docs-label">
                <FileCheck2 size={12} />
                <span>Active Docs ({activeDocuments.length}):</span>
              </span>
              {activeDocuments.map((doc) => (
                <span
                  key={doc.document_id || doc.filename}
                  className="chat-active-doc-badge"
                  data-testid="chat-active-doc-badge"
                >
                  <FileText size={11} />
                  <span title={doc.filename}>{doc.filename}</span>
                  <button
                    type="button"
                    className="chat-active-doc-badge-remove"
                    onClick={() => handleRemoveActiveDoc(doc.document_id || doc.filename)}
                    aria-label={`Remove ${doc.filename} from active context`}
                    title="Remove from context"
                  >
                    <X size={10} />
                  </button>
                </span>
              ))}
              <button
                type="button"
                className="chat-active-docs-clear"
                onClick={handleClearAllActiveDocs}
                title="Clear all active documents"
                data-testid="chat-clear-active-docs-btn"
              >
                Clear All
              </button>
            </div>
          )}

          {/* Chat Messages Body */}
          <div className="chat-messages-scroll" role="log" aria-live="polite">
            {messages.length === 0 ? (
              <div className="chat-empty-state" data-testid="chat-empty-state">
                <p>No messages yet. Ask a question about this neighborhood's infrastructure, schools, transit, or air quality.</p>
              </div>
            ) : (
              messages.map((msg) => {
                if (msg.sender === 'system') {
                  return (
                    <div key={msg.id} className="chat-system-pill" data-testid="chat-system-notice">
                      <MapPin size={11} />
                      <span>{msg.text}</span>
                    </div>
                  );
                }

                return (
                  <div
                    key={msg.id}
                    className={`chat-bubble-row ${msg.sender === 'user' ? 'chat-row-user' : 'chat-row-assistant'}`}
                  >
                    {msg.sender === 'assistant' && (
                      <img
                        src="/neighborhood-ai-logo.svg"
                        alt="Neighborhood AI Advisor"
                        className="chat-msg-avatar"
                        width="36"
                        height="36"
                        onError={(e) => {
                          e.currentTarget.onerror = null;
                          e.currentTarget.src = '/neighborhood-ai-logo.png';
                        }}
                      />
                    )}
                    <div className={`chat-bubble ${msg.sender === 'user' ? 'bubble-user' : 'bubble-assistant'} ${msg.isError ? 'bubble-error' : ''}`}>
                      <p className="chat-bubble-text">{msg.text}</p>
                      {msg.attachments && msg.attachments.length > 0 && (
                        <div className="chat-msg-attachments-badge" style={{ marginTop: '0.35rem', display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
                          {msg.attachments.map((att, aIdx) => (
                            <span key={aIdx} className="chat-source-badge" style={{ background: 'rgba(255,255,255,0.2)', color: '#ffffff' }}>
                              📎 {att.name} ({formatFileSize(att.size)})
                            </span>
                          ))}
                        </div>
                      )}
                      {msg.isDocumentAnalysis && msg.analysisData && (
                        <DocumentChatCard
                          documents={msg.analysisData.documents}
                          comparison={msg.analysisData.comparison}
                          legalDisclaimer={msg.analysisData.legal_disclaimer}
                        />
                      )}
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="chat-bubble-sources">
                          <span className="chat-sources-label">Sources:</span>
                          {msg.sources.map((s, idx) => (
                            <span key={idx} className="chat-source-badge">{s}</span>
                          ))}
                        </div>
                      )}
                      {msg.sender === 'assistant' && !msg.isError && !msg.isDocumentAnalysis && (
                        <div className="chat-provenance-tag">
                          {msg.isAiGenerated ? (
                            <span className="tag-ai">AI Model: {msg.providerName || 'Generative LLM'}</span>
                          ) : (
                            <span className="tag-telemetry">Telemetry Grounded (AI Unconfigured)</span>
                          )}
                        </div>
                      )}
                      {msg.sender === 'assistant' && msg.isDocumentAnalysis && (
                        <div className="chat-provenance-tag">
                          <span className="tag-telemetry">Grounded Extraction · Page Citations Verified</span>
                        </div>
                      )}
                      <span className="chat-bubble-time">{msg.time}</span>
                    </div>
                  </div>
                );
              })
            )}

            {isChatLoading && (
              <div className="chat-bubble-row chat-row-assistant" data-testid="chat-loading-row">
                <img
                  src="/neighborhood-ai-logo.svg"
                  alt="Neighborhood AI Advisor"
                  className="chat-msg-avatar"
                  width="36"
                  height="36"
                  onError={(e) => {
                    e.currentTarget.onerror = null;
                    e.currentTarget.src = '/neighborhood-ai-logo.png';
                  }}
                />
                <div className="chat-bubble bubble-assistant loading" role="status" aria-live="polite">
                  <div className="chat-loading-indicator">
                    <Loader2 size={13} className="spin-icon" />
                    <span>Analyzing verified location telemetry...</span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick Prompts Suggestions */}
          <div className="chat-prompts-section">
            <span className="prompts-label">Suggested Inquiries:</span>
            <div className="prompts-chips-wrapper">
              {activeSuggestedPrompts.map((prompt, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="prompt-chip-btn"
                  onClick={() => handlePromptSelect(prompt)}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>

          {/* Chat Input Bar */}
          <form onSubmit={handleSend} className="chat-input-form">
            {/* Staged Attachments Tray */}
            {attachedFiles.length > 0 && (
              <div className="chat-attachments-tray" data-testid="chat-attachments-tray">
                {attachedFiles.map((file, idx) => (
                  <div key={idx} className="chat-attachment-chip" data-testid="chat-attachment-chip">
                    <FileText size={12} />
                    <span className="chat-attachment-chip-name" title={file.name}>{file.name}</span>
                    <span className="chat-attachment-chip-size">({formatFileSize(file.size)})</span>
                    <button
                      type="button"
                      className="chat-attachment-chip-remove"
                      onClick={() => handleRemoveAttachedFile(idx)}
                      aria-label={`Remove ${file.name}`}
                    >
                      <X size={10} />
                    </button>
                  </div>
                ))}
                {attachedFiles.length > 1 && (
                  <button
                    type="button"
                    className="chat-attachments-clear-btn"
                    onClick={handleClearAllAttachments}
                  >
                    Clear All
                  </button>
                )}
              </div>
            )}

            {/* File Validation Errors */}
            {fileValidationErrors.length > 0 && (
              <div
                className="chat-validation-errors"
                data-testid="chat-validation-errors"
                style={{
                  color: '#dc2626',
                  fontSize: '0.72rem',
                  marginBottom: '0.4rem',
                  padding: '0.2rem 0.5rem',
                  background: '#fef2f2',
                  borderRadius: '4px',
                }}
              >
                {fileValidationErrors.map((err, idx) => (
                  <div key={idx} className="flex items-center gap-1">
                    <AlertCircle size={11} className="inline mr-1" />
                    <span>{err}</span>
                  </div>
                ))}
              </div>
            )}

            <div className="chat-input-wrapper">
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.txt,.text,.md,.markdown,.csv"
                style={{ display: 'none' }}
                onChange={handleFileInputChange}
                data-testid="chat-file-input"
              />
              <button
                type="button"
                className={`chat-attach-btn ${attachedFiles.length > 0 ? 'has-attachments' : ''}`}
                onClick={handleFileAttachClick}
                aria-label="Attach documents for analysis"
                title="Attach property documents (PDF, TXT, MD up to 10MB)"
                disabled={isChatLoading}
                data-testid="chat-attach-btn"
              >
                <Paperclip size={16} />
              </button>
              <input
                type="text"
                className="chat-text-input"
                placeholder={
                  attachedFiles.length > 0
                    ? `Ask questions about ${attachedFiles.length} attached document${attachedFiles.length > 1 ? 's' : ''}...`
                    : activeDocuments.length > 0
                    ? `Ask about ${activeDocuments[0].filename} or neighborhood...`
                    : 'Ask about neighborhood livability, commute, schools...'
                }
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                disabled={isChatLoading}
              />
              <button
                type="submit"
                className="chat-send-btn"
                disabled={(!chatInput.trim() && attachedFiles.length === 0) || isChatLoading}
                aria-label="Send message"
              >
                {isChatLoading ? <Loader2 size={15} className="spin-icon" /> : <Send size={15} />}
              </button>
            </div>
            <div className="chat-input-footnote">
              <Info size={11} />
              <span>
                {activeDocuments.length > 0
                  ? 'Document & neighborhood intelligence grounded in page citations & OSM telemetry'
                  : 'Answers grounded strictly in verified location telemetry · Zero synthetic data'}
              </span>
            </div>
          </form>
        </aside>
      ) : (
        /* Small Floating Circular AI Advisor Launcher */
        <button
          type="button"
          className="floating-advisor-launcher"
          onClick={() => handleSetOpen(true)}
          aria-label="Open NIVAS AI Advisor"
          title="Open NIVAS AI Advisor"
          data-testid="advisor-launcher-btn"
        >
          <div className="launcher-icon-wrap">
            <img
              src="/neighborhood-ai-logo.svg"
              alt=""
              aria-hidden="true"
              className="launcher-logo-img"
              width="28"
              height="28"
              onError={(e) => {
                e.currentTarget.style.display = 'none';
                if (e.currentTarget.nextElementSibling) {
                  e.currentTarget.nextElementSibling.style.display = 'flex';
                }
              }}
            />
            <span className="launcher-fallback-icon" style={{ display: 'none' }}>
              <MessageSquare size={22} />
            </span>
            <span className="launcher-accessible-title sr-only" style={{
              position: 'absolute',
              width: '1px',
              height: '1px',
              padding: 0,
              margin: '-1px',
              overflow: 'hidden',
              clip: 'rect(0, 0, 0, 0)',
              whiteSpace: 'nowrap',
              border: 0,
            }}>
              Neighborhood AI Advisor
            </span>
          </div>
        </button>
      )}
    </div>
  );
}
