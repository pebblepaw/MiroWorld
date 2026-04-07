import { render, screen, waitFor, within } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppProvider, useApp } from "@/contexts/AppContext";
import Analytics from "@/pages/Analytics";

function SeedAnalyticsContext() {
  const { setSessionId, setSimulationRounds, setCountry, setUseCase } = useApp();

  useEffect(() => {
    setSessionId("session-screen5");
    setCountry("singapore");
    setUseCase("policy-review");
    setSimulationRounds(5);
  }, [setCountry, setSessionId, setSimulationRounds, setUseCase]);

  return null;
}

function SeedAnalyticsContextWithAgents() {
  const { setSessionId, setSimulationRounds, setCountry, setUseCase, setAgents } = useApp();

  useEffect(() => {
    setSessionId("session-screen5");
    setCountry("singapore");
    setUseCase("policy-review");
    setSimulationRounds(5);
    setAgents([
      {
        id: "agent-1",
        name: "Supporter One",
        age: 30,
        gender: "Female",
        ethnicity: "Chinese",
        occupation: "Teacher",
        planningArea: "Woodlands",
        incomeBracket: "$4,000-$6,000",
        housingType: "4-Room",
        sentiment: "positive",
        approvalScore: 72,
      },
      {
        id: "agent-2",
        name: "Neutral Two",
        age: 42,
        gender: "Male",
        ethnicity: "Malay",
        occupation: "Nurse",
        planningArea: "Queenstown",
        incomeBracket: "$6,000-$8,000",
        housingType: "5-Room",
        sentiment: "neutral",
        approvalScore: 50,
      },
      {
        id: "agent-3",
        name: "Dissenter Three",
        age: 36,
        gender: "Female",
        ethnicity: "Indian",
        occupation: "Manager",
        planningArea: "Jurong West",
        incomeBracket: "$8,000-$10,000",
        housingType: "Condo",
        sentiment: "negative",
        approvalScore: 24,
      },
    ]);
  }, [setAgents, setCountry, setSessionId, setSimulationRounds, setUseCase]);

  return null;
}

