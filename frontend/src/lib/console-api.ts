export type ConsoleMode = "demo" | "live";
export type ModelProviderId = "google" | "openrouter" | "openai" | "ollama";

export interface ConsoleSessionModelConfigRequest {
  model_provider: ModelProviderId;
  model_name: string;
  embed_model_name?: string;
  api_key?: string;
  base_url?: string;
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
const DEFAULT_MODE: ConsoleMode = import.meta.env.VITE_BOOT_MODE === "live" ? "live" : "demo";

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
  insight_cards: Array<Record<string, unknown>>;
  support_themes: Array<Record<string, unknown>>;
  dissent_themes: Array<Record<string, unknown>>;
  demographic_breakdown: Array<Record<string, unknown>>;
  influential_content: Array<Record<string, unknown>>;
  recommendations: Array<Record<string, unknown>>;
  risks: Array<Record<string, unknown>>;
  error?: string | null;
}

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

export async function createConsoleSession(
  mode: ConsoleMode = DEFAULT_MODE,
  modelConfig: Partial<ConsoleSessionModelConfigRequest> = {},
): Promise<ConsoleSessionResponse> {
  const response = await fetch(`${API_BASE}/api/v2/console/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode, ...modelConfig }),
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

export async function previewPopulation(
  sessionId: string,
  payload: {
    agent_count: number;
    sample_mode: "affected_groups" | "population_baseline";
    sampling_instructions?: string;
    seed?: number;
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
    mode?: ConsoleMode;
  },
): Promise<SimulationState> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/simulation/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJson(response);
}

export async function getSimulationState(sessionId: string): Promise<SimulationState> {
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/simulation/state`);
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
  const response = await fetch(`${API_BASE}/api/v2/console/session/${sessionId}/report/full`);
  return parseJson(response);
}
