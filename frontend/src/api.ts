export type RunSimulationPayload = {
  simulation_id: string;
  policy_summary: string;
  agent_count: number;
  rounds: number;
  planning_areas?: string[];
  min_age?: number;
  max_age?: number;
};

export type KnowledgeProcessPayload = {
  simulation_id: string;
  document_text?: string;
  source_path?: string;
  demographic_focus?: string;
  use_default_demo_document?: boolean;
};

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://localhost:8000';

export async function runSimulation(payload: RunSimulationPayload) {
  const response = await fetch(`${API_BASE}/api/v1/phase-b/simulations/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function processKnowledge(payload: KnowledgeProcessPayload) {
  const response = await fetch(`${API_BASE}/api/v1/phase-a/knowledge/process`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function syncMemory(simulationId: string) {
  const response = await fetch(`${API_BASE}/api/v1/phase-c/memory/sync`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ simulation_id: simulationId }),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function getDashboard(simulationId: string) {
  const response = await fetch(`${API_BASE}/api/v1/phase-e/dashboard/${simulationId}`);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function reportChat(simulationId: string, message: string) {
  const response = await fetch(`${API_BASE}/api/v1/phase-d/report/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ simulation_id: simulationId, message }),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function agentChat(simulationId: string, agentId: string, message: string) {
  const response = await fetch(`${API_BASE}/api/v1/phase-c/chat/agent`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ simulation_id: simulationId, agent_id: agentId, message }),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function getAgentMemory(simulationId: string, agentId: string) {
  const response = await fetch(`${API_BASE}/api/v1/phase-c/memory/${simulationId}/${agentId}`);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function loadStaticDemoOutput() {
  const response = await fetch('/demo-output.json');
  if (!response.ok) {
    throw new Error('Static demo output not found');
  }
  return response.json();
}

export async function getPlanningAreaGeoJson() {
  const live = await fetch(`${API_BASE}/api/v1/phase-e/geo/planning-areas`);
  if (live.ok) {
    return live.json();
  }

  const cached = await fetch('/planning-area-boundaries.geojson');
  if (!cached.ok) {
    throw new Error('Planning area GeoJSON unavailable');
  }
  return cached.json();
}
