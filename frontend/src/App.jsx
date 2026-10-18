import React, { useState, useEffect } from 'react';
import UploadScreen from './components/UploadScreen';
import ProcessingScreen from './components/ProcessingScreen';
import ResultsScreen from './components/ResultsScreen';
import ReportScreen from './components/ReportScreen';
import CompareForm from './components/CompareForm';
import CompareResultsView from './components/CompareResultsView';
import LivabilityWorkspace from './components/LivabilityWorkspace';
import DisasterWorkspace from './components/DisasterWorkspace';
import DocumentIntelligenceWorkspace from './components/DocumentIntelligenceWorkspace';
import { submitPropertyScore, compareProperties } from './services/api';
import { Building2, RefreshCw, Scale, Search, Compass, ShieldCheck, AlertTriangle, FileText } from 'lucide-react';
import nivasLogo from './assets/nivas_logo.png';

const HEADER_TAGLINE = 'Find the place that feels like home.';

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

const getInitialAppSection = () => {
  try {
    if (typeof window !== 'undefined' && window.location?.hash) {
      const hash = window.location.hash.replace('#', '').toLowerCase();
      if (hash === 'livability' || hash === 'inspection' || hash === 'disaster' || hash === 'documents') {
        return hash;
      }
    }
    const saved = safeStorage.getItem('nivas_app_section');
    if (saved === 'livability' || saved === 'inspection' || saved === 'disaster' || saved === 'documents') {
      return saved;
    }
  } catch (e) {
    // Ignore storage/window errors in restricted environments
  }
  return 'livability';
};

