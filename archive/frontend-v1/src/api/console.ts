import type {
  ConsoleMode,
  ConsoleAgentChatResponse,
  ConsoleReportChatResponse,
  ConsoleSession,
  DemoBundle,
  InteractionHub,
  KnowledgeArtifact,
  PopulationArtifact,
  ReportFrictionMap,
  ReportFull,
  ReportOpinions,
  SimulationEvent,
  SimulationState,
} from '../types/console';

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://localhost:8000';

async function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export function createSession(sessionId: string, mode: ConsoleMode) {
  return jsonFetch<ConsoleSession>(`${API_BASE}/api/v2/console/session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, mode }),
  });
}

export function processKnowledge(
  sessionId: string,
  payload: { documentText?: string; demographicFocus?: string; useDefaultDemoDocument?: boolean },
) {
  return jsonFetch<KnowledgeArtifact>(`${API_BASE}/api/v2/console/session/${sessionId}/knowledge/process`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      document_text: payload.documentText,
      demographic_focus: payload.demographicFocus,
      use_default_demo_document: payload.useDefaultDemoDocument ?? false,
    }),
  });
}

export function uploadKnowledge(
  sessionId: string,
  payload: { file: File; demographicFocus?: string },
) {
  const formData = new FormData();
  formData.append('file', payload.file);
  if (payload.demographicFocus) {
    formData.append('demographic_focus', payload.demographicFocus);
  }
  return jsonFetch<KnowledgeArtifact>(`${API_BASE}/api/v2/console/session/${sessionId}/knowledge/upload`, {
    method: 'POST',
    body: formData,
  });
}

export function previewPopulation(
  sessionId: string,
  payload: {
    agentCount: number;
    minAge?: number;
    maxAge?: number;
    planningAreas?: string[];
    incomeBrackets?: string[];
  },
) {
  return jsonFetch<PopulationArtifact>(`${API_BASE}/api/v2/console/session/${sessionId}/sampling/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      agent_count: payload.agentCount,
      min_age: payload.minAge,
      max_age: payload.maxAge,
      planning_areas: payload.planningAreas ?? [],
      income_brackets: payload.incomeBrackets ?? [],
    }),
  });
}

