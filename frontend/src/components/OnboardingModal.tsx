import { useEffect, useState } from 'react';
import { ArrowRight, Cpu, Globe, Key, Target } from 'lucide-react';

import { useApp } from '@/contexts/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  createV2Session,
  displayProviderId,
  displayUseCaseId,
  getV2Countries,
  getV2Providers,
  isLiveBootMode,
  normalizeProviderId,
  normalizeUseCaseId,
} from '@/lib/console-api';

type CountryCard = {
  id: string;
  name: string;
  emoji: string;
  available: boolean;
};

type ProviderCard = {
  label: string;
  models: string[];
  requiresKey: boolean;
};

const RETIRED_PROVIDER_MODELS: Record<string, Set<string>> = {
  gemini: new Set(["gemini-2.0-flash-lite", "gemini-2.0-flash-lite-001"]),
};

const PREFERRED_PROVIDER_MODELS: Record<string, string[]> = {
  gemini: [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-2.5-pro",
  ],
};

const FALLBACK_COUNTRIES: CountryCard[] = [
  { id: 'singapore', name: 'Singapore', emoji: '🇸🇬', available: true },
  { id: 'usa', name: 'USA', emoji: '🇺🇸', available: true },
  { id: 'india', name: 'India', emoji: '🇮🇳', available: false },
  { id: 'japan', name: 'Japan', emoji: '🇯🇵', available: false },
];

const FALLBACK_PROVIDERS: Record<string, ProviderCard> = {
  gemini: {
    label: 'Google Gemini',
    models: ['gemini-2.5-flash-lite', 'gemini-2.5-flash', 'gemini-flash-lite-latest'],
    requiresKey: true,
  },
  openai: {
    label: 'OpenAI',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'],
    requiresKey: true,
  },
  ollama: {
    label: 'Ollama (Local)',
    models: ['qwen3:4b-instruct-2507-q4_K_M', 'llama3:8b'],
    requiresKey: false,
  },
};

const USE_CASES = [
  { id: 'public-policy-testing', label: 'Public Policy Testing', icon: '🏛️' },
  { id: 'product-market-research', label: 'Product & Market Research', icon: '📦' },
];

function toCountryId(code: string, name: string) {
  const normalizedCode = String(code || '').trim().toLowerCase();
  const normalizedName = String(name || '').trim().toLowerCase();
  if (normalizedCode === 'sg' || normalizedName === 'singapore') {
    return 'singapore';
  }
  if (normalizedCode === 'us' || normalizedName === 'usa') {
    return 'usa';
  }
  return normalizedCode || normalizedName;
}

function toDisplayCountry(country: string) {
  return toCountryId(country, country);
}

function toDisplayUseCase(useCase: string) {
  return displayUseCaseId(useCase) || 'public-policy-testing';
}

function buildCountryCatalog(countries: Array<{ code: string; name: string; flag_emoji: string; available: boolean }>) {
  const catalogById = new Map<string, CountryCard>();

  for (const country of countries) {
    const id = toCountryId(country.code, country.name);
    if (!id) {
      continue;
    }

    catalogById.set(id, {
      id,
      name: country.name,
      emoji: country.flag_emoji,
      available: country.available,
    });
  }

  const merged = FALLBACK_COUNTRIES.map((fallback) => catalogById.get(fallback.id) ?? fallback);
  for (const [id, country] of catalogById.entries()) {
    if (!merged.some((item) => item.id === id)) {
      merged.push(country);
    }
  }

  return merged;
}

function buildProviderCatalog(providers: Array<{ name: string; models: string[]; requires_api_key: boolean }>) {
  const catalog: Record<string, ProviderCard> = {};
  for (const provider of providers) {
    const id = String(provider.name || '').trim().toLowerCase();
    if (!id) {
      continue;
    }
    catalog[id] = {
      label:
        id === 'gemini'
          ? 'Google Gemini'
          : id === 'openai'
            ? 'OpenAI'
            : id === 'ollama'
              ? 'Ollama (Local)'
              : provider.name,
      models: curateProviderModels(id, provider.models.length > 0 ? provider.models : FALLBACK_PROVIDERS[id]?.models ?? []),
      requiresKey: Boolean(provider.requires_api_key),
    };
  }
  return Object.keys(catalog).length > 0 ? catalog : FALLBACK_PROVIDERS;
}