export default function App() {
  const [appSection, setAppSection] = useState(getInitialAppSection); // 'livability' by default, persisted across reloads
  const [mode, setMode] = useState(() => {
    const saved = safeStorage.getItem('nivas_inspection_mode');
    if (saved === 'single' || saved === 'compare') return saved;
    return 'single';
  });
  const [currentScreen, setCurrentScreen] = useState('upload'); // 'upload' | 'processing' | 'results' | 'report'

  // Single Property State
  const [payload, setPayload] = useState(null);
  const [result, setResult] = useState(null);

  // Compare Mode State
  const [comparePayload, setComparePayload] = useState(null);
  const [compareResult, setCompareResult] = useState(null);

  // Livability Workspace Independent State (completely decoupled from inspection)
  const [livabilityLocation, setLivabilityLocation] = useState(() => {
    const saved = safeStorage.getItem('nivas_livability_location');
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
  const [livabilitySearchQuery, setLivabilitySearchQuery] = useState('');
  const [advisorInitialOpen, setAdvisorInitialOpen] = useState(true);
  const [advisorInitialFiles, setAdvisorInitialFiles] = useState([]);

  // Persist active section across reloads and sync with URL hash
  useEffect(() => {
    safeStorage.setItem('nivas_app_section', appSection);
    if (typeof window !== 'undefined' && window.location && window.location.hash !== `#${appSection}`) {
      window.history.replaceState(null, '', `#${appSection}`);
    }
  }, [appSection]);

  // Listen to browser forward/back navigation hash changes
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const handleHashChange = () => {
      const hash = window.location.hash.replace('#', '').toLowerCase();
      if (hash === 'livability' || hash === 'inspection' || hash === 'disaster' || hash === 'documents') {
        setAppSection(hash);
      }
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  // Persist mode and location
  useEffect(() => {
    safeStorage.setItem('nivas_inspection_mode', mode);
  }, [mode]);

  useEffect(() => {
    safeStorage.setItem('nivas_livability_location', JSON.stringify(livabilityLocation));
  }, [livabilityLocation]);

  const [error, setError] = useState(null);

  const handleSingleSubmit = async (formData) => {
    setPayload(formData);
    setResult(null); // Invalidate any previous property results immediately
    setError(null);
    setCurrentScreen('processing');

    try {
      const data = await submitPropertyScore(formData);
      setResult(data);
      setCurrentScreen('results');
    } catch (err) {
      console.error('API submission error:', err);
      setResult(null); // Ensure no stale result is retained on failure
      let errorMessage = 'Failed to connect to backend API (/api/score)';
      if (err.response?.data?.detail) {
        if (typeof err.response.data.detail === 'string') {
          errorMessage = err.response.data.detail;
        } else if (Array.isArray(err.response.data.detail)) {
          errorMessage = err.response.data.detail.map((d) => d.msg || JSON.stringify(d)).join(', ');
        } else {
          errorMessage = JSON.stringify(err.response.data.detail);
        }
      } else if (err.message) {
        errorMessage = err.message;
      }
      setError(errorMessage);
    }
  };

  const handleCompareSubmit = async (formData) => {
    setComparePayload(formData);
    setCompareResult(null); // Invalidate any previous compare results immediately
    setError(null);
    setCurrentScreen('processing');

    try {
      const data = await compareProperties(formData);
      setCompareResult(data);
      setCurrentScreen('results');
    } catch (err) {
      console.error('Compare API submission error:', err);
      setCompareResult(null); // Ensure no stale compare result is retained on failure
      let errorMessage = 'Failed to connect to backend API (/api/score/compare)';
      if (err.response?.data?.detail) {
        if (typeof err.response.data.detail === 'string') {
          errorMessage = err.response.data.detail;
        } else if (Array.isArray(err.response.data.detail)) {
          errorMessage = err.response.data.detail.map((d) => d.msg || JSON.stringify(d)).join(', ');
        } else {
          errorMessage = JSON.stringify(err.response.data.detail);
        }
      } else if (err.message) {
        errorMessage = err.message;
      }
      setError(errorMessage);
    }
  };

  const handleReset = () => {
    setPayload(null);
    setResult(null);
    setComparePayload(null);
    setCompareResult(null);
    setError(null);
    setCurrentScreen('upload');
  };

  const switchMode = (newMode) => {
    if (newMode === mode) return;
    setMode(newMode);
    handleReset();
  };

  const hasData = mode === 'single' ? !!result : !!compareResult;

  return (
    <div className="app-container">
      {/* Header Bar */}
      <header className="header">
        <div className="header-brand">
          <img src={nivasLogo} alt="NIVAS" className="header-logo-img" />
          <div className="header-tagline-divider" aria-hidden="true" />
          <span className="header-tagline">
            <span className="header-tagline-dot" aria-hidden="true" />
            {HEADER_TAGLINE}
          </span>
        </div>

        <div className="header-controls">
          {/* Top-Right Section Switcher: Livability vs Disaster Hazards vs Property Inspection vs Document Intelligence */}
          <div className="mode-switcher">
            <button
              className={`mode-btn ${appSection === 'livability' ? 'active' : ''}`}
              onClick={() => setAppSection('livability')}
            >
              <Compass size={14} />
              <span>Livability</span>
            </button>

            <button
              className={`mode-btn ${appSection === 'disaster' ? 'active' : ''}`}
              onClick={() => setAppSection('disaster')}
            >
              <AlertTriangle size={14} />
              <span>Disaster Hazards</span>
            </button>

            <button
              className={`mode-btn ${appSection === 'inspection' ? 'active' : ''}`}
              onClick={() => setAppSection('inspection')}
            >
              <ShieldCheck size={14} />
              <span>Property Inspection</span>
            </button>

            <button
              className={`mode-btn ${appSection === 'documents' ? 'active' : ''}`}
              onClick={() => setAppSection('documents')}
            >
              <FileText size={14} />
              <span>Document Intelligence</span>
            </button>
          </div>

          {appSection === 'inspection' && hasData && (
            <button className="btn-secondary-sm" onClick={handleReset}>
              <RefreshCw size={14} />
              <span>Reset</span>
            </button>
          )}
        </div>
      </header>

      {/* Main Content Area */}
      {appSection === 'livability' ? (
        <main className="screen-content">
          <LivabilityWorkspace
            location={livabilityLocation}
            onLocationChange={setLivabilityLocation}
            searchQuery={livabilitySearchQuery}
            onSearchQueryChange={setLivabilitySearchQuery}
            initialChatOpen={advisorInitialOpen}
            initialFiles={advisorInitialFiles}
            onClearInitialFiles={() => setAdvisorInitialFiles([])}
          />
        </main>
      ) : appSection === 'disaster' ? (
        <main className="screen-content">
          <DisasterWorkspace
            location={livabilityLocation}
            onLocationChange={setLivabilityLocation}
          />
        </main>
      ) : appSection === 'documents' ? (
        <main className="screen-content">
          <DocumentIntelligenceWorkspace
            onOpenInChat={(files) => {
              if (files && files.length > 0) {
                setAdvisorInitialFiles(files);
              }
              setAdvisorInitialOpen(true);
              setAppSection('livability');
            }}
          />
        </main>
      ) : (
        /* Property Inspection Experience */
        <>
          {/* Change 2: Replaced the pipeline box with Single Inspection & Property Compare Mode Switcher */}
          <div className="pipeline-mode-container">
            <div className="pipeline-mode-title-wrap">
              <Building2 size={20} style={{ color: 'var(--ink-deep)' }} />
              <div>
                <span className="pipeline-mode-title">Inspection Workflow Mode</span>
                <span className="pipeline-mode-subtitle" style={{ display: 'block' }}>
                  {mode === 'single'
                    ? 'Analyze a single property across location, valuation, defect, and thermal evidence'
                    : 'Side-by-side comparative evaluation of two real property locations'}
                </span>
              </div>
            </div>

            <div className="pipeline-mode-switcher">
              <button
                className={`pipeline-mode-btn ${mode === 'single' ? 'active' : ''}`}
                onClick={() => switchMode('single')}
              >
                <Search size={14} />
                <span>Single Inspection</span>
              </button>

              <button
                className={`pipeline-mode-btn ${mode === 'compare' ? 'active' : ''}`}
                onClick={() => switchMode('compare')}
              >
                <Scale size={14} />
                <span>Property Compare</span>
              </button>
            </div>
          </div>

      {/* Screen Router */}
      <main className="screen-content">
        {currentScreen === 'upload' && (
          mode === 'single' ? (
            <UploadScreen onSubmit={handleSingleSubmit} error={error} />
          ) : (
            <CompareForm onSubmit={handleCompareSubmit} error={error} />
          )
        )}

        {currentScreen === 'processing' && (
          <ProcessingScreen
            payload={mode === 'single' ? payload : { address: comparePayload?.property_a?.address, property_type: 'Dual Comparison' }}
            error={error}
            onRetry={() => {
              if (mode === 'single' && payload) {
                handleSingleSubmit(payload);
              } else if (mode === 'compare' && comparePayload) {
                handleCompareSubmit(comparePayload);
              }
            }}
            onBack={() => {
              setError(null);
              setCurrentScreen('upload');
            }}
          />
        )}

        {currentScreen === 'results' && (
          mode === 'single' ? (
            <ResultsScreen
              result={result}
              onViewReport={() => setCurrentScreen('report')}
            />
          ) : (
            <CompareResultsView
              compareResult={compareResult}
              onReset={handleReset}
            />
          )
        )}

        {currentScreen === 'report' && (
          mode === 'single' ? (
            <ReportScreen
              result={result}
              onReset={handleReset}
            />
          ) : (
            <CompareResultsView
              compareResult={compareResult}
              onReset={handleReset}
            />
          )
        )}
      </main>
    </>
  )}
    </div>
  );
}
