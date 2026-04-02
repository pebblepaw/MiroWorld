import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import AgentConfig from "@/pages/AgentConfig";
import { AppProvider, useApp } from "@/contexts/AppContext";

vi.mock("@/components/SingaporeMap", () => ({
  SingaporeMap: () => <div data-testid="singapore-map" />,
}));

function SeedStage2Context() {
  const { setSessionId, setKnowledgeArtifact, setKnowledgeGraphReady } = useApp();

  useEffect(() => {
    setSessionId("session-screen2");
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
  }, [setKnowledgeArtifact, setKnowledgeGraphReady, setSessionId]);

  return null;
}

describe("AgentConfig", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("requests a live sampled cohort and renders backend diagnostics and graph data", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
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
      }),
    }) as typeof fetch;

    render(
      <AppProvider>
        <SeedStage2Context />
        <AgentConfig />
      </AppProvider>,
    );

    fireEvent.change(screen.getByLabelText(/strategic parameters/i), {
      target: { value: "Bias toward younger teachers and parents in the north-east." },
    });

    fireEvent.click(screen.getByRole("button", { name: /sample population/i }));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));

    const request = vi.mocked(global.fetch).mock.calls[0];
    expect(request[0]).toContain("/api/v2/console/session/session-screen2/sampling/preview");
    const body = JSON.parse(String(request[1]?.body));
    expect(body.agent_count).toBe(2);
    expect(body.sample_mode).toBe("affected_groups");
    expect(body.sampling_instructions).toBe("Bias toward younger teachers and parents in the north-east.");
    expect(typeof body.seed).toBe("number");

    expect(await screen.findByText("Candidate Shortlist")).toBeInTheDocument();
    expect(screen.getByText("824")).toBeInTheDocument();
    expect(screen.getByText("Semantic Rerank")).toBeInTheDocument();
    expect(screen.getByText("Industry Sector Mix")).toBeInTheDocument();
    expect(screen.getByText("Parsed Strategy Notes")).toBeInTheDocument();
    expect(screen.getAllByText("Bias toward younger teachers and parents in the north-east.").length).toBeGreaterThan(0);
    expect(screen.getByText("Cohort Explorer")).toBeInTheDocument();
    expect(screen.getByLabelText("Persona agent-0001")).toBeInTheDocument();
    expect(screen.getByLabelText("Persona agent-0002")).toBeInTheDocument();
    expect(screen.getByLabelText("Persona agent-0003")).toBeInTheDocument();
  });

  it("switches to baseline mode and re-samples with a fresh seed using the same config", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
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
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
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
        }),
      }) as typeof fetch;

    render(
      <AppProvider>
        <SeedStage2Context />
        <AgentConfig />
      </AppProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: /singapore baseline/i }));
    fireEvent.change(screen.getByLabelText(/strategic parameters/i), {
      target: { value: "Include a broad comparison group across Singapore." },
    });

    fireEvent.click(screen.getByRole("button", { name: /sample population/i }));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));

    const firstBody = JSON.parse(String(vi.mocked(global.fetch).mock.calls[0][1]?.body));
    expect(firstBody.sample_mode).toBe("population_baseline");
    expect(firstBody.sampling_instructions).toBe("Include a broad comparison group across Singapore.");

    fireEvent.click(await screen.findByRole("button", { name: /re-sample/i }));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));

    const secondBody = JSON.parse(String(vi.mocked(global.fetch).mock.calls[1][1]?.body));
    expect(secondBody.sample_mode).toBe("population_baseline");
    expect(secondBody.sampling_instructions).toBe("Include a broad comparison group across Singapore.");
    expect(secondBody.agent_count).toBe(firstBody.agent_count);
    expect(secondBody.seed).not.toBe(firstBody.seed);
  });

  it("renders a read-only parsed summary and does not advertise an unsupported 5,000 agent maximum", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
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
      }),
    }) as typeof fetch;

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
});
