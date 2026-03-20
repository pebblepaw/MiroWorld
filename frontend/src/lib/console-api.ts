export type ConsoleMode = "demo" | "live";

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

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      detail = body.detail || JSON.stringify(body);
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

export async function createConsoleSession(mode: ConsoleMode = DEFAULT_MODE): Promise<{ session_id: string; mode: ConsoleMode; status: string }> {
  const response = await fetch(`${API_BASE}/api/v2/console/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
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
