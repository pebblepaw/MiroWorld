import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "@/App";
import { resetBundledDemoState } from "@/lib/console-api";

vi.mock("@/components/AppSidebar", () => ({
  AppSidebar: () => <aside>Sidebar</aside>,
}));

vi.mock("@/components/StepProgress", () => ({
  StepProgress: () => <div>Step Progress</div>,
}));

vi.mock("@/pages/PolicyUpload", () => ({
  default: () => <div>Policy Upload Screen</div>,
}));

vi.mock("@/pages/AgentConfig", () => ({
  default: () => <div>Agent Config Screen</div>,
}));

vi.mock("@/pages/Simulation", () => ({
  default: () => <div>Simulation Screen</div>,
}));

vi.mock("@/pages/ReportChat", () => ({
  default: () => <div>Report Screen</div>,
}));

vi.mock("@/pages/Analytics", () => ({
  default: () => <div>Analytics Screen</div>,
}));

vi.mock("@/components/OnboardingModal", () => ({
  OnboardingModal: ({ isOpen }: { isOpen: boolean }) => (isOpen ? <div>Configure your simulation environment</div> : null),
}));

function makeResponse(body: unknown) {
  return {
    ok: true,
    json: async () => body,
  } as Response;
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

describe("App demo-static modal behavior", () => {
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

  it("keeps the onboarding modal closed when reloading into an existing demo-static session", async () => {
    window.sessionStorage.setItem(
      "miroworld-app-state",
      JSON.stringify({
        sessionId: "session-cca48d2e",
        currentStep: 3,
        completedSteps: [1, 2, 3],
        country: "singapore",
        useCase: "public-policy-testing",
      }),
    );

    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/demo-output.json")) {
        return makeResponse(makeDemoOutput("session-cca48d2e"));
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }) as typeof fetch;

    render(<App />);

    await waitFor(() => expect(screen.getByText("Simulation Screen")).toBeInTheDocument());
    expect(screen.queryByText("Configure your simulation environment")).not.toBeInTheDocument();
  });
});
