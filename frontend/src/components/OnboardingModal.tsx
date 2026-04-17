import { useEffect, useState } from "react";
import { ArrowRight, Globe, ServerCog, Target, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useApp } from "@/contexts/AppContext";
import {
  createV2Session,
  downloadCountryDataset,
  getCountryDownloadStatus,
  getV2Countries,
  normalizeUseCaseId,
  type ModelProviderId,
  type V2CountryResponse,
} from "@/lib/console-api";

type CountryCard = {
  available: boolean;
  downloadError: string | null;
  downloadRequired: boolean;
  downloadStatus: V2CountryResponse["download_status"];
  emoji: string;
  id: string;
  launchReady: boolean;
  missingDependency: V2CountryResponse["missing_dependency"];
  name: string;
};

const HOSTED_PROVIDER: ModelProviderId = "google";
const HOSTED_MODEL = "gemini-2.5-flash-lite";

const FALLBACK_COUNTRIES: CountryCard[] = [
  {
    id: "singapore",
    name: "Singapore",
    emoji: "🇸🇬",
    available: true,
    launchReady: true,
    downloadRequired: false,
    downloadStatus: "ready",
    downloadError: null,
    missingDependency: null,
  },
  {
    id: "usa",
    name: "USA",
    emoji: "🇺🇸",
    available: true,
    launchReady: true,
    downloadRequired: false,
    downloadStatus: "ready",
    downloadError: null,
    missingDependency: null,
  },
  {
    id: "india",
    name: "India",
    emoji: "🇮🇳",
    available: false,
    launchReady: false,
    downloadRequired: false,
    downloadStatus: "missing",
    downloadError: null,
    missingDependency: null,
  },
  {
    id: "japan",
    name: "Japan",
    emoji: "🇯🇵",
    available: false,
    launchReady: false,
    downloadRequired: false,
    downloadStatus: "missing",
    downloadError: null,
    missingDependency: null,
  },
];

const USE_CASES = [
  { id: "public-policy-testing", label: "Public Policy Testing", icon: "🏛️" },
  { id: "product-market-research", label: "Product & Market Research", icon: "📦" },
];

function toCountryId(code: string, name: string) {
  const normalizedCode = String(code || "").trim().toLowerCase();
  const normalizedName = String(name || "").trim().toLowerCase();

  if (normalizedCode === "sg" || normalizedName === "singapore") {
    return "singapore";
  }

  if (normalizedCode === "us" || normalizedCode === "usa" || normalizedName === "usa") {
    return "usa";
  }

  return normalizedCode || normalizedName;
}

function toCountryCard(country: V2CountryResponse): CountryCard | null {
  const id = toCountryId(country.code, country.name);
  if (!id) {
    return null;
  }

  return {
    available: Boolean(country.available),
    downloadError: country.download_error,
    downloadRequired: Boolean(country.download_required),
    downloadStatus: country.download_status,
    emoji: country.flag_emoji,
    id,
    launchReady: Boolean(country.available && country.dataset_ready !== false),
    missingDependency: country.missing_dependency,
    name: country.name,
  };
}

function buildCountryCatalog(countries: V2CountryResponse[]) {
  const catalogById = new Map<string, CountryCard>();

  for (const country of countries) {
    const entry = toCountryCard(country);
    if (!entry) {
      continue;
    }

    catalogById.set(entry.id, entry);
  }

  const merged = FALLBACK_COUNTRIES.map((country) => catalogById.get(country.id) ?? country);
  for (const [id, country] of catalogById.entries()) {
    if (!merged.some((entry) => entry.id === id)) {
      merged.push(country);
    }
  }

  return merged;
}

function resolveInitialCountry(countryId: string, countries: CountryCard[]) {
  const requested = countries.find((country) => country.id === countryId && country.available);
  if (requested) {
    return requested.id;
  }

  return countries.find((country) => country.available)?.id ?? FALLBACK_COUNTRIES[0].id;
}

