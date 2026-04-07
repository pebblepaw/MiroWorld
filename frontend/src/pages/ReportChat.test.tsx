import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppProvider, useApp } from "@/contexts/AppContext";
import ReportChat from "@/pages/ReportChat";

const toastMock = vi.hoisted(() => vi.fn());

vi.mock("@/hooks/use-toast", () => ({
  toast: toastMock,
  useToast: () => ({
    toasts: [],
    toast: toastMock,
    dismiss: vi.fn(),
  }),
}));

function SeedReportContext({ includeAgents = true }: { includeAgents?: boolean } = {}) {
  const {
    setSessionId,
    setSimulationComplete,
    completeStep,
    setCurrentStep,
    setAgents,
    setSimPosts,
    setCountry,
    setUseCase,
    setSimulationRounds,
  } = useApp();

  useEffect(() => {
    setSessionId("session-screen4");
    setSimulationComplete(true);
    completeStep(3);
    setCurrentStep(4);
    setCountry("singapore");
    setUseCase("public-policy-testing");
    setSimulationRounds(5);
    if (includeAgents) {
      setAgents([
        {
          id: "agent-neg-1",
          name: "Alex Tan",
          age: 33,
          gender: "Male",
          ethnicity: "Chinese",
          occupation: "Teacher",
          planningArea: "Woodlands",
          incomeBracket: "$2,000-$4,000",
          housingType: "4-Room",
          sentiment: "negative",
          approvalScore: 22,
        },
        {
          id: "agent-neg-2",
          name: "Priya Nair",
          age: 40,
          gender: "Female",
          ethnicity: "Indian",
          occupation: "Nurse",
          planningArea: "Jurong West",
          incomeBracket: "$4,000-$6,000",
          housingType: "4-Room",
          sentiment: "negative",
          approvalScore: 30,
        },
        {
          id: "agent-pos-1",
          name: "Janet Lee",
          age: 45,
          gender: "Female",
          ethnicity: "Chinese",
          occupation: "Manager",
          planningArea: "Queenstown",
          incomeBracket: "Above $15,000",
          housingType: "Condo",
          sentiment: "positive",
          approvalScore: 78,
        },
      ]);
      setSimPosts([
        {
          id: "post-1",
          agentId: "agent-neg-1",
          agentName: "Alex Tan",
          agentOccupation: "Teacher",
          agentArea: "Woodlands",
          title: "Costs are too high",
          content: "Families are stretched thin by current policy costs.",
          upvotes: 12,
          downvotes: 4,
          commentCount: 2,
          round: 2,
          timestamp: "Round 2",
          comments: [],
        },
      ]);
    } else {
      setAgents([]);
      setSimPosts([]);
    }
  }, [
    completeStep,
    includeAgents,
    setAgents,
    setCountry,
    setCurrentStep,
    setSessionId,
    setSimPosts,
    setSimulationComplete,
    setSimulationRounds,
    setUseCase,
  ]);

  return null;
}

