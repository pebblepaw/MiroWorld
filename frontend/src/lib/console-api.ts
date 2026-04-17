import type { SimPost } from "@/data/mockData";
import { getSupabaseAccessToken } from "@/lib/supabase-client";

export type ConsoleMode = "demo" | "live";
export type BootMode = "demo" | "demo-static" | "live";
export type ModelProviderId = "google" | "openrouter" | "openai" | "ollama";
export type V2ProviderId = "gemini" | "openai" | "ollama";

export interface ConsoleSessionModelConfigRequest {
  model_provider: ModelProviderId;
  model_name: string;
  embed_model_name?: string;
  api_key?: string;
  base_url?: string;
  analysis_questions?: Array<Record<string, unknown>>;
}

export interface ConsoleSessionModelConfigResponse {
  session_id: string;
  model_provider: ModelProviderId;
  model_name: string;
  embed_model_name: string;
  base_url: string;
  api_key_configured: boolean;
  api_key_masked?: string | null;
}

export interface ConsoleModelProvider {
  id: ModelProviderId;
  label: string;
  default_model: string;
  default_embed_model: string;
  default_base_url: string;
  requires_api_key: boolean;
}

export interface ConsoleModelProviderCatalogResponse {
  providers: ConsoleModelProvider[];
}

export interface ConsoleModelOption {
  id: string;
  label: string;
}

export interface ConsoleProviderModelsResponse {
  provider: ModelProviderId;
  models: ConsoleModelOption[];
}

export interface V2CountryResponse {
  name: string;
  code: string;
  flag_emoji: string;
  dataset_path: string;
  available: boolean;
  dataset_ready: boolean;
  download_required: boolean;
  download_status: "ready" | "missing" | "downloading" | "error";
  download_error: string | null;
  missing_dependency: "huggingface_api_key" | null;
}

export interface V2ProviderResponse {
  name: V2ProviderId;
  models: string[];
  requires_api_key: boolean;
}

export interface V2SessionCreateRequest {
  country: string;
  provider: V2ProviderId | ModelProviderId;
  model: string;
  api_key?: string;
  use_case: string;
  mode?: ConsoleMode;
  session_id?: string;
}

export interface V2SessionCreateResponse {
  session_id: string;
}

export interface V2SessionConfigResponse {
  session_id: string;
  country?: string | null;
  use_case?: string | null;
  provider?: ModelProviderId | V2ProviderId | null;
  model?: string | null;
  api_key_configured?: boolean;
  guiding_prompt?: string | null;
  analysis_questions?: Array<Record<string, unknown>>;
}

export interface ConsoleSessionResponse {
  session_id: string;
  mode: ConsoleMode;
  status: string;
  model_provider: ModelProviderId;
  model_name: string;
  embed_model_name: string;
  base_url: string;
  api_key_configured: boolean;
  api_key_masked?: string | null;
}

export interface KnowledgeNode {
  id: string;
  label: string;
  type: string;
  description?: string | null;
  summary?: string | null;
  weight?: number | null;
  families?: string[] | null;
  facet_kind?: string | null;
  canonical_key?: string | null;
  canonical_value?: string | null;
  display_bucket?: string | null;
  support_count?: number | null;
  degree_count?: number | null;
  importance_score?: number | null;
  source_ids?: string[] | null;
  file_paths?: string[] | null;
  generic_placeholder?: boolean | null;
  low_value_orphan?: boolean | null;
  ui_default_hidden?: boolean | null;
}

export interface KnowledgeEdge {
  source: string;
  target: string;
  type: string;
  label?: string | null;
  summary?: string | null;
  normalized_type?: string | null;
  raw_relation_text?: string | null;
  source_ids?: string[] | null;
  file_paths?: string[] | null;
}

export interface KnowledgeArtifact {
  session_id: string;
  document: {
    document_id: string;
    source_path?: string | null;
    file_name?: string | null;
    file_type?: string | null;
    text_length?: number | null;
    paragraph_count?: number | null;
  };
  summary: string;
  guiding_prompt?: string | null;
  entity_nodes: KnowledgeNode[];
  relationship_edges: KnowledgeEdge[];
  entity_type_counts: Record<string, number>;
  processing_logs: string[];
  demographic_focus_summary?: string | null;
}

export type KnowledgeStreamEventName =
  | "knowledge_started"
  | "knowledge_document_started"
  | "knowledge_chunk_started"
  | "knowledge_chunk_completed"
  | "knowledge_partial"
  | "knowledge_completed"
  | "knowledge_failed"
  | "heartbeat";

export interface KnowledgeStreamEvent {
  name: KnowledgeStreamEventName | string;
  payload: Record<string, unknown>;
  raw: MessageEvent<string>;
}

export interface KnowledgeStreamSubscription {
  close: () => void;
}

export interface ConsoleKnowledgeDocumentInput {
  document_text: string;
  source_path?: string | null;
}

export interface ConsoleKnowledgeProcessRequest {
  document_text?: string | null;
  source_path?: string | null;
  documents?: ConsoleKnowledgeDocumentInput[];
  guiding_prompt?: string | null;
  demographic_focus?: string | null;
  use_default_demo_document?: boolean;
}

export interface ConsoleScrapeResponse {
  url: string;
  title: string;
  text: string;
  length: number;
}

export interface ConsoleDynamicFilterFieldResponse {
  field: string;
  type: "range" | "multi-select-chips" | "single-select-chips" | "dropdown" | string;
  label: string;
  options: string[];
  min?: number | null;
  max?: number | null;
  default_min?: number | null;
  default_max?: number | null;
  default?: string | string[] | null;
}

export interface ConsoleDynamicFiltersResponse {
  session_id: string;
  country: string;
  use_case?: string | null;
  filters: ConsoleDynamicFilterFieldResponse[];
}

export interface TokenUsageEstimateResponse {
  with_caching_usd: number;
  without_caching_usd: number;
  savings_pct: number;
  model: string;
}

export interface TokenUsageRuntimeResponse {
  total_input_tokens: number;
  total_output_tokens: number;
  total_cached_tokens: number;
  estimated_cost_usd: number;
  cost_without_caching_usd: number;
  caching_savings_usd: number;
  caching_savings_pct: number;
  model: string;
}

export interface ParsedSamplingInstructions {
  hard_filters: Record<string, string[]>;
  soft_boosts: Record<string, string[]>;
  soft_penalties?: Record<string, string[]>;
  exclusions: Record<string, string[]>;
  distribution_targets: Record<string, string[]>;
  notes_for_ui: string[];
  source?: string;
}

export interface PopulationSelectionReason {
  score: number;
  selection_score?: number;
  matched_facets: string[];
  matched_document_entities: string[];
  instruction_matches: string[];
  bm25_terms: string[];
  semantic_summary: string;
  semantic_relevance: number;
  bm25_relevance?: number;
  geographic_relevance: number;
  socioeconomic_relevance: number;
  digital_behavior_relevance: number;
  filter_alignment: number;
}

export interface SampledPersona {
  agent_id: string;
  display_name?: string;
  persona: Record<string, unknown>;
  selection_reason: PopulationSelectionReason;
}

export interface PopulationGraphNode {
  id: string;
  label: string;
  subtitle?: string;
  planning_area?: string;
  industry?: string;
  node_type?: string;
  score?: number;
  age?: number;
  sex?: string;
}

export interface PopulationGraphLink {
  source: string;
  target: string;
  weight?: number;
  reason?: string;
  reasons?: string[];
  label?: string;
}

export interface PopulationArtifact {
  session_id: string;
  candidate_count: number;
  sample_count: number;
  sample_mode: "affected_groups" | "population_baseline";
  sample_seed: number;
  parsed_sampling_instructions: ParsedSamplingInstructions;
  coverage: {
    planning_areas?: string[];
    states?: string[];
    geography?: string[];
    geography_label?: string | null;
    age_buckets: Record<string, number>;
    sex_distribution?: Record<string, number>;
  };
  sampled_personas: SampledPersona[];
  agent_graph: {
    nodes: PopulationGraphNode[];
    links: PopulationGraphLink[];
  };
  representativeness: {
    status: string;
    geography_distribution?: Record<string, number>;
    state_distribution?: Record<string, number>;
    planning_area_distribution?: Record<string, number>;
    geography_label?: string | null;
    sex_distribution?: Record<string, number>;
  };
  selection_diagnostics: {
    candidate_count?: number;
    structured_filter_count?: number;
    shortlist_count?: number;
    bm25_shortlist_count?: number;
    semantic_rerank_count?: number;
  };
}

function getDefaultMode(): ConsoleMode {
  return isLiveBootMode() ? "live" : "demo";
}

export interface SimulationCounters {
  posts: number;
  comments: number;
  reactions: number;
  active_authors: number;
}

export interface SimulationCheckpointStatus {
  status: string;
  completed_agents: number;
  total_agents: number;
}

