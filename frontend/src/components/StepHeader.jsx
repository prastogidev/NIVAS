import React from 'react';
import { Upload, Cpu, BarChart3, FileText, CheckCircle2 } from 'lucide-react';

export default function StepHeader({ currentScreen, onSelectScreen, hasResult }) {
  const steps = [
    { id: 'upload', label: '1. Property Details', icon: Upload },
    { id: 'processing', label: '2. Inspection Pipeline', icon: Cpu },
    { id: 'results', label: '3. Composite Scores', icon: BarChart3 },
    { id: 'report', label: '4. Executive Report', icon: FileText },
  ];

  const getStepIndex = (id) => steps.findIndex((s) => s.id === id);
  const currentIndex = getStepIndex(currentScreen);

  return (
    <div className="step-navigation">
      {steps.map((step, idx) => {
        const Icon = step.icon;
        const isCompleted = idx < currentIndex;
        const isActive = idx === currentIndex;
        const isDisabled = (step.id === 'results' || step.id === 'report' || step.id === 'processing') && !hasResult && !isActive;

        return (
          <div
            key={step.id}
            className={`step-item ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''} ${isDisabled ? 'disabled' : ''}`}
            onClick={() => {
              if (!isDisabled && (hasResult || step.id === 'upload')) {
                onSelectScreen(step.id);
              }
            }}
          >
            <div className="step-badge">
              {isCompleted ? <CheckCircle2 size={16} /> : <Icon size={16} />}
            </div>
            <span className="step-label">{step.label}</span>
            {idx < steps.length - 1 && <div className="step-connector" />}
          </div>
        );
      })}
    </div>
  );
}
