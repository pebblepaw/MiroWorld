import pricingYaml from "../../../config/llm_pricing.yaml?raw";

type PricingEntry = {
  input: number;
  output: number;
  cachedInput: number | null;
};

type PricingCatalog = {
  lastUpdated: string;
  models: Record<string, PricingEntry>;
};

function parseYamlScalar(rawValue: string): number | null {
  const trimmed = rawValue.trim();
  if (trimmed === "null") {
    return null;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : 0;
}

function parsePricingCatalog(raw: string): PricingCatalog {
  const catalog: PricingCatalog = {
    lastUpdated: "",
    models: {},
  };
  let currentModel: string | null = null;

  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }

    const lastUpdatedMatch = /^last_updated:\s*"?(.*?)"?$/.exec(trimmed);
    if (lastUpdatedMatch) {
      catalog.lastUpdated = lastUpdatedMatch[1] ?? "";
      continue;
    }

    const modelMatch = /^ {2}([A-Za-z0-9_.:-]+):\s*$/.exec(line);
    if (modelMatch) {
      currentModel = modelMatch[1];
      catalog.models[currentModel] = { input: 0, output: 0, cachedInput: null };
      continue;
    }

    if (!currentModel) {
      continue;
    }

    const valueMatch = /^ {4}(input|output|cached_input):\s*(.+)$/.exec(line);
    if (!valueMatch) {
      continue;
    }

    const [, key, rawValue] = valueMatch;
    const parsed = parseYamlScalar(rawValue);
    if (key === "cached_input") {
      catalog.models[currentModel].cachedInput = parsed;
    } else if (key === "input") {
      catalog.models[currentModel].input = parsed ?? 0;
    } else if (key === "output") {
      catalog.models[currentModel].output = parsed ?? 0;
    }
  }

  return catalog;
}

const STATIC_PRICING = parsePricingCatalog(pricingYaml);

function resolvePricingModel(modelName: string, provider: string): PricingEntry {
  const normalizedModel = String(modelName || "").trim();
  const normalizedProvider = String(provider || "").trim().toLowerCase();
  if (normalizedModel && STATIC_PRICING.models[normalizedModel]) {
    return STATIC_PRICING.models[normalizedModel];
  }
  if (normalizedProvider === "openai") {
    return STATIC_PRICING.models["gpt-4o-mini"] ?? { input: 0, output: 0, cachedInput: null };
  }
  if (normalizedProvider === "ollama") {
    return STATIC_PRICING.models["ollama"] ?? { input: 0, output: 0, cachedInput: 0 };
  }
  return STATIC_PRICING.models["gemini-2.0-flash"] ?? { input: 0, output: 0, cachedInput: null };
}

export function estimateStaticSimulationCostUsd(
  agentCount: number,
  rounds: number,
  provider: string,
  modelName: string,
): number {
  const pricing = resolvePricingModel(modelName, provider);
  const normalizedProvider = String(provider || "").trim().toLowerCase();
  if (normalizedProvider === "ollama" || (pricing.input === 0 && pricing.output === 0)) {
    return 0;
  }

  const totalCalls = Math.max(0, agentCount) * Math.max(1, rounds);
  const avgInput = 3000;
  const avgOutput = 500;
  const cachedRatio = pricing.cachedInput === null ? 0 : 0.6;

  const totalInput = totalCalls * avgInput;
  const totalOutput = totalCalls * avgOutput;
  const cachedTokens = Math.round(totalInput * cachedRatio);
  const nonCachedInput = totalInput - cachedTokens;

  const cachedInputRate = pricing.cachedInput ?? pricing.input;
  return (
    (nonCachedInput / 1_000_000) * pricing.input +
    (cachedTokens / 1_000_000) * cachedInputRate +
    (totalOutput / 1_000_000) * pricing.output
  );
}

export function pricingCatalogLastUpdated(): string {
  return STATIC_PRICING.lastUpdated;
}