export interface SimulationState {
  session_id: string;
  status: string;
  event_count: number;
  last_round: number;
  platform?: string | null;
  planned_rounds?: number | null;
  current_round?: number | null;
  elapsed_seconds?: number | null;
  estimated_total_seconds?: number | null;
  estimated_remaining_seconds?: number | null;
  counters: SimulationCounters;
  checkpoint_status: Record<string, SimulationCheckpointStatus>;
  top_threads: Array<Record<string, unknown>>;
  discussion_momentum: Record<string, unknown>;
  latest_metrics: Record<string, unknown>;
  recent_events: Array<Record<string, unknown>>;
}

export interface ReportMetricDelta {
  metric_name: string;
  metric_label: string;
  metric_unit: string;
  initial_value: number;
  final_value: number;
  delta: number;
  direction: string;
  report_title?: string;
  initial_display?: string;
  final_display?: string;
  delta_display?: string;
  type?: string;
}

export interface ReportEvidenceItem {
  agent_id?: string;
  agent_name?: string;
  post_id?: string;
  quote?: string;
  content?: string;
  source_label?: string;
}

export interface ReportSection {
  question: string;
  report_title: string;
  type: string;
  bullets: string[];
  evidence: ReportEvidenceItem[];
  metric?: ReportMetricDelta;
}

export interface ReportPresetSection {
  title: string;
  bullets: string[];
}

export interface StructuredReportState {
  session_id: string;
  status: string;
  generated_at: string | null;
  executive_summary: string | null;
  quick_stats: Record<string, unknown>;
  metric_deltas: ReportMetricDelta[];
  sections: ReportSection[];
  insight_blocks: Array<Record<string, unknown>>;
  preset_sections: ReportPresetSection[];
  error?: string | null;
}

export interface ConsoleChatResponseMessage {
  agent_id?: string;
  agent_name?: string;
  content: string;
}

export interface ConsoleGroupChatResponse {
  session_id: string;
  responses: ConsoleChatResponseMessage[];
}

export interface ConsoleGroupChatAgentsResponse {
  session_id: string;
  segment: string;
  metric_name?: string | null;
  score_field: string;
  agents: Array<{
    agent_id: string;
    agent_name?: string;
    influence_score: number;
    score?: number | null;
  }>;
}

export interface ConsoleAgentChatResponse {
  session_id: string;
  agent_id?: string;
  responses: ConsoleChatResponseMessage[];
}

type DemoOutput = {
  generated_at?: string;
  session?: Record<string, unknown>;
  source_run?: Record<string, unknown>;
  analysis_questions?: Array<Record<string, unknown>>;
  knowledge?: Record<string, unknown>;
  population?: Record<string, unknown>;
  simulationState?: Record<string, unknown>;
  report?: Record<string, unknown>;
  analytics?: Record<string, unknown>;
};

type DemoSessionConfig = {
  session_id: string;
  country: string;
  use_case: string;
  provider: ModelProviderId | V2ProviderId;
  model: string;
  embed_model_name: string;
  base_url: string;
  api_key: string;
  analysis_questions: Array<Record<string, unknown>>;
};

type DemoAgentRecord = {
  agent_id: string;
  agent_name: string;
  occupation: string;
  planning_area: string;
  approval_score: number;
  metric_score: number;
  sentiment: "positive" | "neutral" | "negative";
  influence_score: number;
};

const STATIC_COUNTRIES: V2CountryResponse[] = [
  { name: "Singapore", code: "sg", flag_emoji: "🇸🇬", dataset_path: "config/countries/singapore.yaml", available: true, dataset_ready: true, download_required: false, download_status: "ready", download_error: null, missing_dependency: null },
  { name: "USA", code: "usa", flag_emoji: "🇺🇸", dataset_path: "config/countries/usa.yaml", available: true, dataset_ready: true, download_required: false, download_status: "ready", download_error: null, missing_dependency: null },
  { name: "India", code: "india", flag_emoji: "🇮🇳", dataset_path: "", available: false, dataset_ready: false, download_required: false, download_status: "missing", download_error: null, missing_dependency: null },
  { name: "Japan", code: "japan", flag_emoji: "🇯🇵", dataset_path: "", available: false, dataset_ready: false, download_required: false, download_status: "missing", download_error: null, missing_dependency: null },
];

const STATIC_V2_PROVIDERS: V2ProviderResponse[] = [
  { name: "gemini", models: ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro"], requires_api_key: true },
  { name: "openai", models: ["gpt-4o-mini", "gpt-4o"], requires_api_key: true },
  { name: "ollama", models: ["qwen3:4b-instruct-2507-q4_K_M", "llama3:8b"], requires_api_key: false },
];

const STATIC_MODEL_CATALOG: ConsoleModelProvider[] = [
  {
    id: "google",
    label: "Google Gemini",
    default_model: "gemini-2.5-flash-lite",
    default_embed_model: "nomic-embed-text",
    default_base_url: "",
    requires_api_key: true,
  },
  {
    id: "openrouter",
    label: "OpenRouter",
    default_model: "meta-llama/llama-3.1-8b-instruct:free",
    default_embed_model: "nomic-embed-text",
    default_base_url: "https://openrouter.ai/api/v1",
    requires_api_key: true,
  },
  {
    id: "openai",
    label: "OpenAI",
    default_model: "gpt-4o-mini",
    default_embed_model: "text-embedding-3-small",
    default_base_url: "https://api.openai.com/v1",
    requires_api_key: true,
  },
  {
    id: "ollama",
    label: "Ollama (Local)",
    default_model: "qwen3:4b-instruct-2507-q4_K_M",
    default_embed_model: "nomic-embed-text",
    default_base_url: "http://127.0.0.1:11434/v1/",
    requires_api_key: false,
  },
];

const STATIC_ANALYSIS_QUESTIONS: Record<string, Array<Record<string, unknown>>> = {
  "public-policy-testing": [
    {
      question: "From your persona's perspective, how strongly do you approve of this policy? Rate 1-10 and explain your score briefly.",
      type: "scale",
      metric_name: "approval_rate",
      metric_label: "Approval Rate",
      metric_unit: "%",
      threshold: 7,
      threshold_direction: "gte",
      report_title: "Policy Approval",
      tooltip: "Percentage of agents who rated approval >= 7/10.",
    },
    {
      question: "From your persona's perspective, which specific parts of this policy do you support or oppose, and why?",
      type: "open-ended",
      metric_name: "policy_viewpoints",
      report_title: "Key Viewpoints",
      tooltip: "Qualitative summary of the main arguments for and against the policy.",
    },
  ],
  "product-market-research": [
    {
      question: "How interested are you in this product? Rate 1-10.",
      type: "scale",
      metric_name: "product_interest",
      metric_label: "Product Interest",
      metric_unit: "%",
      threshold: 7,
      threshold_direction: "gte",
      report_title: "Product Interest",
      tooltip: "Percentage of agents who rated interest >= 7/10.",
    },
    {
      question: "What would you change or improve about this product?",
      type: "open-ended",
      metric_name: "product_feedback",
      report_title: "Product Feedback",
      tooltip: "Qualitative summary of what agents liked, disliked, and want improved.",
    },
    {
      question: "Would you recommend this to a friend? Rate 1-10.",
      type: "scale",
      metric_name: "nps_score",
      metric_label: "NPS (Promoters)",
      metric_unit: "%",
      threshold: 8,
      threshold_direction: "gte",
      report_title: "Net Promoter Score",
      tooltip: "Percentage of agents who would recommend with score >= 8.",
    },
    {
      question: "What are the main pain points or problems you see with this product?",
      type: "open-ended",
      metric_name: "pain_points",
      report_title: "Pain Points",
      tooltip: "Top pain points and unmet needs raised by agents.",
    },
    {
      question: "What alternatives or competitors would you compare this to, and why?",
      type: "open-ended",
      metric_name: "competitive_landscape",
      report_title: "Competitive Landscape",
      tooltip: "Alternatives and competitors mentioned by agents with comparison reasoning.",
    },
  ],
  "campaign-content-testing": [
    {
      question: "Would you try or buy this product/service after seeing this content? (yes/no)",
      type: "yes-no",
      metric_name: "conversion_intent",
      metric_label: "Conversion Intent",
      metric_unit: "%",
      report_title: "Conversion Analysis",
      tooltip: "Percentage of agents expressing intent to buy or try after seeing the content.",
    },
    {
      question: "How engaging is this content? Rate 1-10.",
      type: "scale",
      metric_name: "engagement_score",
      metric_label: "Engagement Score",
      metric_unit: "/10",
      report_title: "Audience Engagement",
      tooltip: "Mean engagement rating across all agents.",
    },
    {
      question: "How credible and trustworthy does this content feel? Rate 1-10.",
      type: "scale",
      metric_name: "credibility_score",
      metric_label: "Credibility",
      metric_unit: "/10",
      report_title: "Content Credibility",
      tooltip: "Mean credibility and trust rating across all agents.",
    },
    {
      question: "What concerns or objections do you have about this content?",
      type: "open-ended",
      metric_name: "objections",
      report_title: "Top Objections",
      tooltip: "Most common reasons agents rejected or were skeptical of the content.",
    },
  ],
};

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
let demoOutputPromise: Promise<DemoOutput> | null = null;
let demoSessionConfig: DemoSessionConfig | null = null;

async function buildAuthorizedInit(init: RequestInit = {}): Promise<RequestInit> {
  const nextHeaders = new Headers(init.headers || {});
  const token = await getSupabaseAccessToken().catch(() => null);
  if (token && !nextHeaders.has("Authorization")) {
    nextHeaders.set("Authorization", `Bearer ${token}`);
  }
  return {
    ...init,
    headers: nextHeaders,
  };
}

async function authenticatedFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  return globalThis.fetch(input, await buildAuthorizedInit(init));
}

