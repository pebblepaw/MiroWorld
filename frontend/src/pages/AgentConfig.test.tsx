import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import AgentConfig from "@/pages/AgentConfig";
import { AppProvider, useApp } from "@/contexts/AppContext";

vi.mock("@/components/SingaporeMap", () => ({
  SingaporeMap: ({
    areaData = [],
    country = "singapore",
  }: {
    areaData?: Array<{ name: string; count: number }>;
    country?: string;
  }) => (
    <div data-testid={`country-map-${country}`}>
      {areaData.map((row) => (
        <span key={row.name}>{row.name}</span>
      ))}
    </div>
  ),
}));

function SeedStage2Context() {
  const { setSessionId, setKnowledgeArtifact, setKnowledgeGraphReady, setCountry } = useApp();

  useEffect(() => {
    setSessionId("session-screen2");
    setCountry("singapore");
    setKnowledgeGraphReady(true);
    setKnowledgeArtifact({
      session_id: "session-screen2",
      document: {
        document_id: "doc-1",
        file_name: "education-grant.pdf",
        file_type: "application/pdf",
        text_length: 1200,
        paragraph_count: 7,
      },
      summary: "Education grants for younger teachers and parents in north-east Singapore.",
      entity_nodes: [
        { id: "facet:sengkang", label: "Sengkang", type: "location", facet_kind: "planning_area", canonical_key: "planning_area:sengkang" },
        { id: "facet:education", label: "Education", type: "industry", facet_kind: "industry", canonical_key: "industry:education" },
      ],
      relationship_edges: [],
      entity_type_counts: {},
      processing_logs: [],
    });
  }, [setCountry, setKnowledgeArtifact, setKnowledgeGraphReady, setSessionId]);

  return null;
}

function SeedStage2ContextWithAgentCount() {
  const { setSessionId, setKnowledgeArtifact, setKnowledgeGraphReady, setAgentCount, setCountry } = useApp();

  useEffect(() => {
    setSessionId("session-screen2");
    setCountry("singapore");
    setKnowledgeGraphReady(true);
    setAgentCount(124);
    setKnowledgeArtifact({
      session_id: "session-screen2",
      document: {
        document_id: "doc-1",
        file_name: "education-grant.pdf",
        file_type: "application/pdf",
        text_length: 1200,
        paragraph_count: 7,
      },
      summary: "Education grants for younger teachers and parents in north-east Singapore.",
      entity_nodes: [],
      relationship_edges: [],
      entity_type_counts: {},
      processing_logs: [],
    });
  }, [setAgentCount, setCountry, setKnowledgeArtifact, setKnowledgeGraphReady, setSessionId]);

  return null;
}

function SeedStage2ContextUsa() {
  const { setSessionId, setKnowledgeArtifact, setKnowledgeGraphReady, setCountry, setPopulationArtifact } = useApp();

  useEffect(() => {
    setSessionId("session-screen2-usa");
    setCountry("usa");
    setKnowledgeGraphReady(true);
    setKnowledgeArtifact({
      session_id: "session-screen2-usa",
      document: {
        document_id: "doc-usa",
        file_name: "urban-policy.pdf",
        file_type: "application/pdf",
        text_length: 1100,
        paragraph_count: 6,
      },
      summary: "Urban policy comparisons across US states.",
      entity_nodes: [],
      relationship_edges: [],
      entity_type_counts: {},
      processing_logs: [],
    });
    setPopulationArtifact({
      session_id: "session-screen2-usa",
      candidate_count: 120,
      sample_count: 2,
      sample_mode: "affected_groups",
      sample_seed: 11,
      parsed_sampling_instructions: {
        hard_filters: {},
        soft_boosts: {},
        soft_penalties: {},
        exclusions: {},
        distribution_targets: {},
        notes_for_ui: [],
        source: "gemini",
      },
      coverage: {
        states: ["California", "Texas"],
        age_buckets: { "20-29": 1, "30-39": 1 },
      },
      sampled_personas: [],
      agent_graph: { nodes: [], links: [] },
      representativeness: {
        status: "balanced",
        state_distribution: { California: 1, Texas: 1 },
        sex_distribution: {},
      },
      selection_diagnostics: {},
    });
  }, [setCountry, setKnowledgeArtifact, setKnowledgeGraphReady, setPopulationArtifact, setSessionId]);

  return null;
}

