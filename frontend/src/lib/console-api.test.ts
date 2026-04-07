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