export function resetBundledDemoState(): void {
  demoOutputPromise = null;
  demoSessionConfig = null;
}

function demoOutputPath(): string {
  const base = String(import.meta.env.BASE_URL || "/");
  return `${base.endsWith("/") ? base : `${base}/`}demo-output.json`;
}

export function getBootMode(): BootMode {
  const mode = String(import.meta.env.VITE_BOOT_MODE || "demo").trim().toLowerCase();
  if (mode === "live" || mode === "demo-static") {
    return mode;
  }
  return "demo";
}

export function isLiveBootMode(): boolean {
  return getBootMode() === "live";
}

export function isStaticDemoBootMode(): boolean {
  return getBootMode() === "demo-static";
}

export function isDemoBootMode(): boolean {
  return getBootMode() !== "live";
}

export async function getBundledDemoOutput(): Promise<Record<string, unknown>> {
  return (await loadBundledDemoOutput()) as Record<string, unknown>;
}

async function loadBundledDemoOutput(): Promise<DemoOutput> {
  if (!demoOutputPromise) {
    demoOutputPromise = (async () => {
      const response = await authenticatedFetch(demoOutputPath());
      await ensureResponseOk(response);
      return response.json() as Promise<DemoOutput>;
    })();
  }
  return demoOutputPromise;
}

function staticQuestionsForUseCase(useCase: string | null | undefined): Array<Record<string, unknown>> {
  const normalized = normalizeUseCaseId(useCase);
  const questions = STATIC_ANALYSIS_QUESTIONS[normalized] ?? STATIC_ANALYSIS_QUESTIONS["public-policy-testing"];
  return questions.map((question) => ({ ...question }));
}

function demoQuestionsFromOutput(demo: DemoOutput, useCase: string | null | undefined): Array<Record<string, unknown>> {
  const topLevel = Array.isArray(demo.analysis_questions) ? demo.analysis_questions : [];
  if (topLevel.length > 0) {
    return topLevel.map((question) => ({ ...question }));
  }
  const sourceRun = (demo.source_run ?? {}) as Record<string, unknown>;
  const sourceQuestions = Array.isArray(sourceRun.analysis_questions) ? sourceRun.analysis_questions : [];
  if (sourceQuestions.length > 0) {
    return sourceQuestions.map((question) => ({ ...question }));
  }
  return staticQuestionsForUseCase(useCase);
}

function defaultModelForProvider(provider: string): string {
  const normalized = normalizeProviderId(provider);
  return STATIC_MODEL_CATALOG.find((entry) => entry.id === normalized)?.default_model ?? "gemini-2.5-flash-lite";
}

function defaultBaseUrlForProvider(provider: string): string {
  const normalized = normalizeProviderId(provider);
  return STATIC_MODEL_CATALOG.find((entry) => entry.id === normalized)?.default_base_url ?? "";
}

async function ensureDemoSessionConfig(
  patch: Partial<DemoSessionConfig> = {},
): Promise<DemoSessionConfig> {
  const normalizedPatch = Object.fromEntries(
    Object.entries(patch).filter(([, value]) => value !== undefined),
  ) as Partial<DemoSessionConfig>;

  if (!demoSessionConfig) {
    const demo = await loadBundledDemoOutput();
    const source = (demo.source_run ?? {}) as Record<string, unknown>;
    const provider = normalizeProviderId(String(normalizedPatch.provider ?? source.provider ?? "google"));
    const useCase = normalizeUseCaseId(String(normalizedPatch.use_case ?? source.use_case ?? "public-policy-testing"));
    demoSessionConfig = {
      session_id: String(normalizedPatch.session_id ?? demo.session?.session_id ?? "demo-session"),
      country: String(normalizedPatch.country ?? source.country ?? "singapore"),
      use_case: useCase,
      provider,
      model: String(normalizedPatch.model ?? source.model ?? defaultModelForProvider(provider)),
      embed_model_name: String(normalizedPatch.embed_model_name ?? "nomic-embed-text"),
      base_url: String(normalizedPatch.base_url ?? defaultBaseUrlForProvider(provider)),
      api_key: String(normalizedPatch.api_key ?? ""),
      analysis_questions:
        normalizedPatch.analysis_questions?.map((question) => ({ ...question }))
        ?? demoQuestionsFromOutput(demo, useCase),
    };
  }

  const nextUseCase = normalizedPatch.use_case ? normalizeUseCaseId(normalizedPatch.use_case) : demoSessionConfig.use_case;
  const nextProvider = normalizedPatch.provider ? normalizeProviderId(String(normalizedPatch.provider)) : demoSessionConfig.provider;

  demoSessionConfig = {
    ...demoSessionConfig,
    ...normalizedPatch,
    use_case: nextUseCase,
    provider: nextProvider,
    model: String(normalizedPatch.model ?? demoSessionConfig.model ?? defaultModelForProvider(nextProvider)),
    embed_model_name: String(normalizedPatch.embed_model_name ?? demoSessionConfig.embed_model_name ?? "nomic-embed-text"),
    base_url: String(normalizedPatch.base_url ?? demoSessionConfig.base_url ?? defaultBaseUrlForProvider(nextProvider)),
    api_key: String(normalizedPatch.api_key ?? demoSessionConfig.api_key ?? ""),
    analysis_questions:
      normalizedPatch.analysis_questions?.map((question) => ({ ...question }))
      ?? (normalizedPatch.use_case ? staticQuestionsForUseCase(nextUseCase) : demoSessionConfig.analysis_questions),
  };

  return demoSessionConfig;
}

function maskDemoApiKey(apiKey: string): string | undefined {
  if (!apiKey) {
    return undefined;
  }
  if (apiKey.length <= 8) {
    return "configured";
  }
  return `${apiKey.slice(0, 4)}...${apiKey.slice(-4)}`;
}

function buildDemoConsoleSession(config: DemoSessionConfig): ConsoleSessionResponse {
  return {
    session_id: config.session_id,
    mode: "demo",
    status: "ready",
    model_provider: normalizeProviderId(String(config.provider)) as ModelProviderId,
    model_name: config.model,
    embed_model_name: config.embed_model_name,
    base_url: config.base_url,
    api_key_configured: Boolean(config.api_key),
    api_key_masked: maskDemoApiKey(config.api_key),
  };
}

function buildDemoModelConfig(config: DemoSessionConfig): ConsoleSessionModelConfigResponse {
  return {
    session_id: config.session_id,
    model_provider: normalizeProviderId(String(config.provider)) as ModelProviderId,
    model_name: config.model,
    embed_model_name: config.embed_model_name,
    base_url: config.base_url,
    api_key_configured: Boolean(config.api_key),
    api_key_masked: maskDemoApiKey(config.api_key),
  };
}

function buildDemoConfigResponse(config: DemoSessionConfig): V2SessionConfigResponse {
  return {
    session_id: config.session_id,
    country: config.country,
    use_case: config.use_case,
    provider: config.provider,
    model: config.model,
    api_key_configured: Boolean(config.api_key),
    analysis_questions: config.analysis_questions.map((question) => ({ ...question })),
  };
}

function metricScoreFromSelectionReason(row: Record<string, unknown>): number {
  const selectionReason = (row.selection_reason ?? {}) as Record<string, unknown>;
  const rawScore = Number(selectionReason.selection_score ?? selectionReason.score ?? 0.5);
  return Math.max(1, Math.min(10, Math.round(rawScore * 10)));
}

function approvalScoreFromSelectionReason(row: Record<string, unknown>): number {
  const selectionReason = (row.selection_reason ?? {}) as Record<string, unknown>;
  const rawScore = Number(selectionReason.selection_score ?? selectionReason.score ?? 0.5);
  return Math.max(1, Math.min(100, Math.round(rawScore * 100)));
}

function sentimentFromMetricScore(score: number): DemoAgentRecord["sentiment"] {
  if (score >= 7) return "positive";
  if (score < 5) return "negative";
  return "neutral";
}

function resolveDemoDisplayName(row: Record<string, unknown>): string {
  const direct = String(row.display_name ?? "").trim();
  if (direct) return direct;
  const persona = (row.persona ?? {}) as Record<string, unknown>;
  const personaName = String(persona.display_name ?? persona.name ?? "").trim();
  if (personaName) return personaName;
  const fallback = String(persona.occupation ?? row.agent_id ?? "Resident").trim();
  return fallback || "Resident";
}