export function OnboardingModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const app = useApp();
  const [countries, setCountries] = useState<CountryCard[]>(FALLBACK_COUNTRIES);
  const [countriesLoaded, setCountriesLoaded] = useState(false);
  const [country, setCountry] = useState(() => resolveInitialCountry(app.country || "singapore", FALLBACK_COUNTRIES));
  const [downloadingCountryId, setDownloadingCountryId] = useState<string | null>(null);
  const [useCase, setUseCase] = useState(() => normalizeUseCaseId(app.useCase || "public-policy-testing"));
  const [launchError, setLaunchError] = useState("");
  const [launching, setLaunching] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    setCountry(resolveInitialCountry(app.country || "singapore", countries));
    setUseCase(normalizeUseCaseId(app.useCase || "public-policy-testing"));
    setLaunchError("");
  }, [app.country, app.useCase, isOpen]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    setCountry((current) => {
      if (countries.some((entry) => entry.id === current)) {
        return current;
      }
      return resolveInitialCountry(app.country || "singapore", countries);
    });
  }, [app.country, countries, isOpen]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    let cancelled = false;
    setCountriesLoaded(false);

    void getV2Countries()
      .then((payload) => {
        if (!cancelled && payload.length > 0) {
          setCountries(buildCountryCatalog(payload));
        }
        if (!cancelled) {
          setCountriesLoaded(true);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setCountries(FALLBACK_COUNTRIES);
          setCountriesLoaded(true);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [isOpen]);

  useEffect(() => {
    if (!downloadingCountryId) {
      return;
    }

    let cancelled = false;
    let timer: number | null = null;

    const poll = async () => {
      try {
        const payload = await getCountryDownloadStatus(downloadingCountryId);
        const nextCountry = toCountryCard(payload);

        if (cancelled || !nextCountry) {
          return;
        }

        setCountries((current) => current.map((entry) => (entry.id === nextCountry.id ? nextCountry : entry)));

        if (nextCountry.launchReady || nextCountry.downloadStatus === "error") {
          setDownloadingCountryId(null);
          if (nextCountry.downloadStatus === "error" && nextCountry.downloadError) {
            setLaunchError(nextCountry.downloadError);
          }
          return;
        }

        timer = window.setTimeout(() => {
          void poll();
        }, 1500);
      } catch (error) {
        if (!cancelled) {
          setDownloadingCountryId(null);
          setLaunchError(error instanceof Error ? error.message : "Failed to refresh hosted dataset status.");
        }
      }
    };

    void poll();

    return () => {
      cancelled = true;
      if (timer !== null) {
        window.clearTimeout(timer);
      }
    };
  }, [downloadingCountryId]);

  if (!isOpen) {
    return null;
  }

  const selectedCountry = countries.find((entry) => entry.id === country);
  const selectedCountryReady = Boolean(selectedCountry?.launchReady);
  const selectedCountryDownloading = downloadingCountryId === selectedCountry?.id || selectedCountry?.downloadStatus === "downloading";
  const launchDisabled = launching || !countriesLoaded || !selectedCountryReady;

  async function handleDownload() {
    if (!selectedCountry) {
      return;
    }

    setLaunchError("");

    try {
      await downloadCountryDataset(selectedCountry.id);
      setDownloadingCountryId(selectedCountry.id);
    } catch (error) {
      setLaunchError(error instanceof Error ? error.message : "Failed to start hosted dataset download.");
    }
  }

  async function handleLaunch() {
    const resolvedUseCase = normalizeUseCaseId(useCase);

    if (!selectedCountryReady || !selectedCountry?.available) {
      setLaunchError("Select an available hosted region before launching.");
      return;
    }

    setLaunching(true);
    setLaunchError("");

    try {
      const payload = await createV2Session({
        country: selectedCountry.id,
        mode: "live",
        model: HOSTED_MODEL,
        provider: HOSTED_PROVIDER,
        use_case: resolvedUseCase,
      });

      app.setCountry(selectedCountry.id);
      app.setUseCase(resolvedUseCase);
      app.setModelProvider(HOSTED_PROVIDER);
      app.setModelName(HOSTED_MODEL);
      app.setModelApiKey("");
      app.setModelBaseUrl("");
      app.setSessionId(payload.session_id);

      onClose();
    } catch (error) {
      setLaunchError(error instanceof Error ? error.message : "Failed to launch the hosted simulation environment.");
    } finally {
      setLaunching(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-sm">
      <div className="surface-card flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden shadow-2xl">
        <div className="relative border-b border-border p-6 text-center">
          <button
            type="button"
            onClick={onClose}
            className="absolute right-4 top-4 text-muted-foreground transition-colors hover:text-foreground"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
          <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-muted">
            <Globe className="h-6 w-6 text-foreground" />
          </div>
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">Configure your simulation environment</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Pick a hosted region and use case. The shared Gemini runtime is already provisioned for this branch.
          </p>
        </div>

        <div className="space-y-8 overflow-y-auto p-6 scrollbar-thin">
          <div>
            <div className="mb-3 flex items-center gap-2">
              <Globe className="h-4 w-4 text-muted-foreground" />
              <span className="label-meta">Region & Dataset</span>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {countries.map((entry) => {
                const selected = country === entry.id;

                return (
                  <button
                    key={entry.id}
                    type="button"
                    onClick={() => {
                      if (!entry.available && !entry.downloadRequired) {
                        setLaunchError("Coming soon");
                        return;
                      }

                      setLaunchError("");
                      setCountry(entry.id);
                    }}
                    title={entry.available ? undefined : "Coming soon"}
                    className={`
                      relative flex flex-col items-center justify-center gap-2 rounded-xl border p-4 transition-all
                      ${(entry.available || entry.downloadRequired) ? "cursor-pointer hover:bg-muted/50" : "cursor-not-allowed opacity-40 hover:bg-muted/50"}
                      ${selected ? "border-[hsl(var(--data-blue))] bg-[hsl(var(--data-blue))]/10" : "border-border bg-transparent"}
                    `}
                  >
                    {!entry.available && !entry.downloadRequired ? (
                      <span className="absolute -top-2 rounded bg-muted px-1.5 py-0.5 font-mono text-[8px] uppercase tracking-wider text-muted-foreground">
                        Coming Soon
                      </span>
                    ) : null}
                    {entry.downloadRequired && !entry.launchReady ? (
                      <span className="absolute -top-2 rounded bg-muted px-1.5 py-0.5 font-mono text-[8px] uppercase tracking-wider text-muted-foreground">
                        {entry.downloadStatus === "downloading" ? "Downloading" : "Download Required"}
                      </span>
                    ) : null}
                    <span className="text-2xl">{entry.emoji}</span>
                    <span className={`text-xs font-medium ${selected ? "text-[hsl(var(--data-blue))]" : "text-foreground"}`}>
                      {entry.name}
                    </span>
                  </button>
                );
              })}
            </div>
            {selectedCountry && !selectedCountryReady ? (
              <div className="mt-4 rounded-2xl border border-border bg-muted/30 p-4">
                <p className="text-sm font-semibold text-foreground">
                  {selectedCountry.downloadRequired ? "Hosted dataset download required" : "Hosted dataset unavailable"}
                </p>
                <p className="mt-2 text-sm text-muted-foreground">
                  {selectedCountry.downloadRequired
                    ? "Download the selected country dataset once, then launch the hosted simulation environment."
                    : "This hosted region is not ready yet."}
                </p>
                {selectedCountry.missingDependency ? (
                  <p className="mt-2 text-xs text-destructive">
                    Missing dependency: {selectedCountry.missingDependency.replace(/_/g, " ")}.
                  </p>
                ) : null}
                {selectedCountry.downloadError ? (
                  <p className="mt-2 text-xs text-destructive">{selectedCountry.downloadError}</p>
                ) : null}
                {selectedCountry.downloadRequired ? (
                  <Button
                    type="button"
                    variant="outline"
                    className="mt-4"
                    disabled={selectedCountryDownloading}
                    onClick={() => void handleDownload()}
                  >
                    {selectedCountryDownloading ? "Downloading dataset..." : `Download ${selectedCountry.name} dataset`}
                  </Button>
                ) : null}
              </div>
            ) : null}
          </div>

          <div>
            <div className="mb-3 flex items-center gap-2">
              <ServerCog className="h-4 w-4 text-muted-foreground" />
              <span className="label-meta">Hosted Runtime</span>
            </div>
            <div className="rounded-2xl border border-border bg-muted/30 p-5">
              <p className="text-sm font-semibold text-foreground">Shared Gemini runtime</p>
              <p className="mt-2 text-sm text-muted-foreground">
                This hosted build launches every session on {HOSTED_MODEL}. Provider, model, and personal API-key setup are
                intentionally hidden on this branch.
              </p>
            </div>
          </div>

          <div>
            <div className="mb-3 flex items-center gap-2">
              <Target className="h-4 w-4 text-muted-foreground" />
              <span className="label-meta">Use Case Template</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {USE_CASES.map((entry) => {
                const selected = useCase === entry.id;

                return (
                  <button
                    key={entry.id}
                    type="button"
                    onClick={() => setUseCase(entry.id)}
                    className={`
                      flex items-center gap-1.5 rounded-full border px-4 py-2 text-xs font-semibold tracking-wider transition-all
                      ${selected
                        ? "border-[hsl(var(--data-blue))] bg-[hsl(var(--data-blue))]/10 text-[hsl(var(--data-blue))]"
                        : "border-border text-muted-foreground hover:bg-muted/50"}
                    `}
                  >
                    <span>{entry.icon}</span>
                    {entry.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <div className="border-t border-border bg-card p-6">
          <Button onClick={() => void handleLaunch()} disabled={launchDisabled} className="h-12 w-full">
            {launching ? "Launching..." : "Launch Simulation Environment"}
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
          {launchError ? <p className="mt-2 text-xs text-destructive">{launchError}</p> : null}
        </div>
      </div>
    </div>
  );
}
