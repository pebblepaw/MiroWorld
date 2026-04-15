import { useEffect, useCallback, useRef, useState, type ChangeEvent } from 'react';
import { ArrowRight, Cpu, Download, Globe, Key, Loader2, Target, X } from 'lucide-react';

import { useApp } from '@/contexts/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  createV2Session,
  displayProviderId,
  displayUseCaseId,
  downloadCountryDataset,
  getCountryDownloadStatus,
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
  datasetReady: boolean;
  downloadRequired: boolean;
  downloadStatus: "ready" | "missing" | "downloading" | "error";
  downloadError: string | null;
  missingDependency: "huggingface_api_key" | null;
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
  { id: 'singapore', name: 'Singapore', emoji: '🇸🇬', available: true, datasetReady: true, downloadRequired: false, downloadStatus: 'ready', downloadError: null, missingDependency: null },
  { id: 'usa', name: 'USA', emoji: '🇺🇸', available: true, datasetReady: true, downloadRequired: false, downloadStatus: 'ready', downloadError: null, missingDependency: null },
  { id: 'india', name: 'India', emoji: '🇮🇳', available: false, datasetReady: false, downloadRequired: false, downloadStatus: 'missing', downloadError: null, missingDependency: null },
  { id: 'japan', name: 'Japan', emoji: '🇯🇵', available: false, datasetReady: false, downloadRequired: false, downloadStatus: 'missing', downloadError: null, missingDependency: null },
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