function buildReportPayload() {
  return {
    session_id: "session-screen4",
    status: "complete",
    generated_at: "2026-04-06T10:00:00Z",
    executive_summary: "Live report summary from backend.",
    quick_stats: {
      agent_count: 3,
      round_count: 5,
      model: "gemini-2.0-flash",
      provider: "google",
    },
    metric_deltas: [
      {
        metric_name: "approval_rate",
        metric_label: "Approval Rate",
        metric_unit: "%",
        initial_value: 42,
        final_value: 57,
        delta: 15,
        direction: "up",
        report_title: "Policy Approval",
      },
      {
        metric_name: "rollout_support",
        metric_label: "Rollout Support",
        metric_unit: "text",
        type: "yes-no",
        initial_value: 25,
        final_value: 75,
        delta: 50,
        direction: "up",
        report_title: "Rollout Support",
      },
    ],
    sections: [
      {
        question: "Do you approve of this policy? Rate 1-10.",
        report_title: "## Policy Approval",
        type: "scale",
        answer: "**Support** increased after the final round of discussion.\n\n- Affordability concerns eased\n- Rollout clarity improved",
        metric: {
          metric_name: "approval_rate",
          metric_label: "Approval Rate",
          metric_unit: "%",
          initial_value: 42,
          final_value: 57,
          delta: 15,
          direction: "up",
          report_title: "Policy Approval",
        },
        evidence: [
          { agent_id: "agent-neg-1", post_id: "post-1", quote: "Families are stretched thin by current policy costs." },
          { agent_id: "agent-pos-1", post_id: "post-2", quote: "The policy can work if safeguards are clear." },
        ],
      },
      {
        question: "What specific aspects of this policy do you support or oppose, and why?",
        report_title: "Key Viewpoints",
        type: "open-ended",
        answer: "Most discussion centered on affordability and rollout fairness.\n\n1. Less pressure on households\n2. Clearer transition support",
        evidence: [
          { agent_id: "agent-neg-2", post_id: "post-3", quote: "I need stronger protections before I can support it." },
        ],
      },
    ],
    insight_blocks: [
      {
        type: "polarization_index",
        title: "Polarization Over Time",
        description: "How divided is public opinion across rounds?",
        data: {
          status: "complete",
          points: [
            { round: "R1", index: 0.2, severity: "low" },
            { round: "R5", index: 0.7, severity: "high" },
          ],
        },
      },
    ],
    preset_sections: [
      {
        title: "Recommendations",
        answer: "Lead with affordability safeguards and clearer rollout details.",
      },
    ],
    error: null,
  };
}

