import { useEffect, useState } from "react";
import { ArrowRight, Globe, ServerCog, Target, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useApp } from "@/contexts/AppContext";
import {
  createV2Session,
  getV2Countries,
  normalizeUseCaseId,
  type ModelProviderId,
  type V2CountryResponse,
} from "@/lib/console-api";

type CountryCard = {
  available: boolean;
  emoji: string;
  id: string;
  name: string;
};

const HOSTED_PROVIDER: ModelProviderId = "google";
const HOSTED_MODEL = "gemini-2.5-flash-lite";

const FALLBACK_COUNTRIES: CountryCard[] = [
  { id: "singapore", name: "Singapore", emoji: "🇸🇬", available: true },
  { id: "usa", name: "USA", emoji: "🇺🇸", available: true },
  { id: "india", name: "India", emoji: "🇮🇳", available: false },
  { id: "japan", name: "Japan", emoji: "🇯🇵", available: false },
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

function buildCountryCatalog(countries: V2CountryResponse[]) {
  const catalogById = new Map<string, CountryCard>();

  for (const country of countries) {
    const id = toCountryId(country.code, country.name);
    if (!id) {
      continue;
    }

    catalogById.set(id, {
      available: Boolean(country.available && country.dataset_ready !== false),
      emoji: country.flag_emoji,
      id,
      name: country.name,
    });
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
  const [country, setCountry] = useState(() => resolveInitialCountry(app.country || "singapore", FALLBACK_COUNTRIES));
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
  }, [app.country, app.useCase, countries, isOpen]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    let cancelled = false;

    void getV2Countries()
      .then((payload) => {
        if (!cancelled && payload.length > 0) {
          setCountries(buildCountryCatalog(payload));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setCountries(FALLBACK_COUNTRIES);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  async function handleLaunch() {
    const selectedCountry = countries.find((entry) => entry.id === country);
    const resolvedUseCase = normalizeUseCaseId(useCase);

    if (!selectedCountry?.available) {
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
                      if (!entry.available) {
                        setLaunchError("Coming soon");
                        return;
                      }

                      setLaunchError("");
                      setCountry(entry.id);
                    }}
                    title={entry.available ? undefined : "Coming soon"}
                    className={`
                      relative flex flex-col items-center justify-center gap-2 rounded-xl border p-4 transition-all
                      ${entry.available ? "cursor-pointer hover:bg-muted/50" : "cursor-not-allowed opacity-40 hover:bg-muted/50"}
                      ${selected ? "border-[hsl(var(--data-blue))] bg-[hsl(var(--data-blue))]/10" : "border-border bg-transparent"}
                    `}
                  >
                    {!entry.available ? (
                      <span className="absolute -top-2 rounded bg-muted px-1.5 py-0.5 font-mono text-[8px] uppercase tracking-wider text-muted-foreground">
                        Coming Soon
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
          <Button onClick={() => void handleLaunch()} disabled={launching} className="h-12 w-full">
            {launching ? "Launching..." : "Launch Simulation Environment"}
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
          {launchError ? <p className="mt-2 text-xs text-destructive">{launchError}</p> : null}
        </div>
      </div>
    </div>
  );
}
