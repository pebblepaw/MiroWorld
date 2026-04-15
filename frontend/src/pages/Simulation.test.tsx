import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useEffect, useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Simulation from "@/pages/Simulation";
import { AppProvider, useApp } from "@/contexts/AppContext";
import { resetBundledDemoState, type SimulationState } from "@/lib/console-api";

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

function SimulationPostsProbe() {
  const { simPosts } = useApp();
  return (
    <div>
      <div data-testid="sim-post-count">{simPosts.length}</div>
      <div data-testid="sim-post-title">{simPosts[0]?.title ?? ""}</div>
    </div>
  );
}

function SessionArtifactsProbe() {
  const {
    agentCount,
    analysisQuestions,
    sampleMode,
    sampleSeed,
    samplingInstructions,
  } = useApp();

  return (
    <div>
      <div data-testid="agent-count">{agentCount}</div>
      <div data-testid="analysis-question-count">{analysisQuestions.length}</div>
      <div data-testid="sample-mode">{sampleMode}</div>
      <div data-testid="sample-seed">{sampleSeed === null ? "null" : String(sampleSeed)}</div>
      <div data-testid="sampling-instructions">{samplingInstructions}</div>
    </div>
  );
}

function SeedPersistedSimulationPosts() {
  const {
    setSessionId,
    setKnowledgeArtifact,
    setKnowledgeGraphReady,
    setPopulationArtifact,
    setAgentsGenerated,
    setSimPosts,
  } = useApp();

  useEffect(() => {
    setSessionId("session-screen3-persisted");
    setKnowledgeGraphReady(true);
    setKnowledgeArtifact({
      session_id: "session-screen3-persisted",
      document: {
        document_id: "doc-persisted",
        file_name: "persisted.pdf",
        file_type: "application/pdf",
        text_length: 1200,
        paragraph_count: 4,
      },
      summary: "Persisted knowledge for navigation rehydration.",
      entity_nodes: [],
      relationship_edges: [],
      entity_type_counts: {},
      processing_logs: [],
    });
    setPopulationArtifact({
      session_id: "session-screen3-persisted",
      candidate_count: 50,
      sample_count: 1,
      sample_mode: "affected_groups",
      sample_seed: 7,
      parsed_sampling_instructions: {
        hard_filters: {},
        soft_boosts: {},
        soft_penalties: {},
        exclusions: {},
        distribution_targets: {},
        notes_for_ui: [],
      },
      coverage: { planning_areas: ["Woodlands"], age_buckets: { "20-29": 1 } },
      sampled_personas: [],
      agent_graph: { nodes: [], links: [] },
      representativeness: { status: "balanced" },
      selection_diagnostics: {},
    });
    setAgentsGenerated(true);
    setSimPosts([
      {
        id: "persisted-post-1",
        agentId: "agent-persisted-1",
        agentName: "Persisted Author",
        agentOccupation: "Teacher",
        agentArea: "Woodlands",
        title: "Persisted thread title",
        content: "Persisted thread body",
        upvotes: 9,
        downvotes: 1,
        commentCount: 2,
        round: 2,
        timestamp: "Round 2",
        comments: [
          {
            id: "persisted-comment-1",
            agentName: "Persisted Commenter",
            agentOccupation: "Nurse",
            content: "Persisted comment body",
            upvotes: 3,
          },
        ],
      },
    ]);
  }, [setAgentsGenerated, setKnowledgeArtifact, setKnowledgeGraphReady, setPopulationArtifact, setSessionId, setSimPosts]);

  return null;
}

function SeedHydratedSimulationState() {
  const {
    setSessionId,
    setKnowledgeArtifact,
    setKnowledgeGraphReady,
    setPopulationArtifact,
    setAgentsGenerated,
    setSimulationRounds,
  } = useApp();

  useEffect(() => {
    setSessionId("session-screen3-hydrate");
    setKnowledgeGraphReady(true);
    setKnowledgeArtifact({
      session_id: "session-screen3-hydrate",
      document: {
        document_id: "doc-hydrate",
        file_name: "hydrate.pdf",
        file_type: "application/pdf",
        text_length: 900,
        paragraph_count: 5,
      },
      summary: "Hydrated state should come from the backend.",
      entity_nodes: [],
      relationship_edges: [],
      entity_type_counts: {},
      processing_logs: [],
    });
    setPopulationArtifact({
      session_id: "session-screen3-hydrate",
      candidate_count: 80,
      sample_count: 4,
      sample_mode: "affected_groups",
      sample_seed: 11,
      parsed_sampling_instructions: {
        hard_filters: {},
        soft_boosts: {},
        soft_penalties: {},
        exclusions: {},
        distribution_targets: {},
        notes_for_ui: [],
      },
      coverage: { planning_areas: ["Woodlands"], age_buckets: { "20-29": 2 } },
      sampled_personas: [],
      agent_graph: { nodes: [], links: [] },
      representativeness: { status: "balanced" },
      selection_diagnostics: {},
    });
    setAgentsGenerated(true);
    setSimulationRounds(6);
  }, [setAgentsGenerated, setKnowledgeArtifact, setKnowledgeGraphReady, setPopulationArtifact, setSessionId, setSimulationRounds]);

  return null;
}

