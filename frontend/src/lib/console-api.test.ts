import { afterEach, describe, expect, it, vi } from "vitest";

describe("console-api live-mode routing", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
    vi.resetModules();
    vi.restoreAllMocks();
  });

  it("does not fall back to legacy simulation routes in live mode", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "live");

    const { startSimulation } = await import("./console-api");
    const fetchSpy = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/v2/console/session/session-1/simulate")) {
        return {
          ok: false,
          status: 404,
          statusText: "Not Found",
          json: async () => ({ detail: "simulate missing" }),
        } as Response;
      }
      return {
        ok: true,
        json: async () => ({ ok: true }),
      } as Response;
    });
    global.fetch = fetchSpy as typeof fetch;

    await expect(
      startSimulation("session-1", {
        subject_summary: "summary",
        rounds: 3,
      }),
    ).rejects.toThrow("simulate missing");

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(
      fetchSpy.mock.calls.some(([url]) => String(url).includes("/simulation/start")),
    ).toBe(false);
  });


  it("sends session config patches with analysis questions through the canonical config route", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "live");

    const { updateV2SessionConfig } = await import("./console-api");
    const fetchSpy = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/v2/console/session/session-1/config")) {
        expect(init?.method).toBe("PATCH");
        expect(JSON.parse(String(init?.body))).toEqual({
          country: "singapore",
          use_case: "product-market-research",
          provider: "openai",
          model: "gpt-4o-mini",
          api_key: "sk-test",
          guiding_prompt: null,
          analysis_questions: [{ question: "Would you use this?", type: "yes-no" }],
        });
        return {
          ok: true,
          json: async () => ({
            session_id: "session-1",
            country: "singapore",
            use_case: "product-market-research",
            provider: "openai",
            model: "gpt-4o-mini",
            api_key_configured: true,
            guiding_prompt: null,
          }),
        } as Response;
      }
      return {
        ok: true,
        json: async () => ({ ok: true }),
      } as Response;
    });
    global.fetch = fetchSpy as typeof fetch;

    await expect(
      updateV2SessionConfig("session-1", {
        country: "singapore",
        use_case: "product-market-research",
        provider: "openai",
        model: "gpt-4o-mini",
        api_key: "sk-test",
        guiding_prompt: null,
        analysis_questions: [{ question: "Would you use this?", type: "yes-no" }],
      }),
    ).resolves.toMatchObject({
      session_id: "session-1",
      model: "gpt-4o-mini",
      provider: "openai",
    });

    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("does not fall back to legacy report routes in live mode", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "live");

    const { generateReport, getStructuredReport } = await import("./console-api");
    const fetchSpy = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/v2/console/session/session-1/report/generate")) {
        return {
          ok: false,
          status: 404,
          statusText: "Not Found",
          json: async () => ({ detail: "report generation missing" }),
        } as Response;
      }
      if (url.endsWith("/api/v2/console/session/session-1/report")) {
        return {
          ok: false,
          status: 404,
          statusText: "Not Found",
          json: async () => ({ detail: "legacy report route" }),
        } as Response;
      }
      return {
        ok: true,
        json: async () => ({ ok: true }),
      } as Response;
    });
    global.fetch = fetchSpy as typeof fetch;

    await expect(
      generateReport("session-1"),
    ).rejects.toThrow("report generation missing");
    await expect(
      getStructuredReport("session-1"),
    ).rejects.toThrow("legacy report route");

    expect(
      fetchSpy.mock.calls.some(([url]) => String(url).includes("/report/full")),
    ).toBe(false);
  });

  it("treats a missing hosted knowledge artifact as not-ready instead of a frontend error", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "live");

    const { getKnowledgeArtifact } = await import("./console-api");
    const fetchSpy = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/v2/console/session/session-1/knowledge")) {
        return new Response(null, {
          status: 204,
        });
      }
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    global.fetch = fetchSpy as typeof fetch;

    await expect(getKnowledgeArtifact("session-1")).resolves.toBeNull();
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("ignores non-json hosted knowledge fallback responses caused by SPA rewrites", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "live");

    const { getKnowledgeArtifact } = await import("./console-api");
    const fetchSpy = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/v2/console/session/session-1/knowledge")) {
        return new Response("<!doctype html><html><body>index</body></html>", {
          status: 200,
          headers: { "Content-Type": "text/html" },
        });
      }
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    global.fetch = fetchSpy as typeof fetch;

    await expect(getKnowledgeArtifact("session-1")).resolves.toBeNull();
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });
});