describe("ReportChat", () => {
  const originalFetch = global.fetch;
  const originalCreateObjectUrl = URL.createObjectURL;
  const originalRevokeObjectUrl = URL.revokeObjectURL;
  const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;

  beforeEach(() => {
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      value: vi.fn(),
      configurable: true,
      writable: true,
    });
    Object.defineProperty(URL, "createObjectURL", {
      value: vi.fn(() => "blob:docx"),
      configurable: true,
      writable: true,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      value: vi.fn(),
      configurable: true,
      writable: true,
    });
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
    toastMock.mockClear();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      value: originalScrollIntoView,
      configurable: true,
      writable: true,
    });
    Object.defineProperty(URL, "createObjectURL", {
      value: originalCreateObjectUrl,
      configurable: true,
      writable: true,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      value: originalRevokeObjectUrl,
      configurable: true,
      writable: true,
    });
    vi.restoreAllMocks();
  });

  it("sends group chat messages to the live backend endpoint and renders live responses", async () => {
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/report/generate") || url.includes("/report/full") || url.includes("/report")) {
        return { ok: true, json: async () => buildReportPayload() } as Response;
      }
      if (url.includes("/chat/group")) {
        return {
          ok: true,
          json: async () => ({
            session_id: "session-screen4",
            responses: [
              {
                agent_id: "agent-neg-1",
                agent_name: "Alex Tan",
                content: "Live backend group response",
              },
            ],
          }),
        } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    }) as typeof fetch;

    render(
      <AppProvider>
        <SeedReportContext />
        <ReportChat />
      </AppProvider>,
    );

    const input = await screen.findByPlaceholderText(/ask the group a question/i);
    fireEvent.change(input, { target: { value: "What changed over the rounds?" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });

    await waitFor(() => {
      const chatCall = vi
        .mocked(global.fetch)
        .mock.calls.find(([url]) => String(url).includes("/chat/group"));
      expect(chatCall).toBeTruthy();
    });

    const chatCall = vi.mocked(global.fetch).mock.calls.find(([url]) => String(url).includes("/chat/group"));
    expect(chatCall).toBeDefined();
    expect(JSON.parse(String(chatCall?.[1]?.body))).toEqual({
      segment: "dissenters",
      message: "What changed over the rounds?",
    });

    expect(await screen.findByText("Live backend group response")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /top supporters/i }));
    const supporterInput = await screen.findByPlaceholderText(/ask the group a question/i);
    fireEvent.change(supporterInput, { target: { value: "What should supporters prioritize next?" } });
    fireEvent.keyDown(supporterInput, { key: "Enter", code: "Enter" });

    await waitFor(() => {
      const supportCall = vi
        .mocked(global.fetch)
        .mock.calls.filter(([url]) => String(url).includes("/chat/group"))
        .at(-1);
      expect(supportCall).toBeTruthy();
    });
    const supportCall = vi.mocked(global.fetch).mock.calls.filter(([url]) => String(url).includes("/chat/group")).at(-1);
    expect(JSON.parse(String(supportCall?.[1]?.body)).segment).toBe("supporters");

    const reportAgentButton = (await screen.findAllByRole("button", { name: /alex tan/i })).find(
      (button) => button.textContent?.trim() === "Alex Tan",
    );
    expect(reportAgentButton).toBeTruthy();
    fireEvent.click(reportAgentButton!);
    expect(await screen.findByText("Agent Profile")).toBeInTheDocument();
    expect(screen.getByText("Teacher")).toBeInTheDocument();
    expect(screen.getByText(/core viewpoint/i)).toBeInTheDocument();
  });

  it("uses the live 1:1 endpoint for direct agent chat", async () => {
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/report/generate") || url.includes("/report/full") || url.includes("/report")) {
        return { ok: true, json: async () => buildReportPayload() } as Response;
      }
      if (url.includes("/chat/agent/agent-neg-1")) {
        return {
          ok: true,
          json: async () => ({
            session_id: "session-screen4",
            response: "Live one-on-one reply",
            agent_id: "agent-neg-1",
            agent_name: "Alex Tan",
          }),
        } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    }) as typeof fetch;

    render(
      <AppProvider>
        <SeedReportContext />
        <ReportChat />
      </AppProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "1:1 Chat" }));
    const search = await screen.findByPlaceholderText(/search agents/i);
    fireEvent.change(search, { target: { value: "Alex" } });
    fireEvent.click(await screen.findByRole("button", { name: /alex tan teacher/i }));

    const input = await screen.findByPlaceholderText(/ask alex/i);
    fireEvent.change(input, { target: { value: "How did your view change?" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });

    await waitFor(() => {
      const chatCall = vi
        .mocked(global.fetch)
        .mock.calls.find(([url]) => String(url).includes("/chat/agent/agent-neg-1"));
      expect(chatCall).toBeTruthy();
    });

    expect(await screen.findByText("Live one-on-one reply")).toBeInTheDocument();
    expect(screen.getByText("How did your view change?").closest("div")).toHaveClass("rounded-br-sm");
    expect(screen.getByText("Live one-on-one reply").closest("div")).toHaveClass("rounded-bl-sm");
  });

  it("renders V2 report sections, evidence quotes, and clickable agent drill-down", async () => {
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/report/generate") || url.includes("/report/full") || url.includes("/report")) {
        return { ok: true, json: async () => buildReportPayload() } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    }) as typeof fetch;

    render(
      <AppProvider>
        <SeedReportContext />
        <ReportChat />
      </AppProvider>,
    );

    expect((await screen.findAllByText("Policy Approval")).length).toBeGreaterThan(0);
    expect(screen.getByText("Approval Rate")).toBeInTheDocument();
    expect(screen.getByText("Polarization Over Time")).toBeInTheDocument();
    expect(screen.getByText("Recommendations")).toBeInTheDocument();
    expect(screen.queryByText("Supporting Views")).not.toBeInTheDocument();
    expect(screen.queryByText("Dissenting Views")).not.toBeInTheDocument();
    expect(
      screen.getAllByText((_, element) => Boolean(element?.textContent?.includes("Families are stretched thin by current policy costs."))).length,
    ).toBeGreaterThan(0);

    expect(screen.queryByText("agent-neg-1")).not.toBeInTheDocument();
    const agentButton = (await screen.findAllByRole("button", { name: /^alex tan$/i })).find(
      (button) => button.textContent?.trim() === "Alex Tan",
    );
    expect(agentButton).toBeTruthy();
    fireEvent.click(agentButton!);

    expect(await screen.findByText("Agent Chat")).toBeInTheDocument();
    expect(screen.getAllByText("Alex Tan").length).toBeGreaterThan(0);
  });

  it("formats metrics as initial to final values, keeps yes-no metrics numeric, and strips markdown markers from report copy", async () => {
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/report/generate") || url.includes("/report/full") || url.includes("/report")) {
        return { ok: true, json: async () => buildReportPayload() } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    }) as typeof fetch;

    render(
      <AppProvider>
        <SeedReportContext />
        <ReportChat />
      </AppProvider>,
    );

    expect((await screen.findAllByText("Policy Approval")).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText((_, element) => Boolean(element?.textContent?.includes("42%") && element?.textContent?.includes("57%"))).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText((_, element) => Boolean(element?.textContent?.includes("25%") && element?.textContent?.includes("75%"))).length,
    ).toBeGreaterThan(0);
    expect(screen.queryByText(/0text/i)).not.toBeInTheDocument();
    expect(
      screen.getAllByText((_, element) => Boolean(element?.textContent?.includes("Support increased after the final round of discussion."))).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText((_, element) => Boolean(element?.textContent?.includes("Affordability concerns eased"))).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText((_, element) => Boolean(element?.textContent?.includes("Rollout clarity improved"))).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText((_, element) => Boolean(element?.textContent?.includes("Most discussion centered on affordability and rollout fairness."))).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText((_, element) => Boolean(element?.textContent?.includes("Less pressure on households"))).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText((_, element) => Boolean(element?.textContent?.includes("Clearer transition support"))).length,
    ).toBeGreaterThan(0);
  });

  it("exports report through the backend DOCX endpoint", async () => {
    const createObjectUrlSpy = vi.spyOn(URL, "createObjectURL");
    const revokeObjectUrlSpy = vi.spyOn(URL, "revokeObjectURL");
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/report/export")) {
        return {
          ok: true,
          blob: async () => new Blob(["docx"], { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" }),
        } as Response;
      }
      if (url.includes("/report/generate") || url.includes("/report/full") || url.includes("/report")) {
        return { ok: true, json: async () => buildReportPayload() } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    }) as typeof fetch;

    render(
      <AppProvider>
        <SeedReportContext />
        <ReportChat />
      </AppProvider>,
    );

    fireEvent.click(await screen.findByRole("button", { name: /export/i }));

    await waitFor(() => {
      const exportCall = vi
        .mocked(global.fetch)
        .mock.calls.find(([url]) => String(url).includes("/report/export"));
      expect(exportCall).toBeTruthy();
    });
    expect(createObjectUrlSpy).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
    expect(revokeObjectUrlSpy).toHaveBeenCalled();
  });

  it("switches the main view modes without breaking the report/chat split", async () => {
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/report/generate") || url.includes("/report/full") || url.includes("/report")) {
        return { ok: true, json: async () => buildReportPayload() } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    }) as typeof fetch;

    render(
      <AppProvider>
        <SeedReportContext />
        <ReportChat />
      </AppProvider>,
    );

    expect(await screen.findByText("Executive Summary")).toBeInTheDocument();
    expect(document.querySelector("div.overflow-y-auto.scrollbar-thin.p-6.space-y-6")).toBeTruthy();
    expect(document.querySelector("div.flex-1.overflow-y-auto.px-4.py-4.space-y-3.scrollbar-thin")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Chat" }));
    expect(screen.queryByText("Executive Summary")).not.toBeInTheDocument();
    expect(screen.getByText("Agent Chat")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Report" }));
    expect(screen.getByText("Executive Summary")).toBeInTheDocument();
  });

  it("shows a live report error instead of auto-loading the cached demo report", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "live");
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/report/generate")) {
        return {
          ok: false,
          status: 502,
          statusText: "Bad Gateway",
          json: async () => ({ detail: "report generation unavailable" }),
        } as Response;
      }
      if (url.includes("/report")) {
        return {
          ok: false,
          status: 404,
          statusText: "Not Found",
          json: async () => ({ detail: "live report unavailable" }),
        } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    }) as typeof fetch;

    render(
      <AppProvider>
        <SeedReportContext />
        <ReportChat />
      </AppProvider>,
    );

    expect(await screen.findByText("report generation unavailable")).toBeInTheDocument();
    expect(screen.queryByText("Generational Divide")).not.toBeInTheDocument();
    expect(screen.queryByText(/Showing cached demo report/i)).not.toBeInTheDocument();
  });

  it("shows live placeholders instead of fabricated report stats when agents are unavailable", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "live");
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/report/generate") || url.includes("/report/full") || url.includes("/report")) {
        return { ok: true, json: async () => buildReportPayload() } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    }) as typeof fetch;

    render(
      <AppProvider>
        <SeedReportContext includeAgents={false} />
        <ReportChat />
      </AppProvider>,
    );

    expect(await screen.findByText("Live report summary from backend.")).toBeInTheDocument();
    expect(
      screen.getAllByText((_, element) => Boolean(element?.textContent?.includes("Singapore · Public Policy Testing · 3 agents · 5 rounds"))).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("Approval Rate")).toBeInTheDocument();
    expect(screen.getAllByText("42% -> 57%").length).toBeGreaterThan(0);
    expect(screen.queryByText("Supporting Views")).not.toBeInTheDocument();
    expect(screen.queryByText("Dissenting Views")).not.toBeInTheDocument();
  });

  it("does not enqueue demo replies when live chat returns no responses", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "live");
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/report/generate") || url.includes("/report/full") || url.includes("/report")) {
        return { ok: true, json: async () => buildReportPayload() } as Response;
      }
      if (url.includes("/chat/group")) {
        return {
          ok: true,
          json: async () => ({
            session_id: "session-screen4",
            responses: [],
          }),
        } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    }) as typeof fetch;

    render(
      <AppProvider>
        <SeedReportContext />
        <ReportChat />
      </AppProvider>,
    );

    const input = await screen.findByPlaceholderText(/ask the group a question/i);
    fireEvent.change(input, { target: { value: "What changed over the rounds?" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });

    await waitFor(() => {
      expect(vi.mocked(global.fetch).mock.calls.some(([url]) => String(url).includes("/chat/group"))).toBe(true);
    });
    await waitFor(() => {
      expect(toastMock).toHaveBeenCalled();
    });
    expect(toastMock.mock.calls.at(-1)?.[0]).toMatchObject({
      title: "Live chat unavailable",
      description: "The backend returned no agent responses.",
      variant: "destructive",
    });
    expect(screen.queryByText("Live backend group response")).not.toBeInTheDocument();
  });

  it("does not enqueue demo replies when live direct chat fails", async () => {
    vi.stubEnv("VITE_BOOT_MODE", "live");
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/report/generate") || url.includes("/report/full") || url.includes("/report")) {
        return { ok: true, json: async () => buildReportPayload() } as Response;
      }
      if (url.includes("/chat/agent/agent-neg-1")) {
        return {
          ok: false,
          status: 502,
          statusText: "Bad Gateway",
          json: async () => ({ detail: "agent chat unavailable" }),
        } as Response;
      }
      return { ok: true, json: async () => ({}) } as Response;
    }) as typeof fetch;

    render(
      <AppProvider>
        <SeedReportContext />
        <ReportChat />
      </AppProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "1:1 Chat" }));
    const search = await screen.findByPlaceholderText(/search agents/i);
    fireEvent.change(search, { target: { value: "Alex" } });
    fireEvent.click(await screen.findByRole("button", { name: /alex tan teacher/i }));

    const input = await screen.findByPlaceholderText(/ask alex/i);
    fireEvent.change(input, { target: { value: "How did your view change?" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });

    await waitFor(() => {
      expect(vi.mocked(global.fetch).mock.calls.some(([url]) => String(url).includes("/chat/agent/agent-neg-1"))).toBe(true);
    });
    await waitFor(() => {
      expect(toastMock).toHaveBeenCalled();
    });
    expect(toastMock.mock.calls.at(-1)?.[0]).toMatchObject({
      title: "Live chat unavailable",
      description: "agent chat unavailable",
      variant: "destructive",
    });
    expect(screen.queryByText("Live one-on-one reply")).not.toBeInTheDocument();
  });
});