function SeedPersistedSimulationState() {
  const {
    setAgentCount,
    setAnalysisQuestions,
    setSampleMode,
    setSampleSeed,
    setSamplingInstructions,
    setSessionId,
    setKnowledgeArtifact,
    setKnowledgeGraphReady,
    setPopulationArtifact,
    setAgentsGenerated,
    setSimulationRounds,
    setSimulationState,
    setSimPosts,
  } = useApp();

  useEffect(() => {
    const state: SimulationState = {
      session_id: "session-screen3-persisted-state",
      status: "running",
      event_count: 12,
      last_round: 4,
      platform: "reddit",
      planned_rounds: 6,
      current_round: 4,
      elapsed_seconds: 123,
      estimated_total_seconds: 210,
      estimated_remaining_seconds: 87,
      counters: { posts: 8, comments: 19, reactions: 11, active_authors: 5 },
      checkpoint_status: {
        baseline: { status: "completed", completed_agents: 3, total_agents: 3 },
        final: { status: "pending", completed_agents: 0, total_agents: 3 },
      },
      top_threads: [{ title: "Persisted hottest thread", engagement: 9 }],
      discussion_momentum: { approval_delta: 0.21, dominant_stance: "support" },
      latest_metrics: {
        approval_rate: { value: 82.3, label: "Approval Rate" },
        net_sentiment: { value: 7.4, label: "Net Sentiment" },
        round_progress_label: "Round 4 is in progress",
      },
      recent_events: [{ event_type: "round_batch_flushed", round_no: 4, batch_index: 1, batch_count: 2 }],
    };

    setSessionId("session-screen3-persisted-state");
    setAgentCount(142);
    setAnalysisQuestions([
      {
        question: "Should the subsidy stay broad?",
        type: "yes-no",
        metric_name: "broad_subsidy_support",
        report_title: "Broad subsidy support",
      },
    ]);
    setSampleMode("population_baseline");
    setSampleSeed(42);
    setSamplingInstructions("Prioritize older households and active commuters.");
    setKnowledgeGraphReady(true);
    setKnowledgeArtifact({
      session_id: "session-screen3-persisted-state",
      document: {
        document_id: "doc-persisted-state",
        file_name: "persisted-state.pdf",
        file_type: "application/pdf",
        text_length: 1500,
        paragraph_count: 6,
      },
      summary: "Persisted simulation state should survive unmounts.",
      entity_nodes: [],
      relationship_edges: [],
      entity_type_counts: {},
      processing_logs: [],
    });
    setPopulationArtifact({
      session_id: "session-screen3-persisted-state",
      candidate_count: 100,
      sample_count: 4,
      sample_mode: "affected_groups",
      sample_seed: 19,
      parsed_sampling_instructions: {
        hard_filters: {},
        soft_boosts: {},
        soft_penalties: {},
        exclusions: {},
        distribution_targets: {},
        notes_for_ui: [],
      },
      coverage: { planning_areas: ["Woodlands"], age_buckets: { "20-29": 2 } },
      sampled_personas: [],
      agent_graph: { nodes: [], links: [] },
      representativeness: { status: "balanced" },
      selection_diagnostics: {},
    });
    setAgentsGenerated(true);
    setSimulationRounds(6);
    setSimulationState(state);
    setSimPosts([
      {
        id: "persisted-state-post-1",
        agentId: "agent-persisted-state-1",
        agentName: "Persisted Author",
        agentOccupation: "Teacher",
        agentArea: "Woodlands",
        title: "Persisted thread title",
        content: "Persisted thread body",
        upvotes: 9,
        downvotes: 1,
        commentCount: 1,
        round: 4,
        timestamp: "Round 4",
        comments: [
          {
            id: "persisted-state-comment-1",
            agentName: "Persisted Commenter",
            agentOccupation: "Nurse",
            content: "Persisted comment body",
            upvotes: 3,
          },
        ],
      },
    ]);
  }, [
    setAgentCount,
    setAgentsGenerated,
    setAnalysisQuestions,
    setKnowledgeArtifact,
    setKnowledgeGraphReady,
    setPopulationArtifact,
    setSampleMode,
    setSampleSeed,
    setSamplingInstructions,
    setSessionId,
    setSimPosts,
    setSimulationRounds,
    setSimulationState,
  ]);

  return null;
}

