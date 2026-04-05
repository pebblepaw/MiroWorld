import { useApp } from '@/contexts/AppContext';
import React from 'react';

const stepLabels = ['Upload', 'Agents', 'Simulate', 'Report', 'Analytics'];

export function StepProgress() {
  const { currentStep, completedSteps } = useApp();

  return (
    <div className="flex items-center justify-between px-4 py-3 w-full">
      {stepLabels.map((label, i) => {
        const step = i + 1;
        const active = currentStep === step;
        const completed = completedSteps.includes(step);
        return (
          <React.Fragment key={step}>
            <div className="flex items-center gap-2 shrink-0 px-2">
              <div
                className={`w-5 h-5 rounded flex items-center justify-center text-[9px] font-mono font-bold flex-shrink-0 transition-colors ${
                  active
                    ? 'bg-white text-black'
                    : completed
                    ? 'bg-white/15 text-white/60'
                    : 'bg-white/5 text-muted-foreground'
                }`}
              >
                {step}
              </div>
              <span className={`text-xs hidden sm:block font-mono uppercase tracking-wider ${
                active ? 'text-foreground' : 'text-muted-foreground'
              }`}>
                {label}
              </span>
            </div>
            {i < stepLabels.length - 1 && (
              <div className={`h-px flex-1 min-w-4 mx-2 ${completed ? 'bg-white/20' : 'bg-border'}`} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}