describe("AgentConfig", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("requests a live sampled cohort and renders backend diagnostics and graph data", async () => {
    global.fetch = vi.fn().mockImplementation(
      createAgentFetch({
        sessionId: "session-screen2",
        previewPayloads: [
          {
            session_id: "session-screen2",
            candidate_count: 824,
            sample_count: 3,
            sample_mode: "affected_groups",
            sample_seed: 17,
            parsed_sampling_instructions: {
              hard_filters: {},
              soft_boosts: {
                occupation: ["teacher"],
                age_cohort: ["youth"],
                planning_area: ["sengkang", "punggol"],
              },
              soft_penalties: {},
              exclusions: {},
              distribution_targets: {},
              notes_for_ui: ["Bias toward younger teachers and parents in the north-east."],
              source: "gemini",
            },
            coverage: {
              planning_areas: ["Sengkang", "Punggol"],
              age_buckets: { "20-29": 2, "30-39": 1 },
              sex_distribution: { Female: 2, Male: 1 },
            },
            sampled_personas: [
              {
                agent_id: "agent-0001",
                persona: {
                  age: 28,
                  sex: "Female",
                  occupation: "teacher",
                  industry: "education",
                  planning_area: "Sengkang",
                  country: "Singapore",
                },
                selection_reason: {
                  score: 0.91,
                  matched_facets: ["planning_area:sengkang", "industry:education"],
                  matched_document_entities: ["teachers", "parents"],
                  instruction_matches: ["occupation", "age_cohort", "planning_area"],
                  bm25_terms: ["teacher", "young", "north-east"],
                  semantic_summary: "Matched facets and instruction preferences.",
                  semantic_relevance: 0.87,
                  bm25_relevance: 0.79,
                  geographic_relevance: 1,
                  socioeconomic_relevance: 0.88,
                  digital_behavior_relevance: 0.4,
                  filter_alignment: 1,
                },
              },
              {
                agent_id: "agent-0002",
                persona: {
                  age: 31,
                  sex: "Male",
                  occupation: "teacher",
                  industry: "education",
                  planning_area: "Punggol",
                  country: "Singapore",
                },
                selection_reason: {
                  score: 0.82,
                  matched_facets: ["industry:education"],
                  matched_document_entities: ["teachers"],
                  instruction_matches: ["occupation", "planning_area"],
                  bm25_terms: ["teacher", "north-east"],
                  semantic_summary: "Matched teaching and planning-area signals.",
                  semantic_relevance: 0.78,
                  bm25_relevance: 0.71,
                  geographic_relevance: 0.92,
                  socioeconomic_relevance: 0.79,
                  digital_behavior_relevance: 0.4,
                  filter_alignment: 1,
                },
              },
              {
                agent_id: "agent-0003",
                persona: {
                  age: 35,
                  sex: "Female",
                  occupation: "counsellor",
                  industry: "education",
                  planning_area: "Sengkang",
                  country: "Singapore",
                },
                selection_reason: {
                  score: 0.77,
                  matched_facets: ["planning_area:sengkang"],
                  matched_document_entities: ["parents"],
                  instruction_matches: ["planning_area"],
                  bm25_terms: ["parents"],
                  semantic_summary: "Parent-support comparison profile.",
                  semantic_relevance: 0.7,
                  bm25_relevance: 0.61,
                  geographic_relevance: 1,
                  socioeconomic_relevance: 0.69,
                  digital_behavior_relevance: 0.4,
                  filter_alignment: 1,
                },
              },
            ],
            agent_graph: {
              nodes: [
                { id: "agent-0001", label: "teacher", subtitle: "Sengkang · education", planning_area: "Sengkang", industry: "education", node_type: "sampled_persona", score: 0.91, age: 28, sex: "Female" },
                { id: "agent-0002", label: "teacher", subtitle: "Punggol · education", planning_area: "Punggol", industry: "education", node_type: "sampled_persona", score: 0.82, age: 31, sex: "Male" },
                { id: "agent-0003", label: "counsellor", subtitle: "Sengkang · education", planning_area: "Sengkang", industry: "education", node_type: "sampled_persona", score: 0.77, age: 35, sex: "Female" },
              ],
              links: [
                { source: "agent-0001", target: "agent-0002", reason: "shared_industry", reasons: ["shared_industry"], label: "shared industry" },
                { source: "agent-0001", target: "agent-0003", reason: "shared_planning_area", reasons: ["shared_planning_area", "shared_industry"], label: "shared planning area, shared industry" },
              ],
            },
            representativeness: {
              status: "balanced",
              planning_area_distribution: { Sengkang: 2, Punggol: 1 },
              sex_distribution: { Female: 2, Male: 1 },
            },
            selection_diagnostics: {
              candidate_count: 824,
              structured_filter_count: 824,
              shortlist_count: 96,
              bm25_shortlist_count: 96,
              semantic_rerank_count: 48,
            },
          },
        ],
      }),
    ) as typeof fetch;

    render(
      <AppProvider>
        <SeedStage2Context />
        <AgentConfig />
      </AppProvider>,
    );

    await screen.findByRole("button", { name: /sample population/i });
    expect(screen.queryByText(/Current target: 0 agents/i)).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/strategic parameters/i), {
      target: { value: "Bias toward younger teachers and parents in the north-east." },
    });

    fireEvent.click(screen.getByRole("button", { name: /sample population/i }));

    await waitFor(() => expect(global.fetch).toHaveBeenCalled());

    const previewRequest = vi.mocked(global.fetch).mock.calls.find(([url]) => String(url).includes("/sampling/preview"));
    expect(previewRequest?.[0]).toContain("/api/v2/console/session/session-screen2/sampling/preview");
    const body = JSON.parse(String(previewRequest?.[1]?.body));
    expect(body.agent_count).toBe(2);
    expect(body.sample_mode).toBe("affected_groups");
    expect(body.sampling_instructions).toBe("Bias toward younger teachers and parents in the north-east.");
    expect(typeof body.seed).toBe("number");
    expect(body.min_age).toBeUndefined();
    expect(body.max_age).toBeUndefined();
    expect(body.planning_areas).toBeUndefined();
    expect(body.dynamic_filters).toBeUndefined();

    expect(await screen.findByText("Candidate Shortlist")).toBeInTheDocument();
    expect(screen.getByText("824")).toBeInTheDocument();
    expect(screen.getByText("Semantic Rerank")).toBeInTheDocument();
    expect(screen.getByText("Occupation Distribution")).toBeInTheDocument();
    expect(screen.getByText("Age Stratification")).toBeInTheDocument();
    expect(screen.queryByText("Teacher 2")).not.toBeInTheDocument();
    expect(screen.queryByText("Counsellor 1")).not.toBeInTheDocument();
    expect(screen.queryByText("n=3")).not.toBeInTheDocument();
    expect(screen.queryByText("Estimated Token Usage")).not.toBeInTheDocument();
    expect(screen.queryByText("$0.42")).not.toBeInTheDocument();
    expect(screen.queryByText("$1.68")).not.toBeInTheDocument();
    expect(screen.queryByText("Runtime: $0.21 · 8,000 cached tokens")).not.toBeInTheDocument();
    expect(screen.getByText("Parsed Strategy Notes")).toBeInTheDocument();
    expect(screen.getAllByText("Bias toward younger teachers and parents in the north-east.").length).toBeGreaterThan(0);
    expect(screen.getByText("Cohort Explorer")).toBeInTheDocument();
    expect(screen.getByLabelText("Persona agent-0001")).toBeInTheDocument();
    expect(screen.getByLabelText("Persona agent-0002")).toBeInTheDocument();
    expect(screen.getByLabelText("Persona agent-0003")).toBeInTheDocument();
    expect(screen.getByTestId("country-map-singapore")).toBeInTheDocument();
    expect(screen.getByText("Population Baseline")).toBeInTheDocument();
  });

  it("updates the sample helper text with the current target size", async () => {
    render(
      <AppProvider>
        <SeedStage2ContextWithAgentCount />
        <AgentConfig />
      </AppProvider>,
    );

    await screen.findByText("124");
    expect(screen.queryByText(/Current target: 124 agents/i)).not.toBeInTheDocument();
  });

  it("renders the country map for USA sessions", async () => {
    global.fetch = vi.fn().mockImplementation(
      createAgentFetch({
        sessionId: "session-screen2-usa",
        previewPayloads: [
          {
            session_id: "session-screen2-usa",
            candidate_count: 320,
            sample_count: 2,
            sample_mode: "affected_groups",
            sample_seed: 11,
            parsed_sampling_instructions: {
              hard_filters: {},
              soft_boosts: {},
              soft_penalties: {},
              exclusions: {},
              distribution_targets: {},
              notes_for_ui: [],
              source: "gemini",
            },
            coverage: {
              states: ["California", "Texas"],
              age_buckets: { "20-29": 1, "30-39": 1 },
            },
            sampled_personas: [
              {
                agent_id: "agent-us-1",
                persona: { age: 28, sex: "Female", occupation: "analyst", industry: "technology", state: "California", country: "USA" },
                selection_reason: {
                  score: 0.9,
                  matched_facets: [],
                  matched_document_entities: [],
                  instruction_matches: [],
                  bm25_terms: [],
                  semantic_summary: "",
                  semantic_relevance: 0.8,
                  bm25_relevance: 0.7,
                  geographic_relevance: 1,
                  socioeconomic_relevance: 0.8,
                  digital_behavior_relevance: 0.3,
                  filter_alignment: 1,
                },
              },
              {
                agent_id: "agent-us-2",
                persona: { age: 35, sex: "Male", occupation: "teacher", industry: "education", state: "Texas", country: "USA" },
                selection_reason: {
                  score: 0.8,
                  matched_facets: [],
                  matched_document_entities: [],
                  instruction_matches: [],
                  bm25_terms: [],
                  semantic_summary: "",
                  semantic_relevance: 0.7,
                  bm25_relevance: 0.6,
                  geographic_relevance: 1,
                  socioeconomic_relevance: 0.7,
                  digital_behavior_relevance: 0.3,
                  filter_alignment: 1,
                },
              },
            ],
            agent_graph: { nodes: [], links: [] },
            representativeness: {
              status: "balanced",
              state_distribution: { California: 1, Texas: 1 },
            },
            selection_diagnostics: {},
          },
        ],
      }),
    ) as typeof fetch;

    render(
      <AppProvider>
        <SeedStage2ContextUsa />
        <AgentConfig />
      </AppProvider>,
    );

    await screen.findByRole("button", { name: /sample population/i });
    fireEvent.click(screen.getByRole("button", { name: /sample population/i }));
    expect(await screen.findByTestId("country-map-usa")).toBeInTheDocument();
    expect(screen.getByText("California")).toBeInTheDocument();
    expect(screen.getByText("Texas")).toBeInTheDocument();
    expect(screen.getByText("Population Baseline")).toBeInTheDocument();
  });

  it("omits removed legacy range filters from the sampling payload", async () => {
    global.fetch = vi.fn().mockImplementation(
      createAgentFetch({
        sessionId: "session-screen2",
        previewPayloads: [
          {
            session_id: "session-screen2",
            candidate_count: 50,
            sample_count: 2,
            sample_mode: "affected_groups",
            sample_seed: 21,
            parsed_sampling_instructions: {
              hard_filters: {},
              soft_boosts: {},
              soft_penalties: {},
              exclusions: {},
              distribution_targets: {},
              notes_for_ui: [],
              source: "gemini",
            },
            coverage: {},
            sampled_personas: [],
            agent_graph: { nodes: [], links: [] },
            representativeness: { status: "balanced" },
            selection_diagnostics: {},
          },
        ],
      }),
    ) as typeof fetch;

    render(
      <AppProvider>
        <SeedStage2Context />
        <AgentConfig />
      </AppProvider>,
    );

    await screen.findByRole("button", { name: /sample population/i });
    fireEvent.click(screen.getByRole("button", { name: /sample population/i }));

    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    const previewRequest = vi.mocked(global.fetch).mock.calls.find(([url]) => String(url).includes("/sampling/preview"));
    const body = JSON.parse(String(previewRequest?.[1]?.body));
    expect(body.min_age).toBeUndefined();
    expect(body.max_age).toBeUndefined();
    expect(body.dynamic_filters).toBeUndefined();
  });

  it("switches to baseline mode and re-samples with a fresh seed using the same config", async () => {
    global.fetch = vi.fn().mockImplementation(
      createAgentFetch({
        sessionId: "session-screen2",
        previewPayloads: [
          {
            session_id: "session-screen2",
            candidate_count: 1200,
            sample_count: 2,
            sample_mode: "population_baseline",
            sample_seed: 44,
            parsed_sampling_instructions: { hard_filters: {}, soft_boosts: {}, soft_penalties: {}, exclusions: {}, distribution_targets: {}, notes_for_ui: [], source: "gemini" },
            coverage: { planning_areas: ["Bedok", "Yishun"], age_buckets: { "20-29": 1, "50-59": 1 } },
            sampled_personas: [],
            agent_graph: { nodes: [], links: [] },
            representativeness: { status: "balanced" },
            selection_diagnostics: { shortlist_count: 50, semantic_rerank_count: 20 },
          },
          {
            session_id: "session-screen2",
            candidate_count: 1200,
            sample_count: 2,
            sample_mode: "population_baseline",
            sample_seed: 91,
            parsed_sampling_instructions: { hard_filters: {}, soft_boosts: {}, soft_penalties: {}, exclusions: {}, distribution_targets: {}, notes_for_ui: [], source: "gemini" },
            coverage: { planning_areas: ["Bedok", "Yishun"], age_buckets: { "20-29": 1, "50-59": 1 } },
            sampled_personas: [],
            agent_graph: { nodes: [], links: [] },
            representativeness: { status: "balanced" },
            selection_diagnostics: { shortlist_count: 50, semantic_rerank_count: 20 },
          },
        ],
      }),
    ) as typeof fetch;

    render(
      <AppProvider>
        <SeedStage2Context />
        <AgentConfig />
      </AppProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: /population baseline/i }));
    fireEvent.change(screen.getByLabelText(/strategic parameters/i), {
      target: { value: "Include a broad comparison group across Singapore." },
    });

    fireEvent.click(screen.getByRole("button", { name: /sample population/i }));
    await waitFor(() =>
      expect(
        vi.mocked(global.fetch).mock.calls.filter(([url]) => String(url).includes("/sampling/preview")).length,
      ).toBe(1),
    );

    const previewCalls = vi.mocked(global.fetch).mock.calls.filter(([url]) => String(url).includes("/sampling/preview"));
    const firstBody = JSON.parse(String(previewCalls[0]?.[1]?.body));
    expect(firstBody.sample_mode).toBe("population_baseline");
    expect(firstBody.sampling_instructions).toBe("Include a broad comparison group across Singapore.");

    fireEvent.click(await screen.findByRole("button", { name: /re-sample/i }));
    await waitFor(() =>
      expect(
        vi.mocked(global.fetch).mock.calls.filter(([url]) => String(url).includes("/sampling/preview")).length,
      ).toBe(2),
    );

    const secondPreviewCalls = vi.mocked(global.fetch).mock.calls.filter(([url]) => String(url).includes("/sampling/preview"));
    const secondBody = JSON.parse(String(secondPreviewCalls[1]?.[1]?.body));
    expect(secondBody.sample_mode).toBe("population_baseline");
    expect(secondBody.sampling_instructions).toBe("Include a broad comparison group across Singapore.");
    expect(secondBody.agent_count).toBe(firstBody.agent_count);
    expect(secondBody.seed).not.toBe(firstBody.seed);
  });

  it("renders a read-only parsed summary and does not advertise an unsupported 5,000 agent maximum", async () => {
    global.fetch = vi.fn().mockImplementation(
      createAgentFetch({
        sessionId: "session-screen2",
        previewPayloads: [
          {
            session_id: "session-screen2",
            candidate_count: 640,
            sample_count: 4,
            sample_mode: "affected_groups",
            sample_seed: 21,
            parsed_sampling_instructions: {
              hard_filters: {
                occupation: ["teacher"],
              },
              soft_boosts: {
                age_cohort: ["youth"],
                planning_area: ["sengkang", "punggol"],
              },
              soft_penalties: {},
              exclusions: {
                industry: ["finance"],
              },
              distribution_targets: {
                planning_area: ["sengkang", "punggol"],
              },
              notes_for_ui: ["Bias toward younger teachers in the north-east, with finance excluded."],
              source: "gemini",
            },
            coverage: {
              planning_areas: ["Sengkang", "Punggol"],
              age_buckets: { "20-29": 2, "30-39": 2 },
            },
            sampled_personas: [],
            agent_graph: { nodes: [], links: [] },
            representativeness: { status: "balanced" },
            selection_diagnostics: { shortlist_count: 80, semantic_rerank_count: 32 },
          },
        ],
      }),
    ) as typeof fetch;

    render(
      <AppProvider>
        <SeedStage2Context />
        <AgentConfig />
      </AppProvider>,
    );

    expect(screen.queryByText("5,000")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/strategic parameters/i), {
      target: { value: "Bias toward younger teachers in the north-east, with finance excluded." },
    });
    fireEvent.click(screen.getByRole("button", { name: /sample population/i }));

    expect(await screen.findByText("Parsed Strategy Notes")).toBeInTheDocument();
    expect(screen.getAllByText("Bias toward younger teachers in the north-east, with finance excluded.").length).toBeGreaterThan(0);
  });

  it("shows a live sampling error instead of loading cached demo agents", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "live");
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.includes("/api/v2/console/session/session-screen2/filters")) {
        return {
          ok: true,
          json: async () => defaultFilters,
        } as Response;
      }

      if (url.includes("/api/v2/token-usage/session-screen2/estimate")) {
        return {
          ok: false,
          status: 502,
          statusText: "Bad Gateway",
          json: async () => ({ detail: "token usage unavailable" }),
        } as Response;
      }

      if (url.endsWith("/api/v2/token-usage/session-screen2")) {
        return {
          ok: false,
          status: 502,
          statusText: "Bad Gateway",
          json: async () => ({ detail: "runtime unavailable" }),
        } as Response;
      }

      if (url.includes("/api/v2/console/session/session-screen2/sampling/preview")) {
        return {
          ok: false,
          status: 502,
          statusText: "Bad Gateway",
          json: async () => ({ detail: "live sampling failed" }),
        } as Response;
      }

      if (url.endsWith("/demo-output.json")) {
        return {
          ok: true,
          json: async () => ({ population: { sampled_personas: [] } }),
        } as Response;
      }

      return {
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({ detail: `Unhandled fetch: ${url}` }),
      } as Response;
    }) as typeof fetch;

    render(
      <AppProvider>
        <SeedStage2Context />
        <AgentConfig />
      </AppProvider>,
    );

    await screen.findByRole("button", { name: /sample population/i });
    fireEvent.click(screen.getByRole("button", { name: /sample population/i }));

    expect(await screen.findByText("live sampling failed")).toBeInTheDocument();
    expect(
      vi.mocked(global.fetch).mock.calls.some(([url]) => String(url).endsWith("/demo-output.json")),
    ).toBe(false);
    expect(screen.queryByText(/Demo Population Loaded/i)).not.toBeInTheDocument();
  });
});

