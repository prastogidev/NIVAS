import React, { useState } from 'react';
import StepHeader from './components/StepHeader';
import UploadScreen from './components/UploadScreen';
import ProcessingScreen from './components/ProcessingScreen';
import ResultsScreen from './components/ResultsScreen';
import ReportScreen from './components/ReportScreen';
import CompareForm from './components/CompareForm';
import CompareResultsView from './components/CompareResultsView';
import { submitPropertyScore, compareProperties } from './services/api';
import { Building2, RefreshCw, Scale, Search } from 'lucide-react';
import nivasLogo from './assets/nivas_logo.png';

export default function App() {
  const [mode, setMode] = useState('single'); // 'single' | 'compare'
  const [currentScreen, setCurrentScreen] = useState('upload'); // 'upload' | 'processing' | 'results' | 'report'

  // Single Property State
  const [payload, setPayload] = useState(null);
  const [result, setResult] = useState(null);

  // Compare Mode State
  const [comparePayload, setComparePayload] = useState(null);
  const [compareResult, setCompareResult] = useState(null);

  const [error, setError] = useState(null);

  const handleSingleSubmit = async (formData) => {
    setPayload(formData);
    setError(null);
    setCurrentScreen('processing');

    try {
      const data = await submitPropertyScore(formData);
      setResult(data);
      setCurrentScreen('results');
    } catch (err) {
      console.error('API submission error:', err);
      let errorMessage = 'Failed to connect to backend API at http://127.0.0.1:8000/api/score';
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
    setError(null);
    setCurrentScreen('processing');

    try {
      const data = await compareProperties(formData);
      setCompareResult(data);
      setCurrentScreen('results');
    } catch (err) {
      console.error('Compare API submission error:', err);
      let errorMessage = 'Failed to connect to backend API at http://127.0.0.1:8000/api/score/compare';
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
        </div>

        <div className="header-controls">
          {/* Mode Switcher */}
          <div className="mode-switcher">
            <button
              className={`mode-btn ${mode === 'single' ? 'active' : ''}`}
              onClick={() => switchMode('single')}
            >
              <Search size={14} />
              <span>Single Inspection</span>
            </button>

            <button
              className={`mode-btn ${mode === 'compare' ? 'active' : ''}`}
              onClick={() => switchMode('compare')}
            >
              <Scale size={14} />
              <span>Property Compare</span>
            </button>
          </div>

          {hasData && (
            <button className="btn-secondary-sm" onClick={handleReset}>
              <RefreshCw size={14} />
              <span>Reset</span>
            </button>
          )}
        </div>
      </header>

      {/* 4-Step Wizard Header */}
      <StepHeader
        currentScreen={currentScreen}
        onSelectScreen={setCurrentScreen}
        hasResult={hasData}
      />

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
    </div>
  );
}
