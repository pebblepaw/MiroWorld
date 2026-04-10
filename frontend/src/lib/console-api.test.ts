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
        policy_summary: "summary",
        rounds: 3,
      }),
    ).rejects.toThrow("simulate missing");

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(
      fetchSpy.mock.calls.some(([url]) => String(url).includes("/simulation/start")),
    ).toBe(false);
  });


  it("sends V2 session config patches with analysis questions through the canonical config route", async () => {
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
});