async function getDemoAgentRecords(): Promise<DemoAgentRecord[]> {
  const demo = await loadBundledDemoOutput();
  const personas = Array.isArray(demo.population?.sampled_personas)
    ? demo.population?.sampled_personas
    : [];

  return personas.map((item, index) => {
    const row = item as Record<string, unknown>;
    const persona = (row.persona ?? {}) as Record<string, unknown>;
    const metricScore = metricScoreFromSelectionReason(row);
    return {
      agent_id: String(row.agent_id ?? `demo-agent-${index + 1}`),
      agent_name: resolveDemoDisplayName(row),
      occupation: String(persona.occupation ?? "Resident"),
      planning_area: String(persona.planning_area ?? "Unknown"),
      approval_score: approvalScoreFromSelectionReason(row),
      metric_score: metricScore,
      sentiment: sentimentFromMetricScore(metricScore),
      influence_score: Number((row.selection_reason as Record<string, unknown> | undefined)?.selection_score ?? (row.selection_reason as Record<string, unknown> | undefined)?.score ?? 0),
    } satisfies DemoAgentRecord;
  });
}

async function getDemoAgentLookup(): Promise<Map<string, DemoAgentRecord>> {
  return new Map((await getDemoAgentRecords()).map((agent) => [agent.agent_id, agent]));
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function normalizeStringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => String(item ?? "").trim())
    .filter((item) => item.length > 0);
}

function resolveDemoReportRecord(demo: DemoOutput): Record<string, unknown> {
  const directReport = asRecord(demo.report);
  const looksLikeReport = (value: Record<string, unknown>): boolean => {
    return Boolean(
      String(value.session_id ?? "").trim()
      || String(value.executive_summary ?? "").trim()
      || Array.isArray(value.metric_deltas)
      || Array.isArray(value.sections)
      || Array.isArray(value.preset_sections),
    );
  };

  return looksLikeReport(directReport) ? directReport : {};
}

function resolveDemoAnalyticsPayload(
  demo: DemoOutput,
  key: string,
  metricName?: string,
): Record<string, unknown> {
  const analytics = asRecord(demo.analytics);
  if (metricName) {
    const byMetric = asRecord(analytics.by_metric);
    const metricRecord = asRecord(byMetric[metricName]);
    const metricPayload = asRecord(metricRecord[key]);
    if (Object.keys(metricPayload).length > 0) {
      return metricPayload;
    }
  }
  return asRecord(analytics[key]);
}

function resolveDemoCascadesRecord(demo: DemoOutput): Record<string, unknown> {
  const cascades = resolveDemoAnalyticsPayload(demo, "cascades");
  if (Object.keys(cascades).length > 0) {
    return cascades;
  }

  const report = resolveDemoReportRecord(demo);
  const insightBlocks = Array.isArray(report.insight_blocks) ? report.insight_blocks : [];
  const cascadeBlock = insightBlocks.find((block) => {
    const entry = asRecord(block);
    return entry.type === "viral_cascade";
  });
  return asRecord(asRecord(cascadeBlock).data);
}

function normalizeMetricDelta(raw: unknown): ReportMetricDelta | null {
  const entry = asRecord(raw);
  const metricName = String(entry.metric_name ?? "").trim();
  const metricLabel = String(entry.metric_label ?? metricName).trim();
  if (!metricName && !metricLabel) {
    return null;
  }
  return {
    metric_name: metricName || metricLabel.toLowerCase().replace(/\s+/g, "_"),
    metric_label: metricLabel || metricName,
    metric_unit: String(entry.metric_unit ?? "").trim(),
    initial_value: Number(entry.initial_value ?? 0),
    final_value: Number(entry.final_value ?? 0),
    delta: Number(entry.delta ?? 0),
    direction: String(entry.direction ?? "flat"),
    report_title: String(entry.report_title ?? "").trim() || undefined,
    initial_display: String(entry.initial_display ?? "").trim() || undefined,
    final_display: String(entry.final_display ?? "").trim() || undefined,
    delta_display: String(entry.delta_display ?? "").trim() || undefined,
    type: String(entry.type ?? "").trim() || undefined,
  };
}

function normalizeEvidenceItem(raw: unknown): ReportEvidenceItem {
  const entry = asRecord(raw);
  return {
    agent_id: String(entry.agent_id ?? "").trim() || undefined,
    agent_name: String(entry.agent_name ?? "").trim() || undefined,
    post_id: String(entry.post_id ?? "").trim() || undefined,
    quote: String(entry.quote ?? "").trim() || undefined,
    content: String(entry.content ?? "").trim() || undefined,
    source_label: String(entry.source_label ?? "").trim() || undefined,
  };
}

function normalizeReportSection(raw: unknown): ReportSection | null {
  const entry = asRecord(raw);
  const question = String(entry.question ?? "").trim();
  const title = String(entry.report_title ?? question).trim();
  if (!question && !title) {
    return null;
  }
  const metric = normalizeMetricDelta(entry.metric);
  return {
    question: question || title,
    report_title: title || question,
    type: String(entry.type ?? "open-ended").trim() || "open-ended",
    bullets: normalizeStringList(entry.bullets),
    evidence: Array.isArray(entry.evidence) ? entry.evidence.map((item) => normalizeEvidenceItem(item)) : [],
    ...(metric ? { metric } : {}),
  };
}

function normalizePresetSection(raw: unknown): ReportPresetSection | null {
  const entry = asRecord(raw);
  const title = String(entry.title ?? "").trim();
  if (!title) {
    return null;
  }
  return {
    title,
    bullets: normalizeStringList(entry.bullets),
  };
}

async function getDemoViralPosts(): Promise<Array<Record<string, unknown>>> {
  const demo = await loadBundledDemoOutput();
  const cascades = resolveDemoCascadesRecord(demo);
  const posts = Array.isArray(cascades.viral_posts)
    ? cascades.viral_posts
    : Array.isArray(cascades.posts)
      ? cascades.posts
      : Array.isArray(cascades.top_threads)
        ? cascades.top_threads
        : [];
  return posts.map((post) => ({ ...(post as Record<string, unknown>) }));
}

function resolveConversationAuthorName(
  agent: DemoAgentRecord | undefined,
  authoredName: unknown,
  authoredId: string,
): string {
  const payloadName = String(authoredName ?? "").trim();
  const agentName = String(agent?.agent_name ?? "").trim();
  const agentOccupation = String(agent?.occupation ?? "").trim();

  if (agentName && agentName !== authoredId && agentName !== agentOccupation) {
    return agentName;
  }
  if (payloadName) {
    return payloadName;
  }
  if (agentName) {
    return agentName;
  }
  return authoredId;
}

export async function getBundledDemoSimulationPosts(): Promise<SimPost[]> {
  const [lookup, posts] = await Promise.all([getDemoAgentLookup(), getDemoViralPosts()]);
  return posts.slice(0, 16).map((item, index) => {
    const post = item as Record<string, unknown>;
    const authorId = String(post.author ?? post.author_agent_id ?? `agent-${index + 1}`);
    const agent = lookup.get(authorId);
    const authorName = resolveConversationAuthorName(agent, post.author_name, authorId);
    const comments = Array.isArray(post.comments) ? post.comments : [];
    return {
      id: String(post.post_id ?? `demo-post-${index + 1}`),
      agentId: authorId,
      agentName: authorName,
      agentOccupation: agent?.occupation ?? "Resident",
      agentArea: agent?.planning_area ?? "Unknown",
      title: String(post.title ?? "Discussion thread"),
      content: String(post.content ?? post.body ?? ""),
      upvotes: Math.max(0, Number(post.upvotes ?? post.likes ?? 0)),
      downvotes: Math.max(0, Number(post.downvotes ?? post.dislikes ?? 0)),
      commentCount: comments.length,
      round: 1,
      timestamp: "Captured demo run",
      comments: comments.map((comment, commentIndex) => {
        const entry = comment as Record<string, unknown>;
        const commentAgentId = String(entry.author ?? entry.author_agent_id ?? `comment-agent-${commentIndex + 1}`);
        const commentAgent = lookup.get(commentAgentId);
        return {
          id: String(entry.comment_id ?? `${post.post_id}-comment-${commentIndex + 1}`),
          agentName: resolveConversationAuthorName(commentAgent, entry.author_name, commentAgentId),
          agentOccupation: commentAgent?.occupation ?? "",
          content: String(entry.content ?? entry.body ?? ""),
          upvotes: Math.max(0, Number(entry.upvotes ?? entry.likes ?? 0)),
        };
      }),
    } satisfies SimPost;
  });
}

async function getDemoKnowledgeArtifact(sessionId: string): Promise<KnowledgeArtifact> {
  const demo = await loadBundledDemoOutput();
  const knowledge = (demo.knowledge ?? {}) as Record<string, unknown>;
  return {
    session_id: sessionId,
    document: (knowledge.document ?? { document_id: `demo-document-${sessionId}` }) as KnowledgeArtifact["document"],
    summary: String(knowledge.summary ?? ""),
    guiding_prompt: (knowledge.guiding_prompt as string | null | undefined) ?? null,
    entity_nodes: Array.isArray(knowledge.entity_nodes) ? (knowledge.entity_nodes as KnowledgeNode[]) : [],
    relationship_edges: Array.isArray(knowledge.relationship_edges) ? (knowledge.relationship_edges as KnowledgeEdge[]) : [],
    entity_type_counts: (knowledge.entity_type_counts as Record<string, number> | undefined) ?? {},
    processing_logs: Array.isArray(knowledge.processing_logs) ? knowledge.processing_logs.map((entry) => String(entry)) : [],
    demographic_focus_summary: (knowledge.demographic_focus_summary as string | null | undefined) ?? null,
  };
}

