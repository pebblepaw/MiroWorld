import { act, render, screen, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Analysis from "@/pages/Analysis";
import { AppProvider, useApp } from "@/contexts/AppContext";

function SeedStage4Context() {
  const { setSessionId, setSimulationComplete, setCurrentStep, completeStep } = useApp();

  useEffect(() => {
    setSessionId("session-screen4");
    setSimulationComplete(true);
    completeStep(3);
    setCurrentStep(4);
  }, [completeStep, setCurrentStep, setSessionId, setSimulationComplete]);

  return null;
}

describe("Analysis", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("starts report generation asynchronously and renders the fixed report schema when complete", async () => {
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          session_id: "session-screen4",
          status: "running",
          generated_at: null,
          executive_summary: null,
          insight_cards: [],
          support_themes: [],
          dissent_themes: [],
          demographic_breakdown: [],
          influential_content: [],
          recommendations: [],
          risks: [],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          session_id: "session-screen4",
          status: "running",
          generated_at: null,
          executive_summary: null,
          insight_cards: [],
          support_themes: [],
          dissent_themes: [],
          demographic_breakdown: [],
          influential_content: [],
          recommendations: [],
          risks: [],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          session_id: "session-screen4",
          status: "completed",
          generated_at: "2026-03-21T10:15:00Z",
          executive_summary: "Support increased after affordability-focused discussion.",
          insight_cards: [
            { title: "Woodlands youth moved most", summary: "The strongest approval shift came from active younger residents.", severity: "high" },
          ],
          support_themes: [
            { theme: "Affordability", summary: "Subsidies lower weekly participation costs.", evidence: ["The subsidy would make weekly training affordable."] },
          ],
          dissent_themes: [
            { theme: "Coverage gaps", summary: "Some agents worried inactive households were underserved.", evidence: ["Need wider outreach."] },
          ],
          demographic_breakdown: [
            { segment: "Woodlands youth", approval_rate: 0.74, dissent_rate: 0.12, sample_size: 18 },
          ],
          influential_content: [
            { content_type: "post", author_agent_id: "agent-0001", summary: "Affordability post drove early support.", engagement_score: 9 },
          ],
          recommendations: [
            { title: "Lead with affordability messaging", rationale: "This was the strongest support driver.", priority: "high" },
          ],
          risks: [
            { title: "Quiet cohorts underheard", summary: "Lower-activity households may still have unmet concerns.", severity: "medium" },
          ],
        }),
      }) as typeof fetch;

    render(
      <AppProvider>
        <SeedStage4Context />
        <Analysis />
      </AppProvider>,
    );

    await act(async () => {
      await Promise.resolve();
    });

    expect(global.fetch).toHaveBeenCalledTimes(2);
    expect(vi.mocked(global.fetch).mock.calls[0][0]).toContain("/api/v2/console/session/session-screen4/report/generate");
    expect(vi.mocked(global.fetch).mock.calls[1][0]).toContain("/api/v2/console/session/session-screen4/report/full");
    expect(screen.getByText(/generating ai report/i)).toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(1600);
      await Promise.resolve();
    });

    expect(screen.getByText("Support increased after affordability-focused discussion.")).toBeInTheDocument();
    expect(screen.getByText("Woodlands youth moved most")).toBeInTheDocument();
    expect(screen.getByText("Lead with affordability messaging")).toBeInTheDocument();
    expect(screen.getByText("Quiet cohorts underheard")).toBeInTheDocument();
  });
});
