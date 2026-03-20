export type ScreenKey =
  | 'stage-1'
  | 'stage-2'
  | 'stage-3'
  | 'stage-4-report'
  | 'stage-4-opinions'
  | 'stage-4-friction'
  | 'stage-5-hub';

export type ConsoleMode = 'demo' | 'live';
export type GraphView = 'knowledge' | 'agent';

export type ConsoleSession = {
  session_id: string;
  mode: ConsoleMode;
  status: string;
};

export type KnowledgeArtifact = {
  session_id: string;
  document: {
    document_id: string;
    source_path?: string | null;
    text_length: number;
  };
  summary: string;
  entity_nodes: Array<{ id: string; label: string; type: string }>;
  relationship_edges: Array<{ source: string; target: string; type: string }>;
  entity_type_counts: Record<string, number>;
  processing_logs: string[];
  demographic_focus_summary?: string | null;
};

export type ChatTranscriptEntry = {
  role: string;
  content: string;
  created_at?: string;
  agent_id?: string | null;
};

export type InfluentialAgent = Record<string, unknown> & {
  agent_id: string;
  planning_area?: string | null;
  latest_argument?: string | null;
  influence_score?: number | null;
  transcript?: ChatTranscriptEntry[];
  recent_memory?: Array<Record<string, unknown>>;
  persona?: Record<string, unknown>;
};

export type PopulationSample = {
  agent_id: string;
  persona: Record<string, unknown>;
  selection_reason: Record<string, number>;
};

export type PopulationArtifact = {
  session_id: string;
  candidate_count: number;
  sample_count: number;
  coverage: {
    planning_areas: string[];
    age_buckets: Record<string, number>;
  };
  sampled_personas: PopulationSample[];
  agent_graph: {
    nodes: Array<Record<string, unknown>>;
    links: Array<Record<string, unknown>>;
  };
  representativeness: Record<string, unknown>;
};

export type SimulationEvent = {
  id?: number;
  event_type: string;
  session_id: string;
  round_no?: number;
  actor_agent_id?: string;
  content?: string;
  reaction?: string;
  post_id?: string | number;
  metrics?: Record<string, number>;
  timestamp?: string;
};

export type SimulationState = {
  session_id: string;
  status: string;
  event_count: number;
  last_round: number;
  latest_metrics: Record<string, unknown>;
  recent_events: SimulationEvent[];
};

export type ReportFull = {
  session_id: string;
  report: Record<string, unknown>;
};

export type ReportOpinions = {
  session_id: string;
  feed: Array<Record<string, unknown>>;
  influential_agents: InfluentialAgent[];
};

export type ReportFrictionMap = {
  session_id: string;
  map_metrics: Array<Record<string, unknown>>;
  anomaly_summary: string;
};

export type InteractionHub = {
  session_id: string;
  selected_agent_id?: string | null;
  report_agent: {
    starter_prompt?: string | null;
    transcript?: ChatTranscriptEntry[];
  } & Record<string, unknown>;
  influential_agents: InfluentialAgent[];
  selected_agent?: InfluentialAgent | null;
};

export type ConsoleReportChatResponse = {
  session_id: string;
  response: string;
  gemini_model: string;
  zep_context_used: boolean;
};

export type ConsoleAgentChatResponse = {
  session_id: string;
  agent_id: string;
  response: string;
  memory_used: boolean;
  gemini_model: string;
  zep_context_used: boolean;
};

export type DemoBundle = {
  session: ConsoleSession;
  knowledge: KnowledgeArtifact | null;
  population: PopulationArtifact | null;
  simulationState: SimulationState | null;
  reportFull: ReportFull | null;
  reportOpinions: ReportOpinions | null;
  reportFriction: ReportFrictionMap | null;
  interactionHub: InteractionHub | null;
};