function SeedDraftSessionInputs() {
  const { setAgentCount, setSampleMode, setSampleSeed, setSamplingInstructions, setSessionId } = useApp();

  useEffect(() => {
    setAgentCount(88);
    setSampleMode("population_baseline");
    setSampleSeed(17);
    setSamplingInstructions("Keep the current draft inputs.");
    setSessionId("session-screen1-created");
  }, [setAgentCount, setSampleMode, setSampleSeed, setSamplingInstructions, setSessionId]);

  return null;
}

function SessionSwitchHarness() {
  const { setSessionId } = useApp();

  return (
    <button type="button" onClick={() => setSessionId("session-screen3-fresh")}>
      Switch session
    </button>
  );
}

function Screen3ToggleHarness() {
  const [visible, setVisible] = useState(true);

  return (
    <div>
      <button type="button" onClick={() => setVisible((current) => !current)}>
        Toggle Screen 3
      </button>
      {visible ? <Simulation /> : null}
    </div>
  );
}

describe("Simulation", () => {
  const originalFetch = global.fetch;
  const originalEventSource = global.EventSource;

  beforeEach(() => {
    resetBundledDemoState();
    MockEventSource.reset();
    window.sessionStorage.clear();
    vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const pendingState = {
        session_id: "session-screen3",
        status: "pending",
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
      };
      const runningState = {
        ...pendingState,
        status: "running",
      };
      if (url.includes("/simulation/state")) {
        return {
          ok: true,
          json: async () => pendingState,
        } as Response;
      }
      return {
        ok: true,
        json: async () => runningState,
      } as Response;
    }) as typeof fetch;
  });

  afterEach(() => {
    window.sessionStorage.clear();
    global.fetch = originalFetch;
    global.EventSource = originalEventSource;
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("uses the v2 simulate contract, defaults controversy boost off to 0, normalizes SSE metrics, and persists sim posts", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "live");

    render(
      <AppProvider>
        <SeedStage3Context />
        <SimulationPostsProbe />
        <Simulation />
      </AppProvider>,
    );

    await waitFor(() =>
      expect(
        vi.mocked(global.fetch).mock.calls.some(([request]) =>
          String(request).includes("/simulation/state"),
        ),
      ).toBe(true),
    );
    fireEvent.click(screen.getByRole("button", { name: "5" }));
    fireEvent.click(screen.getByRole("button", { name: /start simulation/i }));

    await waitFor(() =>
      expect(
        vi.mocked(global.fetch).mock.calls.some(([request]) =>
          String(request).includes("/api/v2/console/session/session-screen3/simulate"),
        ),
      ).toBe(true),
    );
    const [hydrateRequest] = vi.mocked(global.fetch).mock.calls.filter(([request]) =>
      String(request).includes("/api/v2/console/session/session-screen3/simulation/state"),
    );
    const simulateRequest = vi.mocked(global.fetch).mock.calls.find(([request]) =>
      String(request).includes("/api/v2/console/session/session-screen3/simulate"),
    );
    expect(hydrateRequest?.[0]).toContain("/api/v2/console/session/session-screen3/simulation/state");
    expect(simulateRequest?.[0]).toContain("/api/v2/console/session/session-screen3/simulate");
    expect(JSON.parse(String(simulateRequest[1]?.body)).rounds).toBe(5);
    expect(JSON.parse(String(simulateRequest[1]?.body)).controversy_boost).toBe(0);

    const source = MockEventSource.instances[0];
    expect(source.url).toContain("/api/v2/console/session/session-screen3/simulation/stream");

    act(() => {
      source.emit("checkpoint_started", { event_type: "checkpoint_started", checkpoint_kind: "baseline", total_agents: 3 });
      source.emit("checkpoint_completed", { event_type: "checkpoint_completed", checkpoint_kind: "baseline", completed_agents: 3, total_agents: 3 });
      source.emit("round_started", { event_type: "round_started", round_no: 1 });
      source.emit("round_batch_flushed", { event_type: "round_batch_flushed", round: 1, batch: 1, total_batches: 2, percentage: 50 });
      source.emit("post_created", { event_type: "post_created", round_no: 1, actor_agent_id: "agent-0001", actor_name: "Amir", actor_subtitle: "Woodlands · Student", actor_occupation: "Student", post_id: 1, title: "Sports access matters", content: "The subsidy would make weekly training affordable." });
      source.emit("comment_created", { event_type: "comment_created", round_no: 1, actor_agent_id: "agent-0002", actor_name: "Rachel", actor_subtitle: "Woodlands · Coach", post_id: 1, comment_id: 4, content: "This also helps team retention." });
      source.emit("comment_created", { event_type: "comment_created", round_no: 1, actor_agent_id: "agent-0002", actor_name: "Rachel", actor_subtitle: "Woodlands · Coach", post_id: 1, comment_id: 5, content: "Parents can plan activities earlier." });
      source.emit("comment_created", { event_type: "comment_created", round_no: 1, actor_agent_id: "agent-0003", actor_name: "Joel", actor_subtitle: "Yishun · Accountant", post_id: 1, comment_id: 6, content: "Affordability affects participation." });
      source.emit("comment_created", { event_type: "comment_created", round_no: 1, actor_agent_id: "agent-0003", actor_name: "Joel", actor_subtitle: "Yishun · Accountant", post_id: 1, comment_id: 7, content: "Transport support should be bundled too." });
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
        metrics: {
          approval_rate: { value: 73.4, label: "Approval Rate" },
          net_sentiment: { value: 6.8, label: "Net Sentiment" },
        },
      });
      source.emit("run_completed", { event_type: "run_completed", round_no: 1, elapsed_seconds: 15 });
    });

    const threadTitles = await screen.findAllByText("Sports access matters");
    expect(threadTitles.length).toBeGreaterThan(0);
    expect(screen.getByText("The subsidy would make weekly training affordable.")).toBeInTheDocument();
    expect(screen.getByText("This also helps team retention.")).toBeInTheDocument();
    expect(screen.queryByText("Transport support should be bundled too.")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /view 1 more replies/i }));
    expect(screen.getByText("Transport support should be bundled too.")).toBeInTheDocument();
    expect(screen.getByText("Round 1 (50%)")).toBeInTheDocument();
    expect(screen.getByText("0m 15s")).toBeInTheDocument();
    expect(screen.getByText("Generate Report")).toBeInTheDocument();
    expect(screen.getByText("73.4%")).toBeInTheDocument();
    expect(screen.getByText("6.8/10")).toBeInTheDocument();
    expect(screen.getByTestId("sim-post-count")).toHaveTextContent("1");
    expect(screen.getByTestId("sim-post-title")).toHaveTextContent("Sports access matters");
    expect(screen.getAllByText("1").length).toBeGreaterThan(1);
  });

  it("rehydrates persisted simulation posts when the screen remounts", async () => {
    render(
      <AppProvider>
        <SeedPersistedSimulationPosts />
        <Simulation />
      </AppProvider>,
    );

    expect(await screen.findByText("Persisted thread title")).toBeInTheDocument();
    expect(screen.getByText("Persisted thread body")).toBeInTheDocument();
    expect(screen.getByText("Persisted Author")).toBeInTheDocument();
    expect(screen.getByText("Persisted Commenter")).toBeInTheDocument();
  });

  it("hydrates cached demo posts in backend-backed demo mode", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "demo");

    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/demo-output.json")) {
        return {
          ok: true,
          json: async () => ({
            population: {
              sampled_personas: [
                {
                  agent_id: "agent-0001",
                  persona: { occupation: "Teacher", planning_area: "Woodlands" },
                },
              ],
            },
            analytics: {
              cascades: {
                viral_posts: [
                  {
                    post_id: "demo-post-1",
                    author: "agent-0001",
                    author_name: "Demo Author",
                    title: "Bundled demo post",
                    content: "Bundled demo body",
                    likes: 8,
                    dislikes: 1,
                    comments: [
                      {
                        comment_id: "demo-comment-1",
                        author: "agent-0001",
                        author_name: "Demo Author",
                        content: "Bundled demo reply",
                        likes: 2,
                      },
                    ],
                  },
                ],
              },
            },
          }),
        } as Response;
      }
      if (url.includes("/simulation/state")) {
        return {
          ok: true,
          json: async () => ({
            session_id: "session-screen3-hydrate",
            status: "completed",
            event_count: 12,
            last_round: 4,
            platform: "reddit",
            planned_rounds: 6,
            current_round: 6,
            elapsed_seconds: 123,
            estimated_total_seconds: 123,
            estimated_remaining_seconds: 0,
            counters: { posts: 8, comments: 19, reactions: 11, active_authors: 5 },
            checkpoint_status: {
              baseline: { status: "completed", completed_agents: 3, total_agents: 3 },
              final: { status: "completed", completed_agents: 3, total_agents: 3 },
            },
            top_threads: [{ title: "Bundled demo post", engagement: 9 }],
            discussion_momentum: { approval_delta: 0.21, dominant_stance: "support" },
            latest_metrics: {
              approval_rate: { value: 82.3, label: "Approval Rate" },
              net_sentiment: { value: 7.4, label: "Net Sentiment" },
              round_progress_label: "Completed",
            },
            recent_events: [],
          }),
        } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    }) as typeof fetch;

    render(
      <AppProvider>
        <SeedHydratedSimulationState />
        <Simulation />
      </AppProvider>,
    );

    expect(await screen.findByText("Bundled demo post")).toBeInTheDocument();
    expect(screen.queryByText("No posts to display")).not.toBeInTheDocument();
    expect(screen.getAllByText("Demo Author").length).toBeGreaterThan(0);
  });

  it("renders seeded titles exactly and strips markdown formatting from Screen 3 discourse", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "live");

    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/simulation/state")) {
        return {
          ok: true,
          json: async () => ({
            session_id: "session-screen3-plain-text",
            status: "idle",
            event_count: 0,
            last_round: 0,
            platform: "reddit",
            planned_rounds: 5,
            current_round: 0,
            elapsed_seconds: 0,
            estimated_total_seconds: 0,
            estimated_remaining_seconds: 0,
            counters: { posts: 0, comments: 0, reactions: 0, active_authors: 0 },
            checkpoint_status: {},
            top_threads: [],
            discussion_momentum: {},
            latest_metrics: {},
            recent_events: [],
          }),
        } as Response;
      }
      if (url.includes("/simulate")) {
        return {
          ok: true,
          json: async () => ({ session_id: "session-screen3-plain-text", status: "running" }),
        } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    }) as typeof fetch;

    render(
      <AppProvider>
        <SeedStage3Context />
        <Simulation />
      </AppProvider>,
    );

    fireEvent.click(await screen.findByRole("button", { name: /start simulation/i }));

    await waitFor(() => {
      expect(MockEventSource.instances).toHaveLength(1);
    });
    const source = MockEventSource.instances[0];
    act(() => {
      source.emit("post_created", {
        event_type: "post_created",
        round_no: 1,
        actor_agent_id: "agent-0001",
        actor_name: "Amir",
        actor_subtitle: "Woodlands · Student",
        actor_occupation: "Student",
        post_id: 11,
        title: "[Will this keep transport affordable?] (Seeded post)",
        content: "**Fare relief** matters for lower-income riders.\n- Keep the sign-up simple.",
      });
      source.emit("comment_created", {
        event_type: "comment_created",
        round_no: 1,
        actor_agent_id: "agent-0002",
        actor_name: "Rachel",
        actor_subtitle: "Woodlands · Coach",
        post_id: 11,
        comment_id: 20,
        content: "**Agreed**.\n- The application process should stay short.",
      });
    });

    expect(await screen.findByText("[Will this keep transport affordable?] (Seeded post)")).toBeInTheDocument();
    expect(screen.getByText(/Fare relief matters for lower-income riders\./)).toBeInTheDocument();
    expect(screen.getByText(/Keep the sign-up simple\./)).toBeInTheDocument();
    expect(screen.getByText(/Agreed\./)).toBeInTheDocument();
    expect(screen.queryByText(/\*\*Fare relief\*\*/)).not.toBeInTheDocument();
  });

  it("hydrates screen 3 state from the backend when the context state is missing", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        session_id: "session-screen3-hydrate",
        status: "running",
        event_count: 12,
        last_round: 4,
        platform: "reddit",
        planned_rounds: 6,
        current_round: 4,
        elapsed_seconds: 123,
        estimated_total_seconds: 210,
        estimated_remaining_seconds: 87,
        counters: { posts: 8, comments: 19, reactions: 11, active_authors: 5 },
        checkpoint_status: {
          baseline: { status: "completed", completed_agents: 3, total_agents: 3 },
          final: { status: "pending", completed_agents: 0, total_agents: 3 },
        },
        top_threads: [{ title: "Hydrated hottest thread", engagement: 9 }],
        discussion_momentum: { approval_delta: 0.21, dominant_stance: "support" },
        latest_metrics: {
          approval_rate: { value: 82.3, label: "Approval Rate" },
          net_sentiment: { value: 7.4, label: "Net Sentiment" },
          round_progress_label: "Round 4 is in progress",
        },
        recent_events: [{ event_type: "round_batch_flushed", round_no: 4, batch_index: 1, batch_count: 2 }],
      }),
    }) as typeof fetch;

    render(
      <AppProvider>
        <SeedHydratedSimulationState />
        <Simulation />
      </AppProvider>,
    );

    await waitFor(() =>
      expect(
        vi.mocked(global.fetch).mock.calls.some(([request]) =>
          String(request).includes("/simulation/state"),
        ),
      ).toBe(true),
    );
    expect(screen.getByText("Live Social Simulation")).toBeInTheDocument();
  });

  it("keeps Screen 3 simulation state after the page unmounts and remounts", async () => {
    render(
      <AppProvider>
        <SeedPersistedSimulationState />
        <Screen3ToggleHarness />
      </AppProvider>,
    );

    expect(await screen.findByText("Round 4 of 6")).toBeInTheDocument();
    expect(screen.getByText("82.3%")).toBeInTheDocument();
    expect(screen.getByText("Persisted thread title")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /toggle screen 3/i }));
    expect(screen.queryByText("Round 4 of 6")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /toggle screen 3/i }));
    expect(await screen.findByText("Round 4 of 6")).toBeInTheDocument();
    expect(screen.getByText("82.3%")).toBeInTheDocument();
    expect(screen.getByText("Persisted thread title")).toBeInTheDocument();
  });

  it("clears stale Screen 3 state when the session changes", async () => {
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/simulation/state") && url.includes("session-screen3-fresh")) {
        return {
          ok: true,
          json: async () => ({
            session_id: "session-screen3-fresh",
            status: "running",
            event_count: 3,
            last_round: 1,
            platform: "reddit",
            planned_rounds: 8,
            current_round: 1,
            elapsed_seconds: 18,
            estimated_total_seconds: 120,
            estimated_remaining_seconds: 102,
            counters: { posts: 1, comments: 2, reactions: 1, active_authors: 1 },
            checkpoint_status: {
              baseline: { status: "completed", completed_agents: 3, total_agents: 3 },
              final: { status: "pending", completed_agents: 0, total_agents: 3 },
            },
            top_threads: [{ title: "Fresh session thread", engagement: 4 }],
            discussion_momentum: { approval_delta: 0.04, dominant_stance: "mixed" },
            latest_metrics: {
              approval_rate: { value: 71.2, label: "Approval Rate" },
              net_sentiment: { value: 6.1, label: "Net Sentiment" },
              round_progress_label: "Round 1 is in progress",
            },
            recent_events: [],
          }),
        } as Response;
      }
      return {
        ok: true,
        json: async () => ({
          session_id: "session-screen3-persisted-state",
          status: "running",
          event_count: 12,
          last_round: 4,
          platform: "reddit",
          planned_rounds: 6,
          current_round: 4,
          elapsed_seconds: 123,
          estimated_total_seconds: 210,
          estimated_remaining_seconds: 87,
          counters: { posts: 8, comments: 19, reactions: 11, active_authors: 5 },
          checkpoint_status: {
            baseline: { status: "completed", completed_agents: 3, total_agents: 3 },
            final: { status: "pending", completed_agents: 0, total_agents: 3 },
          },
          top_threads: [{ title: "Persisted hottest thread", engagement: 9 }],
          discussion_momentum: { approval_delta: 0.21, dominant_stance: "support" },
          latest_metrics: {
            approval_rate: { value: 82.3, label: "Approval Rate" },
            net_sentiment: { value: 7.4, label: "Net Sentiment" },
            round_progress_label: "Round 4 is in progress",
          },
          recent_events: [{ event_type: "round_batch_flushed", round_no: 4, batch_index: 1, batch_count: 2 }],
        }),
      } as Response;
    }) as typeof fetch;

    render(
      <AppProvider>
        <SeedPersistedSimulationState />
        <SessionSwitchHarness />
        <Simulation />
      </AppProvider>,
    );

    expect(await screen.findByText("Round 4 of 6")).toBeInTheDocument();
    expect(screen.getByText("Persisted thread title")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /switch session/i }));

    await waitFor(() =>
      expect(
        vi.mocked(global.fetch).mock.calls.some(([request]) =>
          String(request).includes("/api/v2/console/session/session-screen3-fresh/simulation/state"),
        ),
      ).toBe(true),
    );

    expect(await screen.findByText("Round 1 of 8")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("Round 4 of 6")).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText("Persisted thread title")).not.toBeInTheDocument());
  });

  it("clears stale session-scoped input when switching between existing sessions", async () => {
    render(
      <AppProvider>
        <SeedPersistedSimulationState />
        <SessionSwitchHarness />
        <SessionArtifactsProbe />
        <Simulation />
      </AppProvider>,
    );

    expect(await screen.findByText("Round 4 of 6")).toBeInTheDocument();
    expect(screen.getByTestId("agent-count")).toHaveTextContent("142");
    expect(screen.getByTestId("analysis-question-count")).toHaveTextContent("1");
    expect(screen.getByTestId("sample-mode")).toHaveTextContent("population_baseline");
    expect(screen.getByTestId("sample-seed")).toHaveTextContent("42");
    expect(screen.getByTestId("sampling-instructions")).toHaveTextContent("Prioritize older households and active commuters.");

    fireEvent.click(screen.getByRole("button", { name: /switch session/i }));

    await waitFor(() =>
      expect(
        vi.mocked(global.fetch).mock.calls.some(([request]) =>
          String(request).includes("/api/v2/console/session/session-screen3-fresh/simulation/state"),
        ),
      ).toBe(true),
    );

    expect(screen.getByTestId("agent-count")).toHaveTextContent("0");
    expect(screen.getByTestId("analysis-question-count")).toHaveTextContent("0");
    expect(screen.getByTestId("sample-mode")).toHaveTextContent("affected_groups");
    expect(screen.getByTestId("sample-seed")).toHaveTextContent("null");
    expect(screen.getByTestId("sampling-instructions")).toHaveTextContent("");
  });

  it("preserves Screen 1 input when a session id is created from null", async () => {
    render(
      <AppProvider>
        <SeedDraftSessionInputs />
        <SessionArtifactsProbe />
      </AppProvider>,
    );

    expect(screen.getByTestId("agent-count")).toHaveTextContent("88");
    expect(screen.getByTestId("sample-mode")).toHaveTextContent("population_baseline");
    expect(screen.getByTestId("sample-seed")).toHaveTextContent("17");
    expect(screen.getByTestId("sampling-instructions")).toHaveTextContent("Keep the current draft inputs.");
  });

  it("sends a 0.5 controversy boost when the binary toggle is enabled", async () => {
    render(
      <AppProvider>
        <SeedStage3Context />
        <Simulation />
      </AppProvider>,
    );

    await waitFor(() =>
      expect(
        vi.mocked(global.fetch).mock.calls.some(([request]) =>
          String(request).includes("/simulation/state"),
        ),
      ).toBe(true),
    );
    fireEvent.click(screen.getByRole("switch", { name: /controversy boost/i }));
    fireEvent.click(screen.getByRole("button", { name: /start simulation/i }));

    await waitFor(() =>
      expect(
        vi.mocked(global.fetch).mock.calls.some(([request]) =>
          String(request).includes("/api/v2/console/session/session-screen3/simulate"),
        ),
      ).toBe(true),
    );
    const request = vi.mocked(global.fetch).mock.calls.find(([request]) =>
      String(request).includes("/api/v2/console/session/session-screen3/simulate"),
    );
    expect(request?.[0]).toContain("/api/v2/console/session/session-screen3/simulate");
    expect(JSON.parse(String(request?.[1]?.body)).controversy_boost).toBe(0.5);
  });

  it("shows hover tooltips for controversy and metric cards while keeping separate scroll regions", async () => {
    render(
      <AppProvider>
        <SeedStage3Context />
        <Simulation />
      </AppProvider>,
    );

    expect(document.querySelector("div.flex.h-full.min-h-0.gap-6.overflow-hidden.p-6")).toBeTruthy();
    expect(document.querySelectorAll("div.overflow-y-auto.scrollbar-thin").length).toBeGreaterThanOrEqual(2);

    expect(
      screen.getByText(
        "Amplifies divisive content in the social feed, simulating how real platforms boost engagement through controversial posts.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Approval Rate").closest("[title]")).toHaveAttribute(
      "title",
      "Reads the latest approval rate from the simulation metrics payload.",
    );
    expect(screen.queryByText(/^Sentiment$/)).not.toBeInTheDocument();
  });

  it("shows missing markers instead of fabricated metric values in live mode when metrics are absent", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "live");

    render(
      <AppProvider>
        <SeedStage3Context />
        <Simulation />
      </AppProvider>,
    );

    const approvalCard = screen.getByText("Approval Rate").closest('div[title]');
    const sentimentCard = screen.getByText("Net Sentiment").closest('div[title]');

    expect(approvalCard).toBeTruthy();
    expect(sentimentCard).toBeTruthy();
    expect(within(approvalCard as HTMLElement).getByText("—")).toBeInTheDocument();
    expect(within(sentimentCard as HTMLElement).getByText("—")).toBeInTheDocument();
    expect(screen.queryByText("68.0%")).not.toBeInTheDocument();
    expect(screen.queryByText("7.2/10")).not.toBeInTheDocument();
  });

  it("hydrates demo-static simulation cost from bundled provider data and derives reaction counts from loaded threads", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "demo-static");

    const fetchSpy = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        session: { session_id: "demo-session" },
        source_run: {
          country: "singapore",
          provider: "google",
          model: "gemini-2.5-pro",
          use_case: "public-policy-testing",
          rounds: 3,
        },
        analysis_questions: [
          { question: "Support?", type: "scale", metric_name: "approval_rate", metric_label: "Approval Rate", metric_unit: "%" },
          { question: "Sentiment?", type: "scale", metric_name: "net_sentiment", metric_label: "Net Sentiment", metric_unit: "/10" },
        ],
        population: {
          session_id: "demo-session",
          sample_count: 35,
          sample_seed: 9,
          sampled_personas: [
            {
              agent_id: "agent-1",
              display_name: "Alicia Tan",
              persona: { planning_area: "Woodlands", age: 28, occupation: "Teacher", sex: "Female" },
              selection_reason: { score: 0.91, matched_facets: [], matched_document_entities: [], instruction_matches: [], bm25_terms: [], semantic_summary: "", semantic_relevance: 0.8, geographic_relevance: 0.7, socioeconomic_relevance: 0.7, digital_behavior_relevance: 0.2, filter_alignment: 1 },
            },
            {
              agent_id: "agent-2",
              display_name: "Marcus Lim",
              persona: { planning_area: "Yishun", age: 42, occupation: "Engineer", sex: "Male" },
              selection_reason: { score: 0.74, matched_facets: [], matched_document_entities: [], instruction_matches: [], bm25_terms: [], semantic_summary: "", semantic_relevance: 0.7, geographic_relevance: 0.6, socioeconomic_relevance: 0.6, digital_behavior_relevance: 0.2, filter_alignment: 1 },
            },
            {
              agent_id: "agent-3",
              display_name: "Nora Ong",
              persona: { planning_area: "Jurong West", age: 35, occupation: "Nurse", sex: "Female" },
              selection_reason: { score: 0.38, matched_facets: [], matched_document_entities: [], instruction_matches: [], bm25_terms: [], semantic_summary: "", semantic_relevance: 0.5, geographic_relevance: 0.5, socioeconomic_relevance: 0.5, digital_behavior_relevance: 0.2, filter_alignment: 1 },
            },
          ],
        },
        simulationState: {
          session_id: "demo-session",
          status: "completed",
          event_count: 1,
          last_round: 3,
          planned_rounds: 3,
          current_round: 3,
          counters: { posts: 1, comments: 2, reactions: 1, active_authors: 3 },
          checkpoint_status: {},
          latest_metrics: { approval_rate: 62, net_sentiment: 6.4 },
          top_threads: [{ title: "Demo thread", engagement: 4 }],
          discussion_momentum: {},
          recent_events: [],
        },
        analytics: {
          cascades: {
            viral_posts: [
              {
                post_id: "post-1",
                author: "agent-1",
                title: "A grounded discussion",
                content: "People are debating the proposal in detail.",
                likes: 1,
                dislikes: 0,
                comments: [
                  {
                    comment_id: "comment-1",
                    author: "agent-2",
                    content: "I support the direction.",
                    likes: 1,
                    dislikes: 0,
                  },
                  {
                    comment_id: "comment-2",
                    author: "agent-3",
                    content: "I still have concerns.",
                    likes: 0,
                    dislikes: 1,
                  },
                ],
              },
            ],
          },
        },
      }),
    }));
    global.fetch = fetchSpy as typeof fetch;

    render(
      <AppProvider>
        <Simulation />
      </AppProvider>,
    );

    const initialCost = await screen.findByText(/~\$\d+\.\d{2} cost/i);
    const initialCostText = initialCost.textContent;
    expect(initialCostText).not.toContain("~$0.00 cost");

    const reactionsCard = await screen.findByText("Reactions");
    await waitFor(() => {
      const card = reactionsCard.closest("div.p-3.rounded-lg.bg-muted\\/40.border.border-border");
      expect(card).not.toBeNull();
      expect(within(card as HTMLElement).getByText("2")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "10" }));

    await waitFor(() => {
      expect(screen.getByText(/~\$\d+\.\d{2} cost/i).textContent).not.toBe(initialCostText);
    });
  });

  it("shows a live simulation error instead of generating mock fallback posts", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "live");
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/simulate")) {
        return {
          ok: false,
          status: 502,
          statusText: "Bad Gateway",
          json: async () => ({ detail: "live simulation unavailable" }),
        } as Response;
      }
      if (url.includes("/simulation/metrics")) {
        return {
          ok: false,
          status: 502,
          statusText: "Bad Gateway",
          json: async () => ({ detail: "metrics unavailable" }),
        } as Response;
      }
      return {
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
      } as Response;
    }) as typeof fetch;

    render(
      <AppProvider>
        <SeedStage3Context />
        <Simulation />
      </AppProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: /start simulation/i }));

    expect(await screen.findByText("live simulation unavailable")).toBeInTheDocument();
    expect(screen.getByText("Simulation Error")).toBeInTheDocument();
    expect(screen.queryByText(/Demo simulation loaded/i)).not.toBeInTheDocument();
  });

  it("maps long runtime tracebacks to a short simulation error message", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "live");

    render(
      <AppProvider>
        <SeedStage3Context />
        <Simulation />
      </AppProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: /start simulation/i }));

    await waitFor(() => expect(MockEventSource.instances.length).toBe(1));
    const source = MockEventSource.instances[0];
    act(() => {
      source.emit("run_failed", {
        event_type: "run_failed",
        error:
          "Real OASIS simulation failed. run_log=/tmp/oasis.log tail=Traceback ... "
          + "ModuleNotFoundError: No module named 'camel' process_exit_code=1",
      });
    });

    expect(
      await screen.findByText(
        "Simulation runtime is unavailable because the OASIS Python environment is missing required packages.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/run_log=\/tmp\/oasis\.log/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/ModuleNotFoundError/i)).not.toBeInTheDocument();
  });
});