async function getDemoPopulationArtifact(sessionId: string): Promise<PopulationArtifact> {
  const demo = await loadBundledDemoOutput();
  const population = (demo.population ?? {}) as Record<string, unknown>;
  return {
    session_id: sessionId,
    candidate_count: Number(population.candidate_count ?? 0),
    sample_count: Number(population.sample_count ?? 0),
    sample_mode: (population.sample_mode as PopulationArtifact["sample_mode"]) ?? "affected_groups",
    sample_seed: Number(population.sample_seed ?? 0),
    parsed_sampling_instructions: (population.parsed_sampling_instructions as PopulationArtifact["parsed_sampling_instructions"]) ?? {
      hard_filters: {},
      soft_boosts: {},
      soft_penalties: {},
      exclusions: {},
      distribution_targets: {},
      notes_for_ui: [],
    },
    coverage: (population.coverage as PopulationArtifact["coverage"]) ?? {
      planning_areas: [],
      age_buckets: {},
    },
    sampled_personas: Array.isArray(population.sampled_personas) ? (population.sampled_personas as SampledPersona[]) : [],
    agent_graph: (population.agent_graph as PopulationArtifact["agent_graph"]) ?? {
      nodes: [],
      links: [],
    },
    representativeness: (population.representativeness as PopulationArtifact["representativeness"]) ?? {
      status: "unknown",
    },
    selection_diagnostics: (population.selection_diagnostics as PopulationArtifact["selection_diagnostics"]) ?? {},
  };
}

async function getDemoSimulationStatePayload(sessionId: string): Promise<SimulationState> {
  const demo = await loadBundledDemoOutput();
  const payload = (demo.simulationState ?? {}) as Record<string, unknown>;
  return {
    session_id: sessionId,
    status: String(payload.status ?? "completed"),
    event_count: Number(payload.event_count ?? 0),
    last_round: Number(payload.last_round ?? 0),
    platform: (payload.platform as string | null | undefined) ?? "reddit",
    planned_rounds: Number(payload.planned_rounds ?? 0),
    current_round: Number(payload.current_round ?? payload.last_round ?? 0),
    elapsed_seconds: Number(payload.elapsed_seconds ?? 0),
    estimated_total_seconds: Number(payload.estimated_total_seconds ?? payload.elapsed_seconds ?? 0),
    estimated_remaining_seconds: Number(payload.estimated_remaining_seconds ?? 0),
    counters: (payload.counters as SimulationCounters | undefined) ?? { posts: 0, comments: 0, reactions: 0, active_authors: 0 },
    checkpoint_status: (payload.checkpoint_status as Record<string, SimulationCheckpointStatus> | undefined) ?? {},
    top_threads: Array.isArray(payload.top_threads) ? (payload.top_threads as Array<Record<string, unknown>>) : [],
    discussion_momentum: (payload.discussion_momentum as Record<string, unknown> | undefined) ?? {},
    latest_metrics: (payload.latest_metrics as Record<string, unknown> | undefined) ?? {},
    recent_events: Array.isArray(payload.recent_events) ? (payload.recent_events as Array<Record<string, unknown>>) : [],
  };
}

async function getDemoReportPayload(sessionId: string): Promise<StructuredReportState> {
  const demo = await loadBundledDemoOutput();
  const report = resolveDemoReportRecord(demo);
  return {
    session_id: sessionId,
    status: String(report.status ?? "complete"),
    generated_at: (report.generated_at as string | null | undefined) ?? null,
    executive_summary: (report.executive_summary as string | null | undefined) ?? null,
    quick_stats: (report.quick_stats as Record<string, unknown> | undefined) ?? {},
    metric_deltas: Array.isArray(report.metric_deltas)
      ? report.metric_deltas.map((item) => normalizeMetricDelta(item)).filter((item): item is ReportMetricDelta => item !== null)
      : [],
    sections: Array.isArray(report.sections)
      ? report.sections.map((item) => normalizeReportSection(item)).filter((item): item is ReportSection => item !== null)
      : [],
    insight_blocks: Array.isArray(report.insight_blocks) ? (report.insight_blocks as Array<Record<string, unknown>>) : [],
    preset_sections: Array.isArray(report.preset_sections)
      ? report.preset_sections.map((item) => normalizePresetSection(item)).filter((item): item is ReportPresetSection => item !== null)
      : [],
    error: (report.error as string | null | undefined) ?? null,
  };
}

function buildStaticQuestionMetadata(question: string): Record<string, unknown> {
  const text = String(question ?? "").trim();
  const slug = text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .split(/\s+/)
    .slice(0, 4)
    .join("_") || "custom_metric";
  const lower = text.toLowerCase();
  const type = /(yes\/no|yes or no|\(yes\/no\)|\bwould you\b|\bdo you\b|\bare you\b)/.test(lower)
    ? "yes-no"
    : /(rate\s+1-10|score\s+1-10|how .*rate|how .*score)/.test(lower)
      ? "scale"
      : "open-ended";

  return {
    question: text,
    type,
    metric_name: slug,
    metric_label: text.slice(0, 48) || "Custom Metric",
    metric_unit: type === "yes-no" ? "%" : type === "scale" ? "/10" : undefined,
    threshold: type === "scale" ? 7 : undefined,
    threshold_direction: type === "scale" ? "gte" : undefined,
    report_title: text.slice(0, 60) || "Custom Question",
    tooltip: "Generated locally for static demo mode.",
  };
}

function buildDemoChatContent(agent: DemoAgentRecord): string {
  const firstName = agent.agent_name.split(" ")[0] || "This agent";
  if (agent.sentiment === "negative") {
    return `${firstName} remains skeptical and keeps returning to practical costs, worker transition risk, and whether the policy meaningfully protects households in ${agent.planning_area}.`;
  }
  if (agent.sentiment === "positive") {
    return `${firstName} sees upside in the proposal, but still wants implementation details that help ${agent.occupation.toLowerCase()} households in ${agent.planning_area}.`;
  }
  return `${firstName} sees tradeoffs on both sides and wants clearer evidence before committing to a stronger position.`;
}

const CHAT_REQUEST_TIMEOUT_MS = 90_000;

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") {
        detail = body.detail;
      } else if (body?.detail !== undefined) {
        detail = JSON.stringify(body.detail);
      } else if (typeof body?.message === "string") {
        detail = body.message;
      } else {
        detail = JSON.stringify(body);
      }
    } catch {
      const text = await response.text();
      if (text) {
        detail = text;
      }
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

async function fetchChatWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs: number = CHAT_REQUEST_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const timeoutHandle = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await authenticatedFetch(url, { ...init, signal: controller.signal });
  } catch (error) {
    const isAbortError =
      (error instanceof DOMException && error.name === "AbortError")
      || (error instanceof Error && error.name === "AbortError");
    if (isAbortError) {
      throw new Error(
        `Live chat timed out after ${Math.round(timeoutMs / 1000)} seconds while waiting for backend memory retrieval. `
        + "Please retry and check backend service health.",
      );
    }
    throw error;
  } finally {
    clearTimeout(timeoutHandle);
  }
}

export function normalizeProviderId(provider: string | null | undefined): ModelProviderId | V2ProviderId {
  const normalized = String(provider ?? "").trim().toLowerCase();
  if (normalized === "gemini") {
    return "google";
  }
  if (normalized === "google" || normalized === "openrouter" || normalized === "openai" || normalized === "ollama") {
    return normalized;
  }
  return normalized as ModelProviderId | V2ProviderId;
}

export function displayProviderId(provider: string | null | undefined): string {
  const normalized = String(provider ?? "").trim().toLowerCase();
  if (normalized === "google") {
    return "gemini";
  }
  return normalized;
}

export function normalizeUseCaseId(useCase: string | null | undefined): string {
  const normalized = String(useCase ?? "").trim().toLowerCase();
  // V2 canonical names — pass through
  if (normalized === "public-policy-testing" || normalized === "product-market-research" || normalized === "campaign-content-testing") {
    return normalized;
  }
  // V1 backward compat
  if (normalized === "policy-review") return "public-policy-testing";
  if (normalized === "reviews" || normalized === "customer-review") return "product-market-research";
  if (normalized === "pmf-discovery" || normalized === "product-market-fit") return "product-market-research";
  if (normalized === "ad-testing") return "campaign-content-testing";
  return normalized;
}

export function displayUseCaseId(useCase: string | null | undefined): string {
  const normalized = String(useCase ?? "").trim().toLowerCase();
  // V2 canonical names — pass through as-is for display
  if (normalized === "public-policy-testing" || normalized === "product-market-research" || normalized === "campaign-content-testing") {
    return normalized;
  }
  // V1 backward compat
  if (normalized === "policy-review") return "public-policy-testing";
  if (normalized === "customer-review" || normalized === "reviews") return "product-market-research";
  if (normalized === "product-market-fit" || normalized === "pmf-discovery") return "product-market-research";
  if (normalized === "ad-testing") return "campaign-content-testing";
  return normalized;
}