describe("console-api demo-static routing", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
    vi.resetModules();
    vi.restoreAllMocks();
  });

  it("hydrates bundled demo data without calling API routes", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "demo-static");

    const demoPayload = {
      session: { session_id: "demo-session" },
      source_run: {
        country: "singapore",
        provider: "google",
        model: "gemini-2.5-flash-lite",
        use_case: "public-policy-testing",
      },
      report: {
        session_id: "demo-session",
        status: "complete",
        executive_summary: "Bundled report summary",
      },
      population: {
        session_id: "demo-session",
        sample_seed: 7,
        sampled_personas: [{ agent_id: "agent-1", persona: {}, selection_reason: { score: 0.8, matched_facets: [], matched_document_entities: [], instruction_matches: [], bm25_terms: [], semantic_summary: "", semantic_relevance: 0.8, geographic_relevance: 0.7, socioeconomic_relevance: 0.7, digital_behavior_relevance: 0.7, filter_alignment: 0.9 } }],
      },
      simulationState: {
        session_id: "demo-session",
        status: "completed",
        counters: { posts: 1, comments: 0, reactions: 0, active_authors: 1 },
        checkpoint_status: {},
        latest_metrics: { approval_rate: 62 },
        top_threads: [],
        discussion_momentum: {},
        recent_events: [],
        event_count: 1,
        last_round: 3,
      },
      analytics: {
        polarization: { session_id: "demo-session", score: 0.42 },
      },
    };

    const fetchSpy = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      expect(url.includes("/api/v2/")).toBe(false);
      return {
        ok: true,
        json: async () => demoPayload,
      } as Response;
    });
    global.fetch = fetchSpy as typeof fetch;

    const {
      createV2Session,
      getAnalyticsPolarization,
      getStructuredReport,
      getSimulationState,
    } = await import("./console-api");

    await expect(
      createV2Session({
        country: "singapore",
        provider: "google",
        model: "gemini-2.5-flash-lite",
        use_case: "public-policy-testing",
      }),
    ).resolves.toEqual({ session_id: "demo-session" });

    await expect(getStructuredReport("demo-session")).resolves.toMatchObject({
      session_id: "demo-session",
      executive_summary: "Bundled report summary",
      status: "complete",
    });

    await expect(getSimulationState("demo-session")).resolves.toMatchObject({
      session_id: "demo-session",
      status: "completed",
      event_count: 1,
    });

    await expect(getAnalyticsPolarization("demo-session")).resolves.toEqual({
      session_id: "demo-session",
      score: 0.42,
    });

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(String(fetchSpy.mock.calls[0]?.[0])).toMatch(/demo-output\.json$/);
  });

  it("keeps remote demo-static providers marked as BYOK", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "demo-static");

    const { getModelProviderCatalog, getV2Providers } = await import("./console-api");

    await expect(getV2Providers()).resolves.toEqual(
      expect.arrayContaining([
        expect.objectContaining({ name: "gemini", requires_api_key: true }),
        expect.objectContaining({ name: "openai", requires_api_key: true }),
        expect.objectContaining({ name: "ollama", requires_api_key: false }),
      ]),
    );

    await expect(getModelProviderCatalog()).resolves.toMatchObject({
      providers: expect.arrayContaining([
        expect.objectContaining({ id: "google", requires_api_key: true }),
        expect.objectContaining({ id: "openai", requires_api_key: true }),
        expect.objectContaining({ id: "ollama", requires_api_key: false }),
      ]),
    });
  });

  it("hydrates top-level V2 demo reports and reads cached simulation posts from cascades", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "demo-static");

    const demoPayload = {
      session: { session_id: "demo-session" },
      source_run: {
        country: "singapore",
        provider: "google",
        model: "gemini-2.5-flash-lite",
        use_case: "public-policy-testing",
      },
      population: {
        session_id: "demo-session",
        sample_seed: 7,
        sampled_personas: [
          {
            agent_id: "agent-1",
            display_name: "Alex Tan",
            persona: { occupation: "Teacher", planning_area: "Woodlands" },
            selection_reason: {
              score: 0.8,
              matched_facets: [],
              matched_document_entities: [],
              instruction_matches: [],
              bm25_terms: [],
              semantic_summary: "",
              semantic_relevance: 0.8,
              geographic_relevance: 0.7,
              socioeconomic_relevance: 0.7,
              digital_behavior_relevance: 0.7,
              filter_alignment: 0.9,
            },
          },
        ],
      },
      report: {
        session_id: "demo-session",
        status: "complete",
        executive_summary: "Wrapped V2 report summary",
        metric_deltas: [
          {
            metric_name: "approval_rate",
            metric_label: "Approval Rate",
            metric_unit: "%",
            initial_value: 40,
            final_value: 55,
            delta: 15,
            direction: "up",
            report_title: "Policy Approval",
          },
        ],
        sections: [
          {
            question: "What changed?",
            report_title: "Policy Approval",
            type: "scale",
            bullets: ["Support improved after safeguards were clarified."],
            evidence: [],
          },
        ],
        preset_sections: [
          {
            title: "Recommendations",
            bullets: ["Lead with affordability safeguards."],
          },
        ],
      },
      analytics: {
        cascades: {
          viral_posts: [
            {
              post_id: "post-1",
              author_agent_id: "agent-1",
              author_name: "Alex Tan",
              title: "Affordability worries are still rising",
              content: "Families still need clearer safeguards.",
              likes: 14,
              dislikes: 2,
              comments: [
                {
                  comment_id: "comment-1",
                  author_agent_id: "agent-1",
                  author_name: "Alex Tan",
                  content: "Clearer rollout details would help.",
                  likes: 3,
                },
              ],
            },
          ],
        },
      },
      simulationState: {
        session_id: "demo-session",
        status: "completed",
        counters: { posts: 1, comments: 1, reactions: 0, active_authors: 1 },
        checkpoint_status: {},
        latest_metrics: {},
        top_threads: [],
        discussion_momentum: {},
        recent_events: [],
        event_count: 1,
        last_round: 3,
      },
    };

    const fetchSpy = vi.fn(async () => {
      return {
        ok: true,
        json: async () => demoPayload,
      } as Response;
    });
    global.fetch = fetchSpy as typeof fetch;

    const { getBundledDemoSimulationPosts, getStructuredReport } = await import("./console-api");

    await expect(getStructuredReport("demo-session")).resolves.toMatchObject({
      session_id: "demo-session",
      executive_summary: "Wrapped V2 report summary",
      metric_deltas: [
        expect.objectContaining({ metric_name: "approval_rate" }),
      ],
      sections: [
        expect.objectContaining({
          bullets: ["Support improved after safeguards were clarified."],
        }),
      ],
      preset_sections: [
        expect.objectContaining({
          bullets: ["Lead with affordability safeguards."],
        }),
      ],
    });

    await expect(getBundledDemoSimulationPosts()).resolves.toMatchObject([
      expect.objectContaining({
        id: "post-1",
        agentId: "agent-1",
        title: "Affordability worries are still rising",
        commentCount: 1,
        comments: [
          expect.objectContaining({
            id: "comment-1",
            content: "Clearer rollout details would help.",
          }),
        ],
      }),
    ]);

    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("prefers sampled persona display names over bundled sg_agent aliases and serves metric-scoped analytics", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "demo-static");

    const demoPayload = {
      session: { session_id: "demo-session" },
      source_run: {
        country: "singapore",
        provider: "google",
        model: "gemini-2.5-flash",
        use_case: "public-policy-testing",
      },
      analysis_questions: [
        {
          question: "Support?",
          type: "scale",
          metric_name: "approval_rate",
          metric_label: "Approval Rate",
          metric_unit: "%",
        },
        {
          question: "Worried about jobs?",
          type: "yes-no",
          metric_name: "ai_job_worry",
          metric_label: "AI Job Replacement Concern",
        },
      ],
      population: {
        session_id: "demo-session",
        sampled_personas: [
          {
            agent_id: "agent-0004",
            display_name: "Syed Anwar Bin Wah Tjahjono",
            persona: { display_name: "Syed Anwar Bin Wah Tjahjono", occupation: "Technician", planning_area: "Punggol" },
            selection_reason: { score: 0.4 },
          },
          {
            agent_id: "agent-0016",
            display_name: "Real Madrid",
            persona: { display_name: "Real Madrid", occupation: "Engineer", planning_area: "Bukit Merah" },
            selection_reason: { score: 0.7 },
          },
        ],
      },
      analytics: {
        polarization: {
          session_id: "demo-session",
          series: [{ round: "Start", polarization_index: 0.15, severity: "low" }],
        },
        opinion_flow: {
          session_id: "demo-session",
          initial: { supporter: 12, neutral: 20, dissenter: 3 },
          final: { supporter: 18, neutral: 10, dissenter: 7 },
          flows: [{ from: "neutral", to: "supporter", count: 8 }],
        },
        agent_stances: {
          session_id: "demo-session",
          stances: [{ agent_id: "agent-0004", score: 8 }],
        },
        cascades: {
          viral_posts: [
            {
              post_id: "post-1",
              author: "agent-0004",
              author_name: "sg_agent_4",
              title: "Demo thread",
              content: "Demo content",
              likes: 4,
              dislikes: 1,
              comments: [
                {
                  comment_id: "comment-1",
                  author: "agent-0016",
                  author_name: "sg_agent_16",
                  content: "Demo reply",
                  likes: 2,
                },
              ],
            },
          ],
        },
        by_metric: {
          approval_rate: {
            polarization: {
              session_id: "demo-session",
              series: [{ round: "Start", polarization_index: 0.66, severity: "high" }],
            },
            opinion_flow: {
              session_id: "demo-session",
              initial: { supporter: 30, neutral: 5, dissenter: 0 },
              final: { supporter: 10, neutral: 5, dissenter: 20 },
              flows: [{ from: "supporter", to: "dissenter", count: 12 }],
            },
            agent_stances: {
              session_id: "demo-session",
              stances: [{ agent_id: "agent-0004", score: 2 }],
            },
          },
        },
      },
      simulationState: {
        session_id: "demo-session",
        status: "completed",
        counters: { posts: 1, comments: 1, reactions: 4, active_authors: 2 },
        checkpoint_status: {},
        latest_metrics: {},
        top_threads: [],
        discussion_momentum: {},
        recent_events: [],
        event_count: 1,
        last_round: 10,
      },
    };

    global.fetch = vi.fn(async () => {
      return {
        ok: true,
        json: async () => demoPayload,
      } as Response;
    }) as typeof fetch;

    const {
      getAnalyticsAgentStances,
      getAnalyticsOpinionFlow,
      getAnalyticsPolarization,
      getBundledDemoSimulationPosts,
    } = await import("./console-api");

    const posts = await getBundledDemoSimulationPosts();

    expect(posts[0]?.agentName).toBe("Syed Anwar Bin Wah Tjahjono");
    expect(posts[0]?.comments[0]?.agentName).toBe("Real Madrid");

    await expect(getAnalyticsPolarization("demo-session", "approval_rate")).resolves.toMatchObject({
      series: [{ polarization_index: 0.66 }],
    });
    await expect(getAnalyticsOpinionFlow("demo-session", "approval_rate")).resolves.toMatchObject({
      final: { dissenter: 20 },
    });
    await expect(getAnalyticsAgentStances("demo-session", "approval_rate")).resolves.toMatchObject({
      stances: [{ agent_id: "agent-0004", score: 2 }],
    });
  });
});