function buildCountryCatalog(countries: Array<{ code: string; name: string; flag_emoji: string; available: boolean; dataset_ready?: boolean; download_required?: boolean; download_status?: string; download_error?: string | null; missing_dependency?: string | null }>) {
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
      datasetReady: country.dataset_ready ?? country.available,
      downloadRequired: country.download_required ?? false,
      downloadStatus: (country.download_status as CountryCard['downloadStatus']) ?? (country.available ? 'ready' : 'missing'),
      downloadError: country.download_error ?? null,
      missingDependency: (country.missing_dependency as CountryCard['missingDependency']) ?? null,
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

function pickPreferredLiveProvider(providers: Record<string, ProviderCard>) {
  for (const providerId of ['gemini', 'openrouter', 'openai']) {
    const provider = providers[providerId];
    if (provider && !provider.requiresKey && provider.models.length > 0) {
      return providerId;
    }
  }
  return null;
}

export function OnboardingModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const app = useApp();
  const liveMode = isLiveBootMode();
  const missingHuggingFaceMessage = liveMode
    ? 'Country downloads are temporarily unavailable because the server is missing its Hugging Face credential.'
    : 'Add HUGGINGFACE_API_KEY to the root .env file, then restart the backend.';

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
  const [downloading, setDownloading] = useState(false);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const selectedCountryCard = countries.find((c) => c.id === country);
  const countryDatasetReady = selectedCountryCard?.datasetReady ?? true;
  const countryDownloadRequired = selectedCountryCard?.downloadRequired ?? false;
  const countryDownloading = selectedCountryCard?.downloadStatus === 'downloading' || downloading;
  const countryMissingDep = selectedCountryCard?.missingDependency;

  const refreshCountryStatus = useCallback(async (countryId: string) => {
    try {
      const status = await getCountryDownloadStatus(countryId);
      setCountries((prev) =>
        prev.map((c) => {
          if (c.id !== toCountryId(status.code, status.name)) return c;
          return {
            ...c,
            datasetReady: status.dataset_ready,
            downloadRequired: status.download_required,
            downloadStatus: status.download_status,
            downloadError: status.download_error,
            missingDependency: status.missing_dependency,
          };
        }),
      );
      return status;
    } catch {
      return null;
    }
  }, []);

  const handleDownloadDataset = useCallback(async (countryId: string, missingDependency?: CountryCard['missingDependency']) => {
    if (!countryId || downloading) return;

    if (missingDependency === 'huggingface_api_key') {
      setLaunchError(missingHuggingFaceMessage);
      return;
    }

    setDownloading(true);
    setLaunchError('');

    try {
      await downloadCountryDataset(countryId);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to start dataset download.';
      if (message.includes('huggingface_api_key')) {
        setLaunchError(missingHuggingFaceMessage);
      } else {
        setLaunchError(message);
      }
      setDownloading(false);
      return;
    }

    // Poll for download completion
    const poll = async () => {
      const status = await refreshCountryStatus(countryId);
      if (!status) {
        pollRef.current = setTimeout(poll, 2000);
        return;
      }
      if (status.download_status === 'downloading') {
        pollRef.current = setTimeout(poll, 2000);
        return;
      }
      setDownloading(false);
      if (status.download_status === 'error') {
        setLaunchError(status.download_error || 'Dataset download failed.');
      }
    };
    pollRef.current = setTimeout(poll, 1500);
  }, [downloading, missingHuggingFaceMessage, refreshCountryStatus]);

  // Clean up polling on unmount or close
  useEffect(() => {
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, []);

  // Stop polling when modal closes
  useEffect(() => {
    if (!isOpen && pollRef.current) {
      clearTimeout(pollRef.current);
      pollRef.current = null;
      setDownloading(false);
    }
  }, [isOpen]);

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

  useEffect(() => {
    if (!isOpen || !liveMode) {
      return;
    }

    const preferredProvider = pickPreferredLiveProvider(providers);
    if (!preferredProvider || preferredProvider === provider) {
      return;
    }

    const currentProvider = providers[provider];
    const shouldSwitchProvider =
      provider === 'ollama' ||
      !currentProvider ||
      (currentProvider.requiresKey && !apiKey.trim());

    if (!shouldSwitchProvider) {
      return;
    }

    setProvider(preferredProvider);
    setModel(pickProviderModel(preferredProvider, providers[preferredProvider].models, app.modelName));
    setApiKey('');
    setLaunchError('');
  }, [apiKey, app.modelName, isOpen, liveMode, provider, providers]);

  if (!isOpen) return null;

  const handleLaunch = async () => {
    const resolvedProvider = normalizeProviderId(provider);
    const resolvedUseCase = normalizeUseCaseId(useCase);
    const providerCard = providers[provider] ?? (liveMode ? undefined : FALLBACK_PROVIDERS[provider] ?? FALLBACK_PROVIDERS.gemini);
    const resolvedCountry = country || 'singapore';

    if (liveMode && !countryDatasetReady) {
      setLaunchError('Country dataset must be downloaded before launching.');
      return;
    }

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
      if (message.includes('country_dataset_missing') || message.includes('country_dataset_invalid')) {
        setLaunchError('Country dataset is not available. Please download it first.');
        // Refresh country status in case it changed
        void refreshCountryStatus(resolvedCountry);
      } else if (message.includes('huggingface_api_key_missing')) {
        setLaunchError(missingHuggingFaceMessage);
      } else {
        setLaunchError(message);
      }
    }
  };

  const selectedProvider = providers[provider] ?? (!liveMode ? FALLBACK_PROVIDERS[provider] ?? FALLBACK_PROVIDERS.gemini : undefined);

  return (
    <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="surface-card w-full max-w-2xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
        <div className="p-6 border-b border-border text-center relative">
          <button
            type="button"
            onClick={onClose}
            className="absolute top-4 right-4 text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-muted border border-border mb-4">
            <Globe className="w-6 h-6 text-foreground" />
          </div>
          <h2 className="text-2xl font-semibold text-foreground tracking-tight">Configure your simulation environment</h2>
          <p className="text-sm text-muted-foreground mt-1">Select country, provider, model, and use case to spin up a new session.</p>
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
                const needsDownload = liveMode && c.available && !c.datasetReady;
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
                      if (liveMode && !c.datasetReady && c.downloadStatus !== 'downloading') {
                        void handleDownloadDataset(c.id, c.missingDependency);
                      }
                    }}
                    title={!c.available ? 'Coming soon' : needsDownload ? 'Dataset download required' : undefined}
                    className={`
                      relative p-4 rounded-xl border flex flex-col items-center justify-center gap-2 transition-all
                      ${c.available ? 'cursor-pointer hover:bg-muted/50' : 'cursor-not-allowed opacity-40 hover:bg-muted/50'}
                      ${isSelected ? 'border-[hsl(var(--data-blue))] bg-[hsl(var(--data-blue))]/10' : 'border-border bg-transparent'}
                    `}
                  >
                    {!c.available && (
                      <span className="absolute -top-2 text-[8px] uppercase tracking-wider font-mono bg-muted text-muted-foreground px-1.5 py-0.5 rounded">
                        Coming Soon
                      </span>
                    )}
                    {c.available && !c.datasetReady && liveMode && (
                      <span className="absolute -top-2 text-[8px] uppercase tracking-wider font-mono bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300 px-1.5 py-0.5 rounded">
                        {c.downloadStatus === 'downloading' ? 'Downloading…' : 'Needs Download'}
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

            {/* Dataset download prompt for selected country */}
            {liveMode && selectedCountryCard?.available && !countryDatasetReady && (
              <div className="mt-4 p-4 rounded-xl border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/30">
                {countryMissingDep === 'huggingface_api_key' ? (
                  <p className="text-sm text-amber-800 dark:text-amber-200">
                    <strong>Missing API Key:</strong> {missingHuggingFaceMessage}
                  </p>
                ) : (
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
                        {countryDownloading
                          ? `Downloading ${selectedCountryCard.name} dataset…`
                          : selectedCountryCard.downloadError
                            ? 'Download failed'
                            : `${selectedCountryCard.name} dataset is required`}
                      </p>
                      {selectedCountryCard.downloadError && (
                        <p className="text-xs text-destructive mt-1">{selectedCountryCard.downloadError}</p>
                      )}
                      {!countryDownloading && !selectedCountryCard.downloadError && (
                        <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">
                          Download the country dataset to enable simulation.
                        </p>
                      )}
                    </div>
                    {countryDownloading ? (
                      <div className="flex items-center gap-2 shrink-0">
                        <Loader2 className="w-4 h-4 animate-spin text-amber-600 dark:text-amber-400" />
                        <span className="text-xs text-amber-600 dark:text-amber-400 font-medium">Downloading…</span>
                      </div>
                    ) : (
                      <Button
                        onClick={() => void handleDownloadDataset(country, countryMissingDep)}
                        variant="outline"
                        size="sm"
                        className="shrink-0 border-amber-400 dark:border-amber-600 text-amber-800 dark:text-amber-200 hover:bg-amber-100 dark:hover:bg-amber-900/50"
                      >
                        <Download className="w-3.5 h-3.5 mr-1.5" />
                        {selectedCountryCard.downloadError ? 'Retry' : 'Download'}
                      </Button>
                    )}
                  </div>
                )}
              </div>
            )}
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
                  onChange={(event: ChangeEvent<HTMLInputElement>) => setApiKey(event.target.value)}
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
                      ${isSelected ? 'border-[hsl(var(--data-blue))] bg-[hsl(var(--data-blue))]/10 text-[hsl(var(--data-blue))]' : 'border-border hover:bg-muted/50 text-muted-foreground'}
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

        <div className="p-6 border-t border-border bg-card">
          <Button
            onClick={() => void handleLaunch()}
            disabled={liveMode && !countryDatasetReady}
            className={`w-full font-medium h-12 text-sm border-0 ${
              liveMode && !countryDatasetReady
                ? 'bg-muted text-muted-foreground cursor-not-allowed'
                : 'bg-[hsl(var(--data-blue))] hover:bg-[hsl(210,100%,50%)] text-white'
            }`}
          >
            Launch Simulation Environment <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
          {liveMode && !countryDatasetReady && !launchError && (
            <p className="mt-2 text-xs text-muted-foreground text-center">Download the country dataset above to enable launch.</p>
          )}
          {launchError && <p className="mt-2 text-xs text-destructive">{launchError}</p>}
        </div>
      </div>
    </div>
  );
}
