export type ConsoleMode = "demo" | "live";
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
    planning_areas: string[];
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
    planning_area_distribution?: Record<string, number>;
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

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

export function isLiveBootMode(): boolean {
  return import.meta.env.VITE_BOOT_MODE === "live";
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

export interface StructuredReportState {
  session_id: string;
  status: string;
  generated_at?: string | null;
  executive_summary?: string | null;
  quick_stats?: Record<string, unknown>;
  metric_deltas?: Array<Record<string, unknown>>;
  sections?: Array<Record<string, unknown>>;
  insight_blocks?: Array<Record<string, unknown>>;
  preset_sections?: Array<Record<string, unknown>>;
  insight_cards: Array<Record<string, unknown>>;
  support_themes: Array<Record<string, unknown>>;
  dissent_themes: Array<Record<string, unknown>>;
  demographic_breakdown: Array<Record<string, unknown>>;
  influential_content: Array<Record<string, unknown>>;
  recommendations: Array<Record<string, unknown>>;
  risks: Array<Record<string, unknown>>;
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

export interface ConsoleAgentChatResponse {
  session_id: string;
  agent_id?: string;
  responses: ConsoleChatResponseMessage[];
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
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (error) {
    const isAbortError =
      (error instanceof DOMException && error.name === "AbortError")
      || (error instanceof Error && error.name === "AbortError");
    if (isAbortError) {
      throw new Error(
        `Live chat timed out after ${Math.round(timeoutMs / 1000)} seconds while waiting for backend memory retrieval. `
        + "Please retry and check backend Graphiti/FalkorDB health.",
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
  const response = await fetch(`${API_BASE}/api/v2/console/session`, {
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
  const response = await fetch(`${API_BASE}/api/v2/countries`);
  return parseJson(response);
}

export async function getV2Providers(): Promise<V2ProviderResponse[]> {
  const response = await fetch(`${API_BASE}/api/v2/providers`);
  return parseJson(response);
}

export async function createV2Session(payload: V2SessionCreateRequest): Promise<V2SessionCreateResponse> {
  const response = await fetch(`${API_BASE}/api/v2/session/create`, {
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
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/config`, {
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
  const response = await fetch(`${API_BASE}/api/v2/console/model/providers`);
  return parseJson(response);
}

export async function listProviderModels(
  provider: ModelProviderId,
  options: { api_key?: string; base_url?: string } = {},
): Promise<ConsoleProviderModelsResponse> {
  const params = new URLSearchParams();
  if (options.api_key) {
    params.set('api_key', options.api_key);
  }
  if (options.base_url) {
    params.set('base_url', options.base_url);
  }
  const query = params.toString();
  const suffix = query ? `?${query}` : '';
  const response = await fetch(`${API_BASE}/api/v2/console/model/providers/${provider}/models${suffix}`);
  return parseJson(response);
}

export async function getSessionModelConfig(sessionId: string): Promise<ConsoleSessionModelConfigResponse> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/model`);
  return parseJson(response);
}

export async function updateSessionModelConfig(
  sessionId: string,
  payload: ConsoleSessionModelConfigRequest,
): Promise<ConsoleSessionModelConfigResponse> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/model`, {
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
): Promise<KnowledgeArtifact> {
  const formData = new FormData();
  formData.append("file", file);
  if (guidingPrompt?.trim()) {
    formData.append("guiding_prompt", guidingPrompt.trim());
  }

  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/knowledge/upload`, {
    method: "POST",
    body: formData,
  });
  return parseJson(response);
}

export async function processKnowledgeDocuments(
  sessionId: string,
  payload: ConsoleKnowledgeProcessRequest,
): Promise<KnowledgeArtifact> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/knowledge/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJson(response);
}

export async function scrapeKnowledgeUrl(sessionId: string, url: string): Promise<ConsoleScrapeResponse> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/scrape`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  return parseJson(response);
}

export async function getDynamicFilters(sessionId: string): Promise<ConsoleDynamicFiltersResponse> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/filters`);
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
  const response = await fetch(`${API_BASE}/api/v2/token-usage/${sessionId}/estimate?${params.toString()}`);
  return parseJson(response);
}

export async function getTokenUsageRuntime(sessionId: string): Promise<TokenUsageRuntimeResponse> {
  const response = await fetch(`${API_BASE}/api/v2/token-usage/${sessionId}`);
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
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/sampling/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJson(response);
}

export async function startSimulation(
  sessionId: string,
  payload: {
    policy_summary: string;
    rounds: number;
    controversy_boost?: number;
    mode?: ConsoleMode;
  },
): Promise<SimulationState> {
  const simulateResponse = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      rounds: payload.rounds,
      controversy_boost: payload.controversy_boost ?? 0,
      mode: payload.mode,
    }),
  });
  return parseJson(simulateResponse);
}

export async function getSimulationState(sessionId: string): Promise<SimulationState> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/simulation/state`);
  return parseJson(response);
}

export async function getSimulationMetrics(sessionId: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/simulation/metrics`);
  return parseJson(response);
}

export function buildSimulationStreamUrl(sessionId: string): string {
  return `${API_BASE}/api/v2/console/session/${sessionId}/simulation/stream`;
}

export async function generateReport(sessionId: string): Promise<StructuredReportState> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/report/generate`, {
    method: "POST",
  });
  return parseJson(response);
}

export async function getStructuredReport(sessionId: string): Promise<StructuredReportState> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/report`);
  return parseJson(response);
}

export async function exportReportDocx(sessionId: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/report/export`);
  await ensureResponseOk(response);
  return response.blob();
}

export async function generateQuestionMetadata(
  question: string,
  useCase?: string,
): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE}/api/v2/questions/generate-metadata`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, use_case: useCase }),
  });
  return parseJson(response);
}

export async function getAnalysisQuestions(
  sessionId: string,
): Promise<{ session_id: string; use_case: string; questions: Array<Record<string, unknown>> }> {
  const response = await fetch(`${API_BASE}/api/v2/session/${sessionId}/analysis-questions`);
  return parseJson(response);
}

export async function sendGroupChatMessage(
  sessionId: string,
  payload: { segment: string; message: string; metric_name?: string },
): Promise<ConsoleGroupChatResponse> {
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

export async function sendAgentChatMessage(
  sessionId: string,
  payload: { agent_id: string; message: string },
): Promise<ConsoleAgentChatResponse> {
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
  const url = new URL(`${API_BASE}/api/v2/console/session/${sessionId}/analytics/polarization`);
  if (metricName) url.searchParams.set("metric_name", metricName);
  const response = await fetch(url.toString());
  return parseJson(response);
}

export async function getAnalyticsOpinionFlow(sessionId: string, metricName?: string): Promise<Record<string, unknown>> {
  const url = new URL(`${API_BASE}/api/v2/console/session/${sessionId}/analytics/opinion-flow`);
  if (metricName) url.searchParams.set("metric_name", metricName);
  const response = await fetch(url.toString());
  return parseJson(response);
}

export async function getAnalyticsInfluence(sessionId: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/analytics/influence`);
  return parseJson(response);
}

export async function getAnalyticsCascades(sessionId: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/analytics/cascades`);
  return parseJson(response);
}

export async function getAnalyticsAgentStances(sessionId: string, metricName?: string): Promise<Record<string, unknown>> {
  const url = new URL(`${API_BASE}/api/v2/console/session/${sessionId}/analytics/agent-stances`);
  if (metricName) url.searchParams.set("metric_name", metricName);
  const response = await fetch(url.toString());
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