function curateProviderModels(providerId: string, models: string[]) {
  const blocked = RETIRED_PROVIDER_MODELS[providerId] ?? new Set<string>();
  const deduped: string[] = [];
  const seen = new Set<string>();

  for (const model of models) {
    const candidate = String(model || '').trim();
    if (!candidate || blocked.has(candidate)) {
      continue;
    }
    if (seen.has(candidate)) {
      continue;
    }
    seen.add(candidate);
    deduped.push(candidate);
  }

  const preferredOrder = PREFERRED_PROVIDER_MODELS[providerId];
  if (!preferredOrder || preferredOrder.length === 0) {
    return deduped;
  }

  const rank = new Map(preferredOrder.map((model, index) => [model, index]));
  return [...deduped].sort((left, right) => {
    const leftRank = rank.get(left);
    const rightRank = rank.get(right);
    if (leftRank !== undefined || rightRank !== undefined) {
      return (leftRank ?? Number.MAX_SAFE_INTEGER) - (rightRank ?? Number.MAX_SAFE_INTEGER);
    }
    return left.localeCompare(right);
  });
}

function pickProviderModel(providerId: string, models: string[], currentModel?: string) {
  const curated = curateProviderModels(providerId, models);
  const candidate = String(currentModel || '').trim();
  const blocked = RETIRED_PROVIDER_MODELS[providerId] ?? new Set<string>();
  if (candidate && curated.includes(candidate) && !blocked.has(candidate)) {
    return candidate;
  }
  return curated[0] ?? candidate;
}

