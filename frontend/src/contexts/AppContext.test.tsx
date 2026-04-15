import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppProvider, useApp } from "@/contexts/AppContext";
import { resetBundledDemoState } from "@/lib/console-api";

const DEMO_BUNDLE_KEY_STORAGE = "miroworld-demo-static-bundle-key";

function makeResponse(body: unknown) {
  return {
    ok: true,
    json: async () => body,
  } as Response;
}

function DemoStateProbe() {
  const app = useApp();

  return (
    <>
      <span data-testid="session-id">{app.sessionId ?? "none"}</span>
      <span data-testid="current-step">{String(app.currentStep)}</span>
      <span data-testid="completed-steps">{app.completedSteps.join(",")}</span>
      <span data-testid="country">{app.country}</span>
      <span data-testid="use-case">{app.useCase}</span>
    </>
  );
}

function makeDemoOutput(sessionId: string) {
  return {
    session: {
      session_id: sessionId,
    },
    source_run: {
      country: "singapore",
      use_case: "public-policy-testing",
      provider: "google",
      model: "gemini-2.5-flash-lite",
      rounds: 10,
    },
    analysis_questions: [
      {
        question: "Do you approve of this policy?",
        type: "scale",
        metric_name: "approval_rate",
        report_title: "Approval Rate",
      },
    ],
    population: {
      session_id: sessionId,
      sample_count: 1,
      sample_seed: 7,
      sampled_personas: [
        {
          agent_id: "agent-demo-1",
          persona: {
            display_name: "Aisha Rahman",
            age: 34,
            sex: "Female",
            occupation: "teacher",
            planning_area: "Bedok",
          },
          selection_reason: {
            score: 0.9,
          },
        },
      ],
    },
    simulationState: {
      session_id: sessionId,
      status: "completed",
      planned_rounds: 10,
      current_round: 10,
      counters: {
        posts: 6,
        comments: 12,
        reactions: 18,
        active_authors: 1,
      },
      top_threads: [],
    },
  };
}

describe("AppContext demo-static hydration", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.stubEnv("VITE_BOOT_MODE", "demo-static");
    window.sessionStorage.clear();
    resetBundledDemoState();
  });

  afterEach(() => {
    window.sessionStorage.clear();
    resetBundledDemoState();
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("resets stale persisted demo session state when the bundled demo changes", async () => {
    window.sessionStorage.setItem(
      "miroworld-app-state",
      JSON.stringify({
        sessionId: "stale-demo-session",
        currentStep: 3,
        completedSteps: [1, 2, 3],
        country: "usa",
        useCase: "product-market-research",
        analysisActiveTab: "viral-posts",
        simSelectedRound: 10,
        simSortBy: "popular",
        simControversyBoostEnabled: true,
      }),
    );
    window.sessionStorage.setItem(DEMO_BUNDLE_KEY_STORAGE, "stale-demo-session");
    window.sessionStorage.setItem("miroworld-report-stale-demo-session", JSON.stringify({ sections: [{ report_title: "Old report" }] }));
    window.sessionStorage.setItem("miroworld-analytics-stale-demo-session", JSON.stringify({ leaderData: [{ name: "Old leader" }] }));

    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/demo-output.json")) {
        return makeResponse(makeDemoOutput("fresh-demo-session"));
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }) as typeof fetch;

    render(
      <AppProvider>
        <DemoStateProbe />
      </AppProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("session-id")).toHaveTextContent("fresh-demo-session"));

    expect(screen.getByTestId("current-step")).toHaveTextContent("1");
    expect(screen.getByTestId("completed-steps")).toHaveTextContent("");
    expect(screen.getByTestId("country")).toHaveTextContent("singapore");
    expect(screen.getByTestId("use-case")).toHaveTextContent("public-policy-testing");
    expect(window.sessionStorage.getItem("miroworld-report-stale-demo-session")).toBeNull();
    expect(window.sessionStorage.getItem("miroworld-analytics-stale-demo-session")).toBeNull();
    expect(window.sessionStorage.getItem(DEMO_BUNDLE_KEY_STORAGE)).toBe("fresh-demo-session");
  });
});