export function startSimulation(sessionId: string, payload: { policySummary: string; rounds: number; mode: ConsoleMode }) {
  return jsonFetch<SimulationState>(`${API_BASE}/api/v2/console/session/${sessionId}/simulation/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      policy_summary: payload.policySummary,
      rounds: payload.rounds,
      mode: payload.mode,
    }),
  });
}

export function getSimulationState(sessionId: string) {
  return jsonFetch<SimulationState>(`${API_BASE}/api/v2/console/session/${sessionId}/simulation/state`);
}

export function subscribeSimulationStream(
  sessionId: string,
  onEvent: (event: SimulationEvent) => void,
  onOpen?: () => void,
  onError?: () => void,
) {
  const source = new EventSource(`${API_BASE}/api/v2/console/session/${sessionId}/simulation/stream`);
  source.onopen = () => onOpen?.();
  source.onerror = () => onError?.();
  const handler = (event: MessageEvent) => {
    try {
      onEvent(JSON.parse(event.data) as SimulationEvent);
    } catch {
      // ignore heartbeat
    }
  };
  source.onmessage = handler;
  source.addEventListener('post_created', handler);
  source.addEventListener('comment_created', handler);
  source.addEventListener('reaction_added', handler);
  source.addEventListener('metrics_updated', handler);
  source.addEventListener('round_started', handler);
  source.addEventListener('round_completed', handler);
  source.addEventListener('run_started', handler);
  source.addEventListener('run_completed', handler);
  return () => source.close();
}

export function getReportFull(sessionId: string) {
  return jsonFetch<ReportFull>(`${API_BASE}/api/v2/console/session/${sessionId}/report/full`);
}

export function getReportOpinions(sessionId: string) {
  return jsonFetch<ReportOpinions>(`${API_BASE}/api/v2/console/session/${sessionId}/report/opinions`);
}

export function getReportFrictionMap(sessionId: string) {
  return jsonFetch<ReportFrictionMap>(`${API_BASE}/api/v2/console/session/${sessionId}/report/friction-map`);
}

export function getInteractionHub(sessionId: string, agentId?: string) {
  const query = agentId ? `?agent_id=${encodeURIComponent(agentId)}` : '';
  return jsonFetch<InteractionHub>(`${API_BASE}/api/v2/console/session/${sessionId}/interaction-hub${query}`);
}

export function postReportChat(sessionId: string, message: string) {
  return jsonFetch<ConsoleReportChatResponse>(`${API_BASE}/api/v2/console/session/${sessionId}/interaction-hub/report-chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
}

export function postAgentChat(sessionId: string, agentId: string, message: string) {
  return jsonFetch<ConsoleAgentChatResponse>(`${API_BASE}/api/v2/console/session/${sessionId}/interaction-hub/agent-chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ agent_id: agentId, message }),
  });
}

export async function getPlanningAreaGeoJson() {
  const live = await fetch(`${API_BASE}/api/v1/phase-e/geo/planning-areas`);
  if (live.ok) {
    return live.json();
  }
  return jsonFetch('/planning-area-boundaries.geojson');
}

export async function loadDemoBundle(): Promise<DemoBundle> {
  const raw = await jsonFetch<any>('/demo-output.json');
  if (raw.session && raw.knowledge && raw.population) {
    return raw as DemoBundle;
  }

  const sessionId = raw.simulation_id ?? 'demo-budget-2026';
  const friction = raw.report?.friction_by_planning_area ?? [];
  const influential = raw.report?.influential_agents ?? [];
  const topPosts = raw.dashboard?.simulation?.top_posts ?? [];
  return {
    session: { session_id: sessionId, mode: 'demo', status: 'created' },
    knowledge: {
      session_id: sessionId,
      document: {
        document_id: 'demo-doc',
        source_path: raw.knowledge?.document ?? 'Sample_Inputs/fy2026_budget_statement.md',
        text_length: String(raw.report?.executive_summary ?? '').length,
      },
      summary: raw.report?.executive_summary ?? 'Cached McKAInsey demo knowledge summary.',
      entity_nodes: [
        { id: 'doc:policy', label: 'Policy Document', type: 'policy' },
        ...friction.slice(0, 5).map((row: any) => ({
          id: `area:${String(row.planning_area).toLowerCase()}`,
          label: String(row.planning_area),
          type: 'planning_area',
        })),
      ],
      relationship_edges: friction.slice(0, 5).map((row: any) => ({
        source: 'doc:policy',
        target: `area:${String(row.planning_area).toLowerCase()}`,
        type: 'impacts_area',
      })),
      entity_type_counts: {
        policy: 1,
        planning_area: friction.slice(0, 5).length,
      },
      processing_logs: ['Loaded cached knowledge artifact', 'Adapted legacy demo bundle'],
      demographic_focus_summary: raw.knowledge?.reason ?? 'Cached budget impact by planning area',
    },
    population: {
      session_id: sessionId,
      candidate_count: influential.length,
      sample_count: influential.length,
      coverage: {
        planning_areas: [...new Set(influential.map((agent: any) => agent.planning_area ?? 'Unknown'))],
        age_buckets: {},
      },
      sampled_personas: influential.map((agent: any, index: number) => ({
        agent_id: agent.agent_id ?? `agent-${index + 1}`,
        persona: {
          planning_area: agent.planning_area ?? 'Unknown',
          income_bracket: agent.income_bracket ?? 'Unknown',
          occupation: agent.occupation ?? 'Unknown',
        },
        selection_reason: {
          score: Number(agent.influence_score ?? 0.6),
          semantic_relevance: 0.7,
          geographic_relevance: 0.8,
          socioeconomic_relevance: 0.6,
          digital_behavior_relevance: 0.5,
          filter_alignment: 1,
        },
      })),
      agent_graph: {
        nodes: influential.map((agent: any, index: number) => ({
          id: agent.agent_id ?? `agent-${index + 1}`,
          label: agent.agent_id ?? `Agent ${index + 1}`,
          planning_area: agent.planning_area ?? 'Unknown',
          score: agent.influence_score ?? 0.6,
        })),
        links: [],
      },
      representativeness: { status: 'cached-demo' },
    },
    simulationState: {
      session_id: sessionId,
      status: 'completed',
      event_count: topPosts.length,
      last_round: raw.simulation?.rounds ?? 10,
      latest_metrics: {
        approval_pre: raw.simulation?.stage3a_approval_rate ?? 0,
        approval_post: raw.simulation?.stage3b_approval_rate ?? 0,
      },
      recent_events: topPosts.map((post: any, index: number) => ({
        event_type: 'post_created',
        session_id: sessionId,
        round_no: 1,
        actor_agent_id: post.actor_agent_id ?? `agent-${index + 1}`,
        content: post.content ?? 'Simulation feed item',
      })),
    },
    reportFull: {
      session_id: sessionId,
      report: raw.report ?? {},
    },
    reportOpinions: {
      session_id: sessionId,
      feed:
        topPosts.length > 0
          ? topPosts
          : [...(raw.report?.key_arguments_for ?? []), ...(raw.report?.key_arguments_against ?? [])].slice(0, 12),
      influential_agents: influential,
    },
    reportFriction: {
      session_id: sessionId,
      map_metrics: friction,
      anomaly_summary: friction[0]?.planning_area
        ? `Highest observed friction cluster: ${friction[0].planning_area}`
        : 'No friction anomalies in cached run.',
    },
    interactionHub: {
      session_id: sessionId,
      selected_agent_id: influential[0]?.agent_id ?? null,
      report_agent: {
        starter_prompt: raw.report_chat?.response ?? 'Ask about the most dissenting groups or mitigation options.',
        transcript: [],
      },
      influential_agents: influential,
      selected_agent: influential[0]
        ? {
            ...influential[0],
            transcript: [],
            recent_memory: [],
          }
        : null,
    },
  };
}