export function OnboardingModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const app = useApp();
  const liveMode = isLiveBootMode();

  const [countries, setCountries] = useState<CountryCard[]>(FALLBACK_COUNTRIES);
  const [providers, setProviders] = useState<Record<string, ProviderCard>>(liveMode ? {} : FALLBACK_PROVIDERS);
  const [country, setCountry] = useState(() => toDisplayCountry(app.country || 'singapore'));
  const [provider, setProvider] = useState(() => displayProviderId(app.modelProvider) || 'gemini');
  const [model, setModel] = useState(() => {
    const initialProvider = displayProviderId(app.modelProvider) || 'gemini';
    return pickProviderModel(initialProvider, FALLBACK_PROVIDERS[initialProvider]?.models ?? FALLBACK_PROVIDERS.gemini.models, app.modelName);
  });
  const [apiKey, setApiKey] = useState(() => app.modelApiKey || '');
  const [useCase, setUseCase] = useState(() => toDisplayUseCase(app.useCase || 'public-policy-testing'));
  const [launchError, setLaunchError] = useState('');

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    setCountry(toDisplayCountry(app.country || 'singapore'));
    setProvider(displayProviderId(app.modelProvider) || 'gemini');
    const nextProvider = displayProviderId(app.modelProvider) || 'gemini';
    setModel(
      pickProviderModel(
        nextProvider,
        providers[nextProvider]?.models ?? FALLBACK_PROVIDERS[nextProvider]?.models ?? FALLBACK_PROVIDERS.gemini.models,
        app.modelName,
      ),
    );
    setApiKey(app.modelApiKey || '');
    setUseCase(toDisplayUseCase(app.useCase || 'public-policy-testing'));
  }, [app.country, app.modelApiKey, app.modelName, app.modelProvider, app.useCase, isOpen, providers]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    let cancelled = false;
    const loadCatalogs = async () => {
      try {
        const payload = await getV2Countries();
        if (!cancelled && payload.length > 0) {
          setCountries(buildCountryCatalog(payload));
        } else if (!cancelled && !liveMode) {
          setCountries(FALLBACK_COUNTRIES);
        }
      } catch {
        if (!cancelled && !liveMode) {
          setCountries(FALLBACK_COUNTRIES);
        }
      }

      try {
        const payload = await getV2Providers();
        if (!cancelled && payload.length > 0) {
          setProviders(buildProviderCatalog(payload));
        } else if (!cancelled && liveMode) {
          setProviders({});
          setLaunchError('Live provider catalog returned no options.');
        }
      } catch {
        if (liveMode) {
          setProviders({});
          setLaunchError('Live provider catalog is unavailable.');
        }
      }
    };

    void loadCatalogs();
    return () => {
      cancelled = true;
    };
  }, [isOpen]);

  useEffect(() => {
    const providerCard = providers[provider];
    if (!providerCard || providerCard.models.length === 0) {
      return;
    }

    const nextModel = pickProviderModel(provider, providerCard.models, model);
    if (nextModel && nextModel !== model) {
      setModel(nextModel);
    }
  }, [model, provider, providers]);

  if (!isOpen) return null;

  const handleLaunch = async () => {
    const resolvedProvider = normalizeProviderId(provider);
    const resolvedUseCase = normalizeUseCaseId(useCase);
    const providerCard = providers[provider] ?? (liveMode ? undefined : FALLBACK_PROVIDERS[provider] ?? FALLBACK_PROVIDERS.gemini);
    const resolvedCountry = country || 'singapore';

    if (!providerCard || providerCard.models.length === 0) {
      setLaunchError('Select a provider and model before launching.');
      return;
    }
    const resolvedModel = model || providerCard.models[0];
    const resolvedApiKey = providerCard.requiresKey ? apiKey : '';
    if (providerCard.requiresKey && !resolvedApiKey.trim()) {
      setLaunchError('API key is required for this provider.');
      return;
    }
    if (!resolvedCountry || !resolvedModel) {
      setLaunchError('Country and model are required.');
      return;
    }

    try {
      const payload = await createV2Session({
        country: resolvedCountry,
        provider: resolvedProvider,
        model: resolvedModel,
        api_key: resolvedApiKey || undefined,
        use_case: resolvedUseCase,
      });

      app.setCountry(resolvedCountry);
      app.setModelProvider(resolvedProvider as any);
      app.setModelName(resolvedModel);
      app.setModelApiKey(resolvedApiKey);
      app.setUseCase(resolvedUseCase);
      app.setSessionId(payload.session_id);
      setLaunchError('');
      onClose();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to launch simulation environment.';
      setLaunchError(message);
    }
  };

  const selectedProvider = providers[provider] ?? (!liveMode ? FALLBACK_PROVIDERS[provider] ?? FALLBACK_PROVIDERS.gemini : undefined);

  return (
    <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="surface-card w-full max-w-2xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
        <div className="p-6 border-b border-border text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-white/5 border border-white/10 mb-4">
            <Globe className="w-6 h-6 text-foreground" />
          </div>
          <h2 className="text-2xl font-semibold text-foreground tracking-tight">Configure your simulation environment</h2>
          <p className="text-sm text-muted-foreground mt-1">Select country, provider, model, and use case to spin up a new V2 session.</p>
        </div>

        <div className="p-6 overflow-y-auto scrollbar-thin space-y-8">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Globe className="w-4 h-4 text-muted-foreground" />
              <span className="label-meta">Region & Dataset</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {countries.map((c) => {
                const isSelected = country === c.id;
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => {
                      if (!c.available) {
                        setLaunchError('Coming soon');
                        return;
                      }

                      setLaunchError('');
                      setCountry(c.id);
                    }}
                    title={!c.available ? 'Coming soon' : undefined}
                    className={`
                      relative p-4 rounded-xl border flex flex-col items-center justify-center gap-2 transition-all
                      ${c.available ? 'cursor-pointer hover:bg-white/5' : 'cursor-not-allowed opacity-40 hover:bg-white/5'}
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
                  {Object.entries(providers).map(([key, data]) => (
                    <option key={key} value={key}>
                      {data.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground font-medium">Model</label>
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  disabled={!selectedProvider || selectedProvider.models.length === 0}
                  className="w-full bg-background border border-border rounded-lg outline-none focus:border-white/30 px-3 py-2 text-sm text-foreground appearance-none"
                >
                  {(selectedProvider?.models ?? []).map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {selectedProvider?.requiresKey && (
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
                      px-4 py-2 rounded-full text-xs font-semibold tracking-wider transition-all border flex items-center gap-1.5
                      ${isSelected ? 'border-[hsl(var(--data-blue))] bg-[hsl(var(--data-blue))]/10 text-[hsl(var(--data-blue))]' : 'border-white/10 hover:bg-white/5 text-muted-foreground'}
                    `}
                  >
                    <span>{uc.icon}</span>
                    {uc.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <div className="p-6 border-t border-border bg-[#050505]">
          <Button
            onClick={() => void handleLaunch()}
            className="w-full bg-[hsl(var(--data-blue))] hover:bg-[hsl(210,100%,50%)] text-white font-medium h-12 text-sm border-0"
          >
            Launch Simulation Environment <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
          {launchError && <p className="mt-2 text-xs text-destructive">{launchError}</p>}
        </div>
      </div>
    </div>
  );
}
