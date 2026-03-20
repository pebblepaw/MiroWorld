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