const defaultFilters = {
  session_id: "session-screen2",
  country: "singapore",
  use_case: "policy-review",
  filters: [
    {
      field: "age",
      type: "range",
      label: "Age Range",
      min: 18,
      max: 85,
      default_min: 20,
      default_max: 65,
      options: [],
    },
    {
      field: "planning_area",
      type: "multi-select-chips",
      label: "Planning Area",
      options: ["All Areas", "Central", "East", "West", "North"],
      default: ["All Areas"],
    },
    {
      field: "occupation",
      type: "dropdown",
      label: "Occupation",
      options: ["All Occupations", "Professional", "Service", "Clerical", "Teacher"],
      default: "All Occupations",
    },
    {
      field: "gender",
      type: "single-select-chips",
      label: "Gender",
      options: ["All", "Male", "Female"],
      default: "All",
    },
  ],
};

const defaultEstimate = {
  with_caching_usd: 0.42,
  without_caching_usd: 1.68,
  savings_pct: 75,
  model: "gemini-2.5-pro",
};

const defaultRuntime = {
  total_input_tokens: 12000,
  total_output_tokens: 3000,
  total_cached_tokens: 8000,
  estimated_cost_usd: 0.21,
  cost_without_caching_usd: 0.84,
  caching_savings_usd: 0.63,
  caching_savings_pct: 75,
  model: "gemini-2.5-pro",
};

