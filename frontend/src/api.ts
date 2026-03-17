export type RunSimulationPayload = {
  simulation_id: string;
  policy_summary: string;
  agent_count: number;
  rounds: number;
  planning_areas?: string[];
  min_age?: number;
  max_age?: number;
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
