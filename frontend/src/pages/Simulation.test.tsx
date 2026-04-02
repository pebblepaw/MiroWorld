import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Simulation from "@/pages/Simulation";
import { AppProvider, useApp } from "@/contexts/AppContext";

class MockEventSource {
  static instances: MockEventSource[] = [];

  url: string;
  listeners = new Map<string, Set<(event: MessageEvent) => void>>();
  onerror: ((event: Event) => void) | null = null;
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: MessageEvent) => void) {
    const set = this.listeners.get(type) ?? new Set();
    set.add(listener);
    this.listeners.set(type, set);
  }

  removeEventListener(type: string, listener: (event: MessageEvent) => void) {
    const set = this.listeners.get(type);
    set?.delete(listener);
  }

  emit(type: string, payload: unknown) {
    const event = { data: JSON.stringify(payload) } as MessageEvent;
    for (const listener of this.listeners.get(type) ?? []) {
      listener(event);
    }
  }

  static reset() {
    MockEventSource.instances = [];
  }
}

function SeedStage3Context() {
  const {
    setSessionId,
    setKnowledgeArtifact,
    setKnowledgeGraphReady,
    setPopulationArtifact,
    setAgentsGenerated,
  } = useApp();

  useEffect(() => {
    setSessionId("session-screen3");
    setKnowledgeGraphReady(true);
    setKnowledgeArtifact({
      session_id: "session-screen3",
      document: {
        document_id: "doc-3",
        file_name: "sports-policy.pdf",
        file_type: "application/pdf",
        text_length: 1800,
        paragraph_count: 8,
      },
      summary: "Sports subsidy for active youths and lower-income families in Woodlands.",
      entity_nodes: [],
      relationship_edges: [],
      entity_type_counts: {},
      processing_logs: [],
    });
    setPopulationArtifact({
      session_id: "session-screen3",
      candidate_count: 200,
      sample_count: 3,
      sample_mode: "affected_groups",
      sample_seed: 17,
      parsed_sampling_instructions: {
        hard_filters: {},
        soft_boosts: {},
        soft_penalties: {},
        exclusions: {},
        distribution_targets: {},
        notes_for_ui: [],
      },
      coverage: { planning_areas: ["Woodlands"], age_buckets: { "20-29": 2 } },
      sampled_personas: [
        { agent_id: "agent-0001", persona: { planning_area: "Woodlands", age: 23, occupation: "Student" }, selection_reason: { score: 0.91, matched_facets: [], matched_document_entities: [], instruction_matches: [], bm25_terms: [], semantic_summary: "", semantic_relevance: 0.8, geographic_relevance: 1, socioeconomic_relevance: 0.8, digital_behavior_relevance: 0.2, filter_alignment: 1 } },
        { agent_id: "agent-0002", persona: { planning_area: "Woodlands", age: 35, occupation: "Coach" }, selection_reason: { score: 0.84, matched_facets: [], matched_document_entities: [], instruction_matches: [], bm25_terms: [], semantic_summary: "", semantic_relevance: 0.7, geographic_relevance: 1, socioeconomic_relevance: 0.7, digital_behavior_relevance: 0.2, filter_alignment: 1 } },
        { agent_id: "agent-0003", persona: { planning_area: "Yishun", age: 41, occupation: "Accountant" }, selection_reason: { score: 0.48, matched_facets: [], matched_document_entities: [], instruction_matches: [], bm25_terms: [], semantic_summary: "", semantic_relevance: 0.4, geographic_relevance: 0.2, socioeconomic_relevance: 0.3, digital_behavior_relevance: 0.1, filter_alignment: 1 } },
      ],
      agent_graph: { nodes: [], links: [] },
      representativeness: { status: "balanced" },
      selection_diagnostics: {},
    });
    setAgentsGenerated(true);
  }, [setKnowledgeArtifact, setKnowledgeGraphReady, setPopulationArtifact, setSessionId, setAgentsGenerated]);

  return null;
}