export async function createConsoleSession(
  mode: ConsoleMode = getDefaultMode(),
  modelConfig: Partial<ConsoleSessionModelConfigRequest> = {},
): Promise<ConsoleSessionResponse> {
  if (isStaticDemoBootMode()) {
    const config = await ensureDemoSessionConfig({
      provider: modelConfig.model_provider ? normalizeProviderId(modelConfig.model_provider) : undefined,
      model: modelConfig.model_name,
      embed_model_name: modelConfig.embed_model_name,
      base_url: modelConfig.base_url,
      api_key: modelConfig.api_key,
      analysis_questions: modelConfig.analysis_questions,
    });
    return {
      ...buildDemoConsoleSession(config),
      mode,
    };
  }
  const response = await authenticatedFetch(`${API_BASE}/api/v2/console/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mode,
      ...modelConfig,
      model_provider: modelConfig.model_provider ? normalizeProviderId(modelConfig.model_provider) : undefined,
    }),
  });
  return parseJson(response);
}

export async function getV2Countries(): Promise<V2CountryResponse[]> {
  if (isStaticDemoBootMode()) {
    return STATIC_COUNTRIES.map((country) => ({ ...country }));
  }
  const response = await authenticatedFetch(`${API_BASE}/api/v2/countries`);
  return parseJson(response);
}

export async function downloadCountryDataset(countryId: string): Promise<{ status: string }> {
  const response = await authenticatedFetch(`${API_BASE}/api/v2/countries/${encodeURIComponent(countryId)}/download`, {
    method: "POST",
  });
  return parseJson(response);
}

export async function getCountryDownloadStatus(countryId: string): Promise<V2CountryResponse> {
  const response = await authenticatedFetch(`${API_BASE}/api/v2/countries/${encodeURIComponent(countryId)}/download-status`);
  return parseJson(response);
}

// ── Country UI Config ──

export interface CountryUiCohortDimension {
  key: string;
  label: string;
  persona_field?: string;
  type?: "age_bucket" | "geography";
}

export interface CountryUiTooltipField {
  field: string;
  label: string;
  section: "header" | "grid";
  type?: "geography";
  fallback_fields?: string[];
}

export interface CountryUiConfig {
  cohort_dimensions?: CountryUiCohortDimension[];
  tooltip_fields?: CountryUiTooltipField[];
}

const STATIC_UI_CONFIGS: Record<string, CountryUiConfig> = {
  sg: {
    cohort_dimensions: [
      { key: "industry", label: "Industry", persona_field: "industry" },
      { key: "ageBucket", label: "Age", type: "age_bucket" },
      { key: "geography", label: "Geography", type: "geography" },
      { key: "occupation", label: "Occupation", persona_field: "occupation" },
      { key: "sex", label: "Gender", persona_field: "sex" },
    ],
    tooltip_fields: [
      { field: "occupation", label: "Occupation", section: "header" },
      { field: "planning_area", label: "Geography", section: "grid", type: "geography" },
      { field: "education_level", label: "Education", section: "grid" },
      { field: "industry", label: "Industry", section: "grid" },
      { field: "cultural_background", label: "Culture", section: "grid" },
      { field: "income_bracket", label: "Salary", section: "grid", fallback_fields: ["salary", "household_income"] },
    ],
  },
  usa: {
    cohort_dimensions: [
      { key: "occupation", label: "Occupation", persona_field: "occupation" },
      { key: "ageBucket", label: "Age", type: "age_bucket" },
      { key: "geography", label: "Geography", type: "geography" },
      { key: "sex", label: "Gender", persona_field: "gender" },
      { key: "ethnicity", label: "Ethnicity", persona_field: "ethnicity" },
    ],
    tooltip_fields: [
      { field: "occupation", label: "Occupation", section: "header" },
      { field: "state", label: "State", section: "grid", type: "geography" },
      { field: "city", label: "City", section: "grid" },
      { field: "education_level", label: "Education", section: "grid" },
      { field: "ethnicity", label: "Ethnicity", section: "grid" },
      { field: "marital_status", label: "Marital Status", section: "grid" },
      { field: "bachelors_field", label: "Bachelors Field", section: "grid" },
      { field: "income_bracket", label: "Income", section: "grid", fallback_fields: ["salary", "household_income"] },
    ],
  },
};

export async function getCountryUiConfig(countryCode: string): Promise<CountryUiConfig> {
  if (isStaticDemoBootMode()) {
    const normalized = countryCode.trim().toLowerCase();
    return STATIC_UI_CONFIGS[normalized] ?? STATIC_UI_CONFIGS["sg"] ?? {};
  }
  try {
    const response = await authenticatedFetch(`${API_BASE}/api/v2/countries/${encodeURIComponent(countryCode)}/ui-config`);
    return await parseJson(response);
  } catch {
    const normalized = countryCode.trim().toLowerCase();
    return STATIC_UI_CONFIGS[normalized] ?? {};
  }
}

export async function getV2Providers(): Promise<V2ProviderResponse[]> {
  if (isStaticDemoBootMode()) {
    return STATIC_V2_PROVIDERS.map((provider) => ({ ...provider, models: [...provider.models] }));
  }
  const response = await authenticatedFetch(`${API_BASE}/api/v2/providers`);
  return parseJson(response);
}

export async function createV2Session(payload: V2SessionCreateRequest): Promise<V2SessionCreateResponse> {
  if (isStaticDemoBootMode()) {
    const config = await ensureDemoSessionConfig({
      country: payload.country,
      provider: normalizeProviderId(payload.provider),
      model: payload.model,
      api_key: payload.api_key,
      use_case: normalizeUseCaseId(payload.use_case),
      session_id: payload.session_id,
    });
    return { session_id: config.session_id };
  }
  const response = await authenticatedFetch(`${API_BASE}/api/v2/session/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...payload,
      mode: payload.mode ?? getDefaultMode(),
      provider: normalizeProviderId(payload.provider),
      use_case: normalizeUseCaseId(payload.use_case),
    }),
  });
  return parseJson(response);
}

export async function updateV2SessionConfig(
  sessionId: string,
  payload: {
    country?: string;
    use_case?: string;
    provider?: string;
    model?: string;
    api_key?: string;
    guiding_prompt?: string | null;
    analysis_questions?: Array<Record<string, unknown>>;
  },
): Promise<V2SessionConfigResponse> {
  if (isStaticDemoBootMode()) {
    const config = await ensureDemoSessionConfig({
      session_id: sessionId,
      country: payload.country,
      provider: payload.provider ? normalizeProviderId(payload.provider) : undefined,
      model: payload.model,
      api_key: payload.api_key,
      use_case: payload.use_case ? normalizeUseCaseId(payload.use_case) : undefined,
      analysis_questions: payload.analysis_questions,
    });
    return buildDemoConfigResponse(config);
  }
  const response = await authenticatedFetch(`${API_BASE}/api/v2/console/session/${sessionId}/config`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...payload,
      provider: payload.provider ? normalizeProviderId(payload.provider) : undefined,
      use_case: payload.use_case ? normalizeUseCaseId(payload.use_case) : undefined,
    }),
  });
  return parseJson(response);
}

export async function getModelProviderCatalog(): Promise<ConsoleModelProviderCatalogResponse> {
  if (isStaticDemoBootMode()) {
    return {
      providers: STATIC_MODEL_CATALOG.map((provider) => ({ ...provider })),
    };
  }
  const response = await authenticatedFetch(`${API_BASE}/api/v2/console/model/providers`);
  return parseJson(response);
}

export async function listProviderModels(
  provider: ModelProviderId,
  options: { api_key?: string; base_url?: string } = {},
): Promise<ConsoleProviderModelsResponse> {
  if (isStaticDemoBootMode()) {
    const catalog = STATIC_MODEL_CATALOG.find((entry) => entry.id === provider);
    return {
      provider,
      models: catalog ? [{ id: catalog.default_model, label: catalog.default_model }] : [],
    };
  }
  const params = new URLSearchParams();
  if (options.api_key) {
    params.set('api_key', options.api_key);
  }
  if (options.base_url) {
    params.set('base_url', options.base_url);
  }
  const query = params.toString();
  const suffix = query ? `?${query}` : '';
  const response = await authenticatedFetch(`${API_BASE}/api/v2/console/model/providers/${provider}/models${suffix}`);
  return parseJson(response);
}

export async function getSessionModelConfig(sessionId: string): Promise<ConsoleSessionModelConfigResponse> {
  if (isStaticDemoBootMode()) {
    const config = await ensureDemoSessionConfig({ session_id: sessionId });
    return buildDemoModelConfig(config);
  }
  const response = await authenticatedFetch(`${API_BASE}/api/v2/console/session/${sessionId}/model`);
  return parseJson(response);
}