function createAgentFetch({
  sessionId = "session-screen2",
  previewPayloads,
  filters = defaultFilters,
  estimate = defaultEstimate,
  runtime = defaultRuntime,
}: {
  sessionId?: string;
  previewPayloads: Array<Record<string, unknown>>;
  filters?: typeof defaultFilters;
  estimate?: typeof defaultEstimate;
  runtime?: typeof defaultRuntime;
}) {
  let previewIndex = 0;

  return async (input: RequestInfo | URL) => {
    const url = String(input);

    if (url.includes(`/api/v2/console/session/${sessionId}/filters`)) {
      return {
        ok: true,
        json: async () => filters,
      };
    }

    if (url.includes(`/api/v2/token-usage/${sessionId}/estimate`)) {
      return {
        ok: true,
        json: async () => estimate,
      };
    }

    if (url.endsWith(`/api/v2/token-usage/${sessionId}`)) {
      return {
        ok: true,
        json: async () => runtime,
      };
    }

    if (url.includes(`/api/v2/console/session/${sessionId}/sampling/preview`)) {
      const payload = previewPayloads[Math.min(previewIndex, previewPayloads.length - 1)] ?? previewPayloads[0];
      previewIndex += 1;
      return {
        ok: true,
        json: async () => payload,
      };
    }

    return {
      ok: false,
      status: 404,
      statusText: "Not Found",
      json: async () => ({ detail: `Unhandled fetch: ${url}` }),
    };
  };
}