describe("Analytics", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("loads live analytics endpoints and renders API-backed leaders and viral posts", async () => {
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/analytics/polarization")) {
        return {
          ok: true,
          json: async () => ({
            points: [
              { round: "R1", index: 0.21, severity: "moderate" },
              { round: "R2", index: 0.72, severity: "high" },
            ],
          }),
        } as Response;
      }
      if (url.includes("/analytics/opinion-flow")) {
        return {
          ok: true,
          json: async () => ({
            initial: { supporter: 120, neutral: 40, dissenter: 90 },
            final: { supporter: 75, neutral: 20, dissenter: 155 },
            flows: [
              { from: "supporter", to: "supporter", count: 62 },
              { from: "supporter", to: "dissenter", count: 48 },
              { from: "neutral", to: "dissenter", count: 19 },
              { from: "dissenter", to: "dissenter", count: 89 },
            ],
          }),
        } as Response;
      }
      if (url.includes("/analytics/influence")) {
        return {
          ok: true,
          json: async () => ({
            top_influencers: [
              {
                name: "API Leader",
                stance: "supporter",
                influence: 0.94,
                top_view: "API-generated supporter perspective.",
                top_post: "API top post content.",
              },
            ],
          }),
        } as Response;
      }
      if (url.includes("/analytics/cascades")) {
        return {
          ok: true,
          json: async () => ({
            viral_posts: [
              {
                author: "API Cascade Author",
                stance: "dissenter",
                title: "API Viral Thread",
                content: "API-generated viral thread body.",
                likes: 201,
                dislikes: 39,
                comments: [],
              },
            ],
          }),
        } as Response;
      }
      return {
        ok: true,
        json: async () => ({}),
      } as Response;
    }) as typeof fetch;

    render(
      <AppProvider>
        <SeedAnalyticsContext />
        <Analytics />
      </AppProvider>,
    );

    expect(screen.getByText(/loading analytics/i)).toBeInTheDocument();
    expect(await screen.findByText("API Leader")).toBeInTheDocument();
    expect(screen.getByText("API Viral Thread")).toBeInTheDocument();

    const opinionFlowSection = screen.getByText("Opinion Flow").closest("section");
    expect(opinionFlowSection).not.toBeNull();
    expect(within(opinionFlowSection as HTMLElement).getByTitle("supporter: 120")).toBeInTheDocument();
    expect(within(opinionFlowSection as HTMLElement).getByTitle("dissenter: 155")).toBeInTheDocument();
    expect((opinionFlowSection as HTMLElement).querySelectorAll("svg")[1]?.querySelectorAll("path")).toHaveLength(4);

    await waitFor(() => {
      expect(
        vi.mocked(global.fetch).mock.calls.some(([url]) => String(url).includes("/analytics/polarization")),
      ).toBe(true);
      expect(
        vi.mocked(global.fetch).mock.calls.some(([url]) => String(url).includes("/analytics/opinion-flow")),
      ).toBe(true);
      expect(
        vi.mocked(global.fetch).mock.calls.some(([url]) => String(url).includes("/analytics/influence")),
      ).toBe(true);
      expect(
        vi.mocked(global.fetch).mock.calls.some(([url]) => String(url).includes("/analytics/cascades")),
      ).toBe(true);
    });
  });

  it("normalizes object top_post payloads into readable leader text", async () => {
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/analytics/polarization")) {
        return { ok: true, json: async () => ({ points: [] }) } as Response;
      }
      if (url.includes("/analytics/opinion-flow")) {
        return {
          ok: true,
          json: async () => ({
            initial: { supporter: 1, neutral: 0, dissenter: 0 },
            final: { supporter: 1, neutral: 0, dissenter: 0 },
            flows: [],
          }),
        } as Response;
      }
      if (url.includes("/analytics/influence")) {
        return {
          ok: true,
          json: async () => ({
            top_influencers: [
              {
                name: "Object Leader",
                stance: "supporter",
                influence: 0.88,
                top_view: "Object-backed lead view.",
                top_post: {
                  content: "Readable top post excerpt.",
                  body: "Readable top post body.",
                  title: "Readable top post title.",
                },
              },
            ],
          }),
        } as Response;
      }
      if (url.includes("/analytics/cascades")) {
        return { ok: true, json: async () => ({ viral_posts: [] }) } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    }) as typeof fetch;

    render(
      <AppProvider>
        <SeedAnalyticsContext />
        <Analytics />
      </AppProvider>,
    );

    expect(await screen.findByText("Object Leader")).toBeInTheDocument();
    expect(screen.getByText("Object-backed lead view.")).toBeInTheDocument();
    expect(screen.queryByText("Readable top post excerpt.")).not.toBeInTheDocument();
    expect(screen.queryByText("[object Object]")).not.toBeInTheDocument();
  });

  it("resolves agent ids to names and prefers viewpoint summaries over raw post text", async () => {
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/analytics/polarization")) {
        return { ok: true, json: async () => ({ points: [] }) } as Response;
      }
      if (url.includes("/analytics/opinion-flow")) {
        return {
          ok: true,
          json: async () => ({
            initial: { supporter: 1, neutral: 0, dissenter: 0 },
            final: { supporter: 1, neutral: 0, dissenter: 0 },
            flows: [{ from: "supporter", to: "supporter", count: 1 }],
          }),
        } as Response;
      }
      if (url.includes("/analytics/influence")) {
        return {
          ok: true,
          json: async () => ({
            top_influencers: [
              {
                agent_id: "agent-1",
                stance: "supporter",
                influence: 0.91,
                summary: "Supporters want clearer safeguards and rollout timing.",
                top_view: "Analysis Question 3: raw post text that should not be shown.",
                top_post: "Raw post body that should stay hidden.",
              },
            ],
          }),
        } as Response;
      }
      if (url.includes("/analytics/cascades")) {
        return {
          ok: true,
          json: async () => ({
            viral_posts: [
              {
                author: "agent-2",
                stance: "dissenter",
                title: "Raw author id should be resolved",
                content: "Agents are reacting to the policy.",
                likes: 12,
                dislikes: 3,
                comments: [
                  {
                    author: "agent-3",
                    stance: "mixed",
                    content: "Comment author ids should also resolve.",
                    likes: 4,
                    dislikes: 1,
                  },
                ],
              },
            ],
          }),
        } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    }) as typeof fetch;

    render(
      <AppProvider>
        <SeedAnalyticsContextWithAgents />
        <Analytics />
      </AppProvider>,
    );

    expect(await screen.findByText("Supporter One")).toBeInTheDocument();
    expect(screen.getByText("Supporters want clearer safeguards and rollout timing.")).toBeInTheDocument();
    expect(screen.queryByText("Analysis Question 3: raw post text that should not be shown.")).not.toBeInTheDocument();
    expect(screen.getByText("Neutral Two")).toBeInTheDocument();
    expect(screen.getByText("Dissenter Three")).toBeInTheDocument();
    expect(screen.queryByText("agent-2")).not.toBeInTheDocument();
    expect(screen.queryByText("agent-3")).not.toBeInTheDocument();
    expect(screen.getByText("Raw author id should be resolved")).toBeInTheDocument();
  });

  it("shows an error notice and falls back to local demo analytics when API calls fail", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("analytics unavailable")) as typeof fetch;

    render(
      <AppProvider>
        <SeedAnalyticsContext />
        <Analytics />
      </AppProvider>,
    );

    expect(await screen.findByText(/showing demo analytics data/i)).toBeInTheDocument();
    expect(screen.getAllByText("Raj Kumar").length).toBeGreaterThan(0);
  });

  it("shows loading placeholders for each analytics block while requests are pending", async () => {
    global.fetch = vi.fn(() => new Promise<Response>(() => {})) as typeof fetch;

    render(
      <AppProvider>
        <SeedAnalyticsContext />
        <Analytics />
      </AppProvider>,
    );

    expect(await screen.findByText(/loading analytics data/i)).toBeInTheDocument();
    expect(screen.getByText(/loading polarization data/i)).toBeInTheDocument();
    expect(screen.getByText(/loading opinion flow data/i)).toBeInTheDocument();
    expect(screen.getByText(/loading leader data/i)).toBeInTheDocument();
    expect(screen.getByText(/loading viral post data/i)).toBeInTheDocument();
  });

  it("shows empty states for each analytics block when the API returns no data", async () => {
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/analytics/polarization")) {
        return { ok: true, json: async () => ({ points: [] }) } as Response;
      }
      if (url.includes("/analytics/opinion-flow")) {
        return {
          ok: true,
          json: async () => ({
            initial: { supporter: 0, neutral: 0, dissenter: 0 },
            final: { supporter: 0, neutral: 0, dissenter: 0 },
            flows: [],
          }),
        } as Response;
      }
      if (url.includes("/analytics/influence")) {
        return { ok: true, json: async () => ({ top_influencers: [] }) } as Response;
      }
      if (url.includes("/analytics/cascades")) {
        return { ok: true, json: async () => ({ viral_posts: [] }) } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    }) as typeof fetch;

    render(
      <AppProvider>
        <SeedAnalyticsContext />
        <Analytics />
      </AppProvider>,
    );

    await waitFor(() => {
      expect(screen.queryByText(/Loading analytics data/i)).not.toBeInTheDocument();
    });
    expect(screen.getByText(/No polarization data yet/i)).toBeInTheDocument();
    expect(screen.getByText(/No opinion flow data yet/i)).toBeInTheDocument();
    expect(screen.getByText(/No leader data yet/i)).toBeInTheDocument();
    expect(screen.getByText(/No viral post data yet/i)).toBeInTheDocument();
    expect(screen.getByText(/No demographic data yet/i)).toBeInTheDocument();
  });

  it("wraps demographic groups in chunks and preserves sentiment color semantics", async () => {
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/analytics/polarization")) {
        return { ok: true, json: async () => ({ points: [] }) } as Response;
      }
      if (url.includes("/analytics/opinion-flow")) {
        return {
          ok: true,
          json: async () => ({
            initial: { supporter: 1, neutral: 1, dissenter: 1 },
            final: { supporter: 1, neutral: 1, dissenter: 1 },
            flows: [{ from: "supporter", to: "supporter", count: 1 }],
          }),
        } as Response;
      }
      if (url.includes("/analytics/influence")) {
        return { ok: true, json: async () => ({ top_influencers: [] }) } as Response;
      }
      if (url.includes("/analytics/cascades")) {
        return { ok: true, json: async () => ({ viral_posts: [] }) } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    }) as typeof fetch;

    render(
      <AppProvider>
        <SeedAnalyticsContextWithAgents />
        <Analytics />
      </AppProvider>,
    );

    const mapHeading = await screen.findByText("Demographic Sentiment Map");
    const mapSection = mapHeading.closest("section");
    expect(mapSection).not.toBeNull();
    expect(mapSection).toHaveClass("surface-card");
    expect(document.querySelector("div.mx-auto.flex.w-full.max-w-\\[1700px\\].flex-col.gap-5.px-6.py-6")).toBeTruthy();
    expect(screen.getByText("Simulation Analytics").closest("header")).toHaveClass("surface-card");
    expect(mapSection?.querySelector(".flex.flex-wrap.gap-x-8.gap-y-10")).toBeTruthy();
    expect(screen.getByTitle("Supporter One · positive")).toHaveStyle({ backgroundColor: "hsl(var(--data-green))" });
    expect(screen.getByTitle("Neutral Two · neutral")).toHaveStyle({ backgroundColor: "hsl(0 0% 45%)" });
    expect(screen.getByTitle("Dissenter Three · negative")).toHaveStyle({ backgroundColor: "hsl(var(--data-red))" });
  });

  it("shows a live analytics error instead of filling in demo leaders and viral posts", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "live");
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/analytics/polarization")) {
        return {
          ok: false,
          status: 502,
          statusText: "Bad Gateway",
          json: async () => ({ detail: "polarization unavailable" }),
        } as Response;
      }
      if (url.includes("/analytics/opinion-flow")) {
        return {
          ok: false,
          status: 502,
          statusText: "Bad Gateway",
          json: async () => ({ detail: "opinion flow unavailable" }),
        } as Response;
      }
      if (url.includes("/analytics/influence")) {
        return {
          ok: false,
          status: 502,
          statusText: "Bad Gateway",
          json: async () => ({ detail: "influence unavailable" }),
        } as Response;
      }
      if (url.includes("/analytics/cascades")) {
        return {
          ok: false,
          status: 502,
          statusText: "Bad Gateway",
          json: async () => ({ detail: "cascades unavailable" }),
        } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    }) as typeof fetch;

    render(
      <AppProvider>
        <SeedAnalyticsContext />
        <Analytics />
      </AppProvider>,
    );

    expect(await screen.findByText("Live analytics returned incomplete data.")).toBeInTheDocument();
    expect(screen.queryByText("Raj Kumar")).not.toBeInTheDocument();
    expect(screen.queryByText("API Leader")).not.toBeInTheDocument();
    expect(screen.queryByText("API Viral Thread")).not.toBeInTheDocument();
  });
});