export async function updateSessionModelConfig(
  sessionId: string,
  payload: ConsoleSessionModelConfigRequest,
): Promise<ConsoleSessionModelConfigResponse> {
  if (isStaticDemoBootMode()) {
    const config = await ensureDemoSessionConfig({
      session_id: sessionId,
      provider: normalizeProviderId(payload.model_provider),
      model: payload.model_name,
      embed_model_name: payload.embed_model_name,
      base_url: payload.base_url,
      api_key: payload.api_key,
      analysis_questions: payload.analysis_questions,
    });
    return buildDemoModelConfig(config);
  }
  const response = await authenticatedFetch(`${API_BASE}/api/v2/console/session/${sessionId}/model`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return parseJson(response);
}

export async function uploadKnowledgeFile(
  sessionId: string,
  file: File,
  guidingPrompt?: string,
  options?: { signal?: AbortSignal },
): Promise<KnowledgeArtifact> {
  if (isStaticDemoBootMode()) {
    return getDemoKnowledgeArtifact(sessionId);
  }
  const formData = new FormData();
  formData.append("file", file);
  if (guidingPrompt?.trim()) {
    formData.append("guiding_prompt", guidingPrompt.trim());
  }

  const response = await authenticatedFetch(`${API_BASE}/api/v2/console/session/${sessionId}/knowledge/upload`, {
    method: "POST",
    body: formData,
    signal: options?.signal,
  });
  return parseJson(response);
}

export async function processKnowledgeDocuments(
  sessionId: string,
  payload: ConsoleKnowledgeProcessRequest,
  options?: { signal?: AbortSignal },
): Promise<KnowledgeArtifact> {
  if (isStaticDemoBootMode()) {
    return getDemoKnowledgeArtifact(sessionId);
  }
  const response = await authenticatedFetch(`${API_BASE}/api/v2/console/session/${sessionId}/knowledge/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: options?.signal,
  });
  return parseJson(response);
}

export async function getKnowledgeArtifact(sessionId: string): Promise<KnowledgeArtifact | null> {
  if (isStaticDemoBootMode()) {
    return getDemoKnowledgeArtifact(sessionId);
  }
  const response = await authenticatedFetch(`${API_BASE}/api/v2/console/session/${sessionId}/knowledge`);
  if (response.status === 404 || response.status === 204) {
    return null;
  }
  const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";
  if (!contentType.includes("application/json")) {
    return null;
  }
  return parseJson(response);
}

function parseKnowledgeStreamPayload(data: string): Record<string, unknown> {
  const trimmed = String(data ?? "").trim();
  if (!trimmed) {
    return {};
  }

  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
    return { value: parsed };
  } catch {
    return { message: trimmed };
  }
}

export function subscribeKnowledgeStream(
  sessionId: string,
  handlers: {
    onEvent?: (event: KnowledgeStreamEvent) => void;
    onError?: (error: Error) => void;
    onOpen?: () => void;
  } = {},
): KnowledgeStreamSubscription | null {
  if (typeof EventSource === "undefined") {
    return null;
  }

  const source = new EventSource(`${API_BASE}/api/v2/console/session/${sessionId}/knowledge/stream`);
  const handleEvent = (name: KnowledgeStreamEventName | string) => (event: MessageEvent<string>) => {
    handlers.onEvent?.({
      name,
      payload: parseKnowledgeStreamPayload(String(event.data ?? "")),
      raw: event,
    });
  };

  const eventNames: KnowledgeStreamEventName[] = [
    "knowledge_started",
    "knowledge_document_started",
    "knowledge_chunk_started",
    "knowledge_chunk_completed",
    "knowledge_partial",
    "knowledge_completed",
    "knowledge_failed",
    "heartbeat",
  ];

  eventNames.forEach((name) => {
    source.addEventListener(name, handleEvent(name));
  });
  source.addEventListener("message", handleEvent("message"));
  source.onopen = () => handlers.onOpen?.();
  source.onerror = () => {
    handlers.onError?.(new Error("Knowledge stream disconnected."));
  };

  return {
    close: () => source.close(),
  };
}

export async function scrapeKnowledgeUrl(sessionId: string, url: string): Promise<ConsoleScrapeResponse> {
  if (isStaticDemoBootMode()) {
    return {
      url,
      title: url,
      text: url,
      length: url.length,
    };
  }
  const response = await authenticatedFetch(`${API_BASE}/api/v2/console/session/${sessionId}/scrape`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  return parseJson(response);
}

export async function getDynamicFilters(sessionId: string): Promise<ConsoleDynamicFiltersResponse> {
  const response = await authenticatedFetch(`${API_BASE}/api/v2/console/session/${sessionId}/filters`);
  return parseJson(response);
}

export async function getTokenUsageEstimate(
  sessionId: string,
  agents: number,
  rounds: number,
): Promise<TokenUsageEstimateResponse> {
  const params = new URLSearchParams({
    agents: String(agents),
    rounds: String(rounds),
  });
  const response = await authenticatedFetch(`${API_BASE}/api/v2/token-usage/${sessionId}/estimate?${params.toString()}`);
  return parseJson(response);
}

export async function getTokenUsageRuntime(sessionId: string): Promise<TokenUsageRuntimeResponse> {
  const response = await authenticatedFetch(`${API_BASE}/api/v2/token-usage/${sessionId}`);
  return parseJson(response);
}

export async function previewPopulation(
  sessionId: string,
  payload: {
    agent_count: number;
    sample_mode: "affected_groups" | "population_baseline";
    sampling_instructions?: string;
    seed?: number;
    min_age?: number;
    max_age?: number;
    planning_areas?: string[];
    dynamic_filters?: Record<string, unknown>;
  },
): Promise<PopulationArtifact> {
  if (isStaticDemoBootMode()) {
    return getDemoPopulationArtifact(sessionId);
  }
  const response = await authenticatedFetch(`${API_BASE}/api/v2/console/session/${sessionId}/sampling/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJson(response);
}

export async function startSimulation(
  sessionId: string,
  payload: {
    subject_summary: string;
    rounds: number;
    controversy_boost?: number;
    mode?: ConsoleMode;
  },
): Promise<SimulationState> {
  if (isStaticDemoBootMode()) {
    return getDemoSimulationStatePayload(sessionId);
  }
  const simulateResponse = await authenticatedFetch(`${API_BASE}/api/v2/console/session/${sessionId}/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      subject_summary: payload.subject_summary,
      rounds: payload.rounds,
      controversy_boost: payload.controversy_boost ?? 0,
      mode: payload.mode,
    }),
  });
  return parseJson(simulateResponse);
}

export async function getSimulationState(sessionId: string): Promise<SimulationState> {
  if (isStaticDemoBootMode()) {
    return getDemoSimulationStatePayload(sessionId);
  }
  const response = await authenticatedFetch(`${API_BASE}/api/v2/console/session/${sessionId}/simulation/state`);
  return parseJson(response);
}

export async function getSimulationMetrics(sessionId: string): Promise<Record<string, unknown>> {
  if (isStaticDemoBootMode()) {
    const state = await getDemoSimulationStatePayload(sessionId);
    return {
      ...state.latest_metrics,
      ...state.counters,
    };
  }
  const response = await authenticatedFetch(`${API_BASE}/api/v2/console/session/${sessionId}/simulation/metrics`);
  return parseJson(response);
}

export function buildSimulationStreamUrl(sessionId: string): string {
  return `${API_BASE}/api/v2/console/session/${sessionId}/simulation/stream`;
}

export async function generateReport(sessionId: string): Promise<StructuredReportState> {
  if (isStaticDemoBootMode()) {
    return getDemoReportPayload(sessionId);
  }
  const response = await authenticatedFetch(`${API_BASE}/api/v2/console/session/${sessionId}/report/generate`, {
    method: "POST",
  });
  return parseJson(response);
}

export async function getStructuredReport(sessionId: string): Promise<StructuredReportState> {
  if (isStaticDemoBootMode()) {
    return getDemoReportPayload(sessionId);
  }
  const response = await authenticatedFetch(`${API_BASE}/api/v2/console/session/${sessionId}/report`);
  return parseJson(response);
}

export async function exportReportDocx(sessionId: string): Promise<Blob> {
  if (isStaticDemoBootMode()) {
    throw new Error("Report export is unavailable in demo-static mode.");
  }
  const response = await authenticatedFetch(`${API_BASE}/api/v2/console/session/${sessionId}/report/export`);
  await ensureResponseOk(response);
  return response.blob();
}

export async function generateQuestionMetadata(
  question: string,
  useCase?: string,
): Promise<Record<string, unknown>> {
  if (isStaticDemoBootMode()) {
    return buildStaticQuestionMetadata(question);
  }
  const response = await authenticatedFetch(`${API_BASE}/api/v2/questions/generate-metadata`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, use_case: useCase }),
  });
  return parseJson(response);
}

export async function getAnalysisQuestions(
  sessionId: string,
): Promise<{ session_id: string; use_case: string; questions: Array<Record<string, unknown>> }> {
  if (isStaticDemoBootMode()) {
    const config = await ensureDemoSessionConfig({ session_id: sessionId });
    return {
      session_id: config.session_id,
      use_case: config.use_case,
      questions: config.analysis_questions.map((question) => ({ ...question })),
    };
  }
  const response = await authenticatedFetch(`${API_BASE}/api/v2/session/${sessionId}/analysis-questions`);
  return parseJson(response);
}

export async function sendGroupChatMessage(
  sessionId: string,
  payload: { segment: string; message: string; metric_name?: string; top_n?: number },
): Promise<ConsoleGroupChatResponse> {
  if (isStaticDemoBootMode()) {
    const agents = await getDemoAgentRecords();
    const normalizedSegment = String(payload.segment ?? "").toLowerCase();
    const desiredSentiment = normalizedSegment.startsWith("support") ? "positive" : normalizedSegment.startsWith("dissent") ? "negative" : "neutral";
    const responders = agents
      .filter((agent) => agent.sentiment === desiredSentiment)
      .sort((left, right) => right.influence_score - left.influence_score)
      .slice(0, payload.top_n ?? 5);
    return {
      session_id: sessionId,
      responses: responders.map((agent) => ({
        agent_id: agent.agent_id,
        agent_name: agent.agent_name,
        content: buildDemoChatContent(agent),
      })),
    };
  }
  const response = await fetchChatWithTimeout(`${API_BASE}/api/v2/console/session/${sessionId}/chat/group`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (response.ok) {
    return normalizeGroupChatPayload(await response.json());
  }
  return normalizeGroupChatPayload(await parseJson<Record<string, unknown>>(response));
}

export async function getGroupChatAgents(
  sessionId: string,
  payload: { segment: string; metric_name?: string; top_n?: number },
): Promise<ConsoleGroupChatAgentsResponse> {
  if (isStaticDemoBootMode()) {
    const agents = await getDemoAgentRecords();
    const normalizedSegment = String(payload.segment ?? "").toLowerCase();
    const desiredSentiment = normalizedSegment.startsWith("support") ? "positive" : normalizedSegment.startsWith("dissent") ? "negative" : "neutral";
    const responders = agents
      .filter((agent) => agent.sentiment === desiredSentiment)
      .sort((left, right) => right.influence_score - left.influence_score)
      .slice(0, payload.top_n ?? 5);
    return {
      session_id: sessionId,
      segment: payload.segment,
      metric_name: payload.metric_name ?? null,
      score_field: "approval_score",
      agents: responders.map((agent) => ({
        agent_id: agent.agent_id,
        agent_name: agent.agent_name,
        influence_score: agent.influence_score,
        score: agent.metric_score,
      })),
    };
  }
  const url = new URL(`${API_BASE}/api/v2/console/session/${sessionId}/chat/group/agents`);
  url.searchParams.set("segment", payload.segment);
  if (payload.metric_name) url.searchParams.set("metric_name", payload.metric_name);
  if (payload.top_n) url.searchParams.set("top_n", String(payload.top_n));
  const response = await authenticatedFetch(url.toString());
  return parseJson(response);
}

export async function sendAgentChatMessage(
  sessionId: string,
  payload: { agent_id: string; message: string },
): Promise<ConsoleAgentChatResponse> {
  if (isStaticDemoBootMode()) {
    const agent = (await getDemoAgentLookup()).get(payload.agent_id);
    if (!agent) {
      return {
        session_id: sessionId,
        agent_id: payload.agent_id,
        responses: [],
      };
    }
    return {
      session_id: sessionId,
      agent_id: payload.agent_id,
      responses: [
        {
          agent_id: agent.agent_id,
          agent_name: agent.agent_name,
          content: buildDemoChatContent(agent),
        },
      ],
    };
  }
  const response = await fetchChatWithTimeout(`${API_BASE}/api/v2/console/session/${sessionId}/chat/agent/${payload.agent_id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: payload.message }),
  });

  if (response.ok) {
    return normalizeAgentChatPayload(payload.agent_id, await response.json());
  }
  return normalizeAgentChatPayload(payload.agent_id, await parseJson<Record<string, unknown>>(response));
}

