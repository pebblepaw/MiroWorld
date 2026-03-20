import { useApp } from '@/contexts/AppContext';

const stepLabels = ['Upload', 'Agents', 'Simulate', 'Analyse', 'Chat'];

export function StepProgress() {
  const { currentStep, completedSteps } = useApp();

  return (
    <div className="flex items-center gap-1 px-4 py-3">
      {stepLabels.map((label, i) => {
        const step = i + 1;
        const active = currentStep === step;
        const completed = completedSteps.includes(step);
        return (
          <div key={step} className="flex items-center gap-1 flex-1">
            <div className="flex items-center gap-2 flex-1">
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-mono font-bold flex-shrink-0 transition-all ${
                  active
                    ? 'bg-primary text-primary-foreground shadow-[0_0_12px_hsl(var(--primary)/0.4)]'
                    : completed
                    ? 'bg-success/20 text-success border border-success/30'
                    : 'bg-muted/50 text-muted-foreground'
                }`}
              >
                {step}
              </div>
              <span className={`text-xs hidden sm:block ${active ? 'text-primary font-medium' : 'text-muted-foreground'}`}>
                {label}
              </span>
            </div>
            {i < stepLabels.length - 1 && (
              <div className={`h-px flex-1 min-w-4 ${completed ? 'bg-success/40' : 'bg-border'}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}
