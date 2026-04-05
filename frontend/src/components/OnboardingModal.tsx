import { useState, useEffect } from 'react';
import { useApp } from '@/contexts/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Globe, Cpu, Key, Target, ArrowRight } from 'lucide-react';

const COUNTRIES = [
  { id: 'singapore', name: 'Singapore', emoji: '🇸🇬', available: true },
  { id: 'usa', name: 'USA', emoji: '🇺🇸', available: true },
  { id: 'india', name: 'India', emoji: '🇮🇳', available: false },
  { id: 'japan', name: 'Japan', emoji: '🇯🇵', available: false },
];

const PROVIDERS: Record<string, { name: string; models: string[]; requiresKey: boolean }> = {
  gemini: {
    name: 'Google Gemini',
    models: ['gemini-2.0-flash', 'gemini-1.5-pro'],
    requiresKey: true,
  },
  openai: {
    name: 'OpenAI',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'],
    requiresKey: true,
  },
  ollama: {
    name: 'Ollama (Local)',
    models: ['qwen3:4b-instruct-2507-q4_K_M', 'llama3:8b'],
    requiresKey: false,
  },
};

const USE_CASES = [
  { id: 'policy-review', label: 'Policy Review' },
  { id: 'ad-testing', label: 'Ad Testing' },
  { id: 'pmf-discovery', label: 'PMF Discovery' },
  { id: 'reviews', label: 'Reviews' },
];

export function OnboardingModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const app = useApp();

  const [country, setCountry] = useState(app.country || 'singapore');
  const [provider, setProvider] = useState(app.modelProvider || 'gemini');
  const [model, setModel] = useState(app.modelName || PROVIDERS['gemini'].models[0]);
  const [apiKey, setApiKey] = useState(app.modelApiKey || '');
  const [useCase, setUseCase] = useState(app.useCase || 'policy-review');

  useEffect(() => {
    if (provider && !PROVIDERS[provider].models.includes(model)) {
      setModel(PROVIDERS[provider].models[0]);
    }
  }, [provider, model]);

  if (!isOpen) return null;

  const handleLaunch = () => {
    app.setCountry(country);
    app.setModelProvider(provider as any);
    app.setModelName(model);
    app.setModelApiKey(apiKey);
    app.setUseCase(useCase);
    // In a real app we might call POST /api/v2/session/create here
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="surface-card w-full max-w-2xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
        
        {/* Header */}
        <div className="p-6 border-b border-border text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-white/5 border border-white/10 mb-4">
            <Globe className="w-6 h-6 text-foreground" />
          </div>
          <h2 className="text-2xl font-semibold text-foreground tracking-tight">Configure Simulation</h2>
          <p className="text-sm text-muted-foreground mt-1">Select your environment parameters to spin up a new OASIS instance.</p>
        </div>

        {/* Scrollable Form Content */}
        <div className="p-6 overflow-y-auto scrollbar-thin space-y-8">
          
          {/* Country / Region */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Globe className="w-4 h-4 text-muted-foreground" />
              <span className="label-meta">Region & Dataset</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {COUNTRIES.map((c) => {
                const isSelected = country === c.id;
                return (
                  <button
                    key={c.id}
                    disabled={!c.available}
                    onClick={() => setCountry(c.id)}
                    className={`
                      relative p-4 rounded-xl border flex flex-col items-center justify-center gap-2 transition-all
                      ${c.available ? 'cursor-pointer hover:bg-white/5' : 'cursor-not-allowed opacity-40'}
                      ${isSelected ? 'border-[hsl(var(--data-blue))] bg-[hsl(var(--data-blue))]/10' : 'border-white/10 bg-transparent'}
                    `}
                  >
                    {!c.available && (
                      <span className="absolute -top-2 text-[8px] uppercase tracking-wider font-mono bg-white/10 text-white/60 px-1.5 py-0.5 rounded">
                        Coming Soon
                      </span>
                    )}
                    <span className="text-2xl">{c.emoji}</span>
                    <span className={`text-xs font-medium ${isSelected ? 'text-[hsl(var(--data-blue))]' : 'text-foreground'}`}>
                      {c.name}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Core Configuration: Provider & Model */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Cpu className="w-4 h-4 text-muted-foreground" />
              <span className="label-meta">Engine</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground font-medium">Provider</label>
                <select
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  className="w-full bg-background border border-border rounded-lg outline-none focus:border-white/30 px-3 py-2 text-sm text-foreground appearance-none"
                >
                  {Object.entries(PROVIDERS).map(([key, data]) => (
                    <option key={key} value={key}>{data.name}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground font-medium">Model</label>
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  className="w-full bg-background border border-border rounded-lg outline-none focus:border-white/30 px-3 py-2 text-sm text-foreground appearance-none"
                >
                  {PROVIDERS[provider].models.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* API Key */}
            {PROVIDERS[provider].requiresKey && (
              <div className="mt-4 space-y-1.5">
                <label className="text-xs text-muted-foreground font-medium flex items-center gap-1.5">
                  <Key className="w-3.5 h-3.5" /> API Key
                </label>
                <Input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-..."
                  className="bg-background border-border text-sm font-mono"
                />
              </div>
            )}
          </div>

          {/* Use Case */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Target className="w-4 h-4 text-muted-foreground" />
              <span className="label-meta">Use Case Template</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {USE_CASES.map((uc) => {
                const isSelected = useCase === uc.id;
                return (
                  <button
                    key={uc.id}
                    onClick={() => setUseCase(uc.id)}
                    className={`
                      px-4 py-2 rounded-full text-xs font-semibold uppercase tracking-wider transition-all border
                      ${isSelected ? 'border-[hsl(var(--data-blue))] bg-[hsl(var(--data-blue))]/10 text-[hsl(var(--data-blue))]' : 'border-white/10 hover:bg-white/5 text-muted-foreground'}
                    `}
                  >
                    {uc.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Footer / CTA */}
        <div className="p-6 border-t border-border bg-[#050505]">
          <Button
            onClick={handleLaunch}
            className="w-full bg-[hsl(var(--data-blue))] hover:bg-[hsl(210,100%,50%)] text-white font-medium h-12 text-sm border-0"
          >
            Launch Simulation Environment <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
        
      </div>
    </div>
  );
}