export async function getAnalyticsPolarization(sessionId: string, metricName?: string): Promise<Record<string, unknown>> {
  if (isStaticDemoBootMode()) {
    const demo = await loadBundledDemoOutput();
    return { ...resolveDemoAnalyticsPayload(demo, "polarization", metricName) };
  }
  const url = new URL(`${API_BASE}/api/v2/console/session/${sessionId}/analytics/polarization`);
  if (metricName) url.searchParams.set("metric_name", metricName);
  const response = await authenticatedFetch(url.toString());
  return parseJson(response);
}

export async function getAnalyticsOpinionFlow(sessionId: string, metricName?: string): Promise<Record<string, unknown>> {
  if (isStaticDemoBootMode()) {
    const demo = await loadBundledDemoOutput();
    return { ...resolveDemoAnalyticsPayload(demo, "opinion_flow", metricName) };
  }
  const url = new URL(`${API_BASE}/api/v2/console/session/${sessionId}/analytics/opinion-flow`);
  if (metricName) url.searchParams.set("metric_name", metricName);
  const response = await authenticatedFetch(url.toString());
  return parseJson(response);
}

export async function getAnalyticsInfluence(sessionId: string): Promise<Record<string, unknown>> {
  if (isStaticDemoBootMode()) {
    const demo = await loadBundledDemoOutput();
    return { ...((demo.analytics?.influence as Record<string, unknown> | undefined) ?? {}) };
  }
  const response = await authenticatedFetch(`${API_BASE}/api/v2/console/session/${sessionId}/analytics/influence`);
  return parseJson(response);
}

export async function getAnalyticsCascades(sessionId: string): Promise<Record<string, unknown>> {
  if (isStaticDemoBootMode()) {
    const demo = await loadBundledDemoOutput();
    return { ...((demo.analytics?.cascades as Record<string, unknown> | undefined) ?? {}) };
  }
  const response = await authenticatedFetch(`${API_BASE}/api/v2/console/session/${sessionId}/analytics/cascades`);
  return parseJson(response);
}

export async function getAnalyticsAgentStances(sessionId: string, metricName?: string): Promise<Record<string, unknown>> {
  if (isStaticDemoBootMode()) {
    const demo = await loadBundledDemoOutput();
    const cached = resolveDemoAnalyticsPayload(demo, "agent_stances", metricName);
    if (Object.keys(cached).length > 0) {
      return { ...cached };
    }
    const agents = await getDemoAgentRecords();
    return {
      session_id: sessionId,
      metric_name: metricName ?? null,
      score_field: "approval_score",
      stances: agents.map((agent) => ({
        agent_id: agent.agent_id,
        score: agent.metric_score,
      })),
    };
  }
  const url = new URL(`${API_BASE}/api/v2/console/session/${sessionId}/analytics/agent-stances`);
  if (metricName) url.searchParams.set("metric_name", metricName);
  const response = await authenticatedFetch(url.toString());
  return parseJson(response);
}

async function ensureResponseOk(response: Response): Promise<void> {
  if (response.ok) {
    return;
  }
  let detail = `${response.status} ${response.statusText}`;
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") {
      detail = body.detail;
    } else if (typeof body?.message === "string") {
      detail = body.message;
    } else {
      detail = JSON.stringify(body);
    }
  } catch {
    const text = await response.text();
    if (text) {
      detail = text;
    }
  }
  throw new Error(detail);
}

function normalizeGroupChatPayload(payload: Record<string, unknown>): ConsoleGroupChatResponse {
  return {
    session_id: String(payload.session_id ?? ""),
    responses: normalizeChatResponses(payload),
  };
}

function normalizeAgentChatPayload(
  fallbackAgentId: string,
  payload: Record<string, unknown>,
): ConsoleAgentChatResponse {
  const agentId = String(payload.agent_id ?? fallbackAgentId);
  const responses = normalizeChatResponses(payload);
  return {
    session_id: String(payload.session_id ?? ""),
    agent_id: agentId,
    responses:
      responses.length > 0
        ? responses.map((entry) => ({
            ...entry,
            agent_id: entry.agent_id ?? agentId,
          }))
        : [],
  };
}

function normalizeChatResponses(payload: Record<string, unknown>): ConsoleChatResponseMessage[] {
  const listCandidate = payload.responses ?? payload.messages;
  if (Array.isArray(listCandidate)) {
    return listCandidate
      .map((row) => normalizeChatResponseEntry(row))
      .filter((row): row is ConsoleChatResponseMessage => Boolean(row));
  }

  const single = normalizeChatResponseEntry(payload);
  if (single) {
    return [single];
  }
  return [];
}

function normalizeChatResponseEntry(value: unknown): ConsoleChatResponseMessage | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const row = value as Record<string, unknown>;
  const contentCandidate = row.content ?? row.response ?? row.message ?? row.text;
  const content = String(contentCandidate ?? "").trim();
  if (!content) {
    return null;
  }
  return {
    content,
    agent_id: row.agent_id ? String(row.agent_id) : row.id ? String(row.id) : undefined,
    agent_name: row.agent_name ? String(row.agent_name) : row.name ? String(row.name) : undefined,
  };
}