describe("Simulation", () => {
  const originalFetch = global.fetch;
  const originalEventSource = global.EventSource;

  beforeEach(() => {
    MockEventSource.reset();
    vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        session_id: "session-screen3",
        status: "running",
        event_count: 0,
        last_round: 0,
        platform: "reddit",
        planned_rounds: 4,
        current_round: 0,
        elapsed_seconds: 0,
        estimated_total_seconds: 55,
        estimated_remaining_seconds: 55,
        counters: { posts: 0, comments: 0, reactions: 0, active_authors: 0 },
        checkpoint_status: {
          baseline: { status: "pending", completed_agents: 0, total_agents: 3 },
          final: { status: "pending", completed_agents: 0, total_agents: 3 },
        },
        top_threads: [],
        discussion_momentum: { approval_delta: 0, dominant_stance: "mixed" },
        latest_metrics: {},
        recent_events: [],
      }),
    }) as typeof fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
    global.EventSource = originalEventSource;
    vi.restoreAllMocks();
  });

  it("starts a live simulation, consumes the SSE stream, and renders feed progress plus completion state", async () => {
    render(
      <AppProvider>
        <SeedStage3Context />
        <Simulation />
      </AppProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "5" }));
    fireEvent.click(screen.getByRole("button", { name: /start simulation/i }));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    const request = vi.mocked(global.fetch).mock.calls[0];
    expect(request[0]).toContain("/api/v2/console/session/session-screen3/simulation/start");
    expect(JSON.parse(String(request[1]?.body)).rounds).toBe(5);

    const source = MockEventSource.instances[0];
    expect(source.url).toContain("/api/v2/console/session/session-screen3/simulation/stream");

    act(() => {
      source.emit("checkpoint_started", { event_type: "checkpoint_started", checkpoint_kind: "baseline", total_agents: 3 });
      source.emit("checkpoint_completed", { event_type: "checkpoint_completed", checkpoint_kind: "baseline", completed_agents: 3, total_agents: 3 });
      source.emit("round_started", { event_type: "round_started", round_no: 1 });
      source.emit("post_created", { event_type: "post_created", round_no: 1, actor_agent_id: "agent-0001", actor_name: "Amir", actor_subtitle: "Woodlands · Student", post_id: 1, title: "Sports access matters", content: "The subsidy would make weekly training affordable." });
      source.emit("comment_created", { event_type: "comment_created", round_no: 1, actor_agent_id: "agent-0002", actor_name: "Rachel", actor_subtitle: "Woodlands · Coach", post_id: 1, comment_id: 4, content: "This also helps team retention." });
      source.emit("reaction_added", { event_type: "reaction_added", round_no: 1, actor_agent_id: "agent-0003", reaction: "like", post_id: 1 });
      source.emit("metrics_updated", {
        event_type: "metrics_updated",
        round_no: 1,
        elapsed_seconds: 14,
        estimated_total_seconds: 50,
        estimated_remaining_seconds: 36,
        counters: { posts: 1, comments: 1, reactions: 1, active_authors: 2 },
        top_threads: [{ post_id: 1, title: "Sports access matters", engagement: 3 }],
        discussion_momentum: { approval_delta: 0.12, dominant_stance: "support" },
      });
      source.emit("run_completed", { event_type: "run_completed", round_no: 1, elapsed_seconds: 15 });
    });

    const threadTitles = await screen.findAllByText("Sports access matters");
    expect(threadTitles.length).toBeGreaterThan(0);
    expect(screen.getByText("The subsidy would make weekly training affordable.")).toBeInTheDocument();
    expect(screen.getByText("This also helps team retention.")).toBeInTheDocument();
    expect(screen.getByText("15s")).toBeInTheDocument();
    expect(screen.getByText("Generate Report")).toBeInTheDocument();
    expect(screen.getAllByText("1").length).toBeGreaterThan(1);
  });
});
