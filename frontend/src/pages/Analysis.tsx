import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, FileText, Loader2, MessagesSquare, Radar, RefreshCw } from "lucide-react";

import { GlassCard } from "@/components/GlassCard";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApp } from "@/contexts/AppContext";
import { StructuredReportState, generateReport, getStructuredReport } from "@/lib/console-api";

const POLL_INTERVAL_MS = 1500;

const EMPTY_REPORT: StructuredReportState = {
  session_id: "",
  status: "idle",
  generated_at: null,
  executive_summary: null,
  insight_cards: [],
  support_themes: [],
  dissent_themes: [],
  demographic_breakdown: [],
  influential_content: [],
  recommendations: [],
  risks: [],
  error: null,
};

export default function Analysis() {
  const { sessionId, simulationComplete } = useApp();
  const [activeTab, setActiveTab] = useState("report");
  const [reportState, setReportState] = useState<StructuredReportState>(EMPTY_REPORT);
  const [reportError, setReportError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const startedRef = useRef<string | null>(null);

  const beginReportGeneration = useCallback(async () => {
    if (!sessionId) {
      setReportError("Start a simulation before generating a report.");
      return;
    }
    startedRef.current = sessionId;
    setLoading(true);
    setReportError(null);
    try {
      const [nextState, polled] = await Promise.all([
        generateReport(sessionId),
        getStructuredReport(sessionId),
      ]);
      setReportState(nextState);
      setReportState(polled);
    } catch (error) {
      startedRef.current = null;
      setReportError(error instanceof Error ? error.message : "Unable to generate report.");
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useLayoutEffect(() => {
    if (!simulationComplete || !sessionId || activeTab !== "report") {
      return;
    }
    if (startedRef.current === sessionId) {
      return;
    }
    void beginReportGeneration();
  }, [activeTab, beginReportGeneration, sessionId, simulationComplete]);

  useEffect(() => {
    if (!sessionId || activeTab !== "report" || reportState.status !== "running") {
      return;
    }

    const timer = window.setInterval(async () => {
      try {
        const nextState = await getStructuredReport(sessionId);
        setReportState(nextState);
      } catch (error) {
        setReportError(error instanceof Error ? error.message : "Unable to refresh report.");
      }
    }, POLL_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [activeTab, reportState.status, sessionId]);

  const hasCompletedReport = reportState.status === "completed";
  const insightCards = reportState.insight_cards ?? [];
  const supportThemes = reportState.support_themes ?? [];
  const dissentThemes = reportState.dissent_themes ?? [];
  const demographicBreakdown = reportState.demographic_breakdown ?? [];
  const influentialContent = reportState.influential_content ?? [];
  const recommendations = reportState.recommendations ?? [];
  const risks = reportState.risks ?? [];

  const statusTone = useMemo(() => {
    if (reportState.status === "completed") return "text-success";
    if (reportState.status === "failed") return "text-destructive";
    return "text-primary";
  }, [reportState.status]);

  return (
    <div className="flex flex-col gap-6 h-full p-6 overflow-y-auto scrollbar-thin">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-foreground">Analysis</h2>
          <p className="text-sm text-muted-foreground">
            Structured report generation from the live McKAInsey simulation, with Screen 4A active and the other views held on mock data for now.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className={`text-xs uppercase tracking-[0.22em] font-mono ${statusTone}`}>
            {reportState.status === "idle" ? "Awaiting Report" : reportState.status}
          </div>
          <Button
            onClick={() => {
              startedRef.current = null;
              void beginReportGeneration();
            }}
            disabled={!sessionId || loading}
            variant="outline"
            className="border-white/12 text-foreground hover:bg-white/6"
          >
            {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> Starting...</> : <><RefreshCw className="w-4 h-4" /> Rebuild Report</>}
          </Button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col gap-4">
        <TabsList className="w-fit bg-white/[0.04] border border-white/10">
          <TabsTrigger value="report">Reports &amp; Insights</TabsTrigger>
          <TabsTrigger value="opinions">Opinions Feed</TabsTrigger>
          <TabsTrigger value="friction">Friction Map</TabsTrigger>
        </TabsList>

        <TabsContent value="report" className="mt-0 flex-1">
          {!simulationComplete && (
            <GlassCard className="p-8 text-center">
              <div className="text-lg font-semibold text-foreground">Run Screen 3 first</div>
              <p className="text-sm text-muted-foreground mt-2">
                The report agent needs a completed live simulation before it can assemble the fixed Screen 4A report.
              </p>
            </GlassCard>
          )}

          {simulationComplete && (
            <div className="space-y-4">
              {(loading || reportState.status === "running") && (
                <GlassCard className="p-5 border border-primary/25">
                  <div className="flex items-center gap-3 text-primary">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="text-sm font-semibold">Generating report</span>
                  </div>
                  <p className="text-sm text-muted-foreground mt-2">
                    The report agent is consolidating checkpoint shifts, influential posts, and demographic approval patterns.
                  </p>
                </GlassCard>
              )}

              {(reportError || reportState.error || reportState.status === "failed") && (
                <GlassCard className="p-5 border border-destructive/30">
                  <div className="flex items-center gap-3 text-destructive">
                    <AlertTriangle className="w-4 h-4" />
                    <span className="text-sm font-semibold">Report generation failed</span>
                  </div>
                  <p className="text-sm text-muted-foreground mt-2">{reportError ?? reportState.error ?? "Gemini did not return a valid structured report."}</p>
                </GlassCard>
              )}

              {hasCompletedReport && (
                <>
                  <div className="grid grid-cols-1 xl:grid-cols-[1.15fr_0.85fr] gap-4">
                    <GlassCard className="p-5">
                      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.22em] text-muted-foreground mb-3">
                        <FileText className="w-4 h-4 text-primary" />
                        Executive Summary
                      </div>
                      <p className="text-base leading-relaxed text-foreground">
                        {reportState.executive_summary}
                      </p>
                      <div className="text-[11px] font-mono text-muted-foreground mt-4">
                        Generated {formatTimestamp(reportState.generated_at)}
                      </div>
                    </GlassCard>

                    <GlassCard className="p-5">
                      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.22em] text-muted-foreground mb-3">
                        <CheckCircle2 className="w-4 h-4 text-primary" />
                        Key Actionable Insights
                      </div>
                      <div className="space-y-3">
                        {insightCards.map((card, index) => (
                          <div key={`${card.title ?? index}`} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                            <div className="flex items-center justify-between gap-3">
                              <div className="text-sm font-semibold text-foreground">{stringValue(card.title, "Untitled insight")}</div>
                              <span className="text-[10px] uppercase tracking-[0.18em] text-primary">{stringValue(card.severity, "info")}</span>
                            </div>
                            <p className="text-sm text-muted-foreground mt-2">{stringValue(card.summary, "")}</p>
                          </div>
                        ))}
                      </div>
                    </GlassCard>
                  </div>

                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                    <ThemeColumn
                      title="Strongest Supporting Views"
                      icon={<CheckCircle2 className="w-4 h-4 text-success" />}
                      items={supportThemes}
                    />
                    <ThemeColumn
                      title="Strongest Dissenting Views"
                      icon={<AlertTriangle className="w-4 h-4 text-destructive" />}
                      items={dissentThemes}
                    />
                  </div>

                  <div className="grid grid-cols-1 xl:grid-cols-[0.95fr_1.05fr] gap-4">
                    <GlassCard className="p-5">
                      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.22em] text-muted-foreground mb-3">
                        <Radar className="w-4 h-4 text-primary" />
                        Approval / Dissent Breakdown
                      </div>
                      <div className="space-y-3">
                        {demographicBreakdown.map((entry, index) => (
                          <div key={`${entry.segment ?? index}`} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                            <div className="flex items-center justify-between gap-3">
                              <div className="text-sm font-semibold text-foreground">{stringValue(entry.segment, "Unknown segment")}</div>
                              <span className="text-xs font-mono text-muted-foreground">n={numberValue(entry.sample_size)}</span>
                            </div>
                            <div className="grid grid-cols-2 gap-3 mt-3">
                              <RateCard label="Approval" value={formatRate(entry.approval_rate)} tone="text-success" />
                              <RateCard label="Dissent" value={formatRate(entry.dissent_rate)} tone="text-destructive" />
                            </div>
                          </div>
                        ))}
                      </div>
                    </GlassCard>

                    <GlassCard className="p-5">
                      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.22em] text-muted-foreground mb-3">
                        <MessagesSquare className="w-4 h-4 text-primary" />
                        Influential Posts &amp; Agents
                      </div>
                      <div className="space-y-3">
                        {influentialContent.map((entry, index) => (
                          <div key={`${entry.summary ?? index}`} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                            <div className="flex items-center justify-between gap-3">
                              <div className="text-sm font-semibold text-foreground">{stringValue(entry.content_type, "content")}</div>
                              <span className="text-xs font-mono text-primary">{numberValue(entry.engagement_score)}</span>
                            </div>
                            <p className="text-sm text-muted-foreground mt-2">{stringValue(entry.summary, "")}</p>
                            {entry.author_agent_id ? (
                              <div className="text-[11px] text-muted-foreground font-mono mt-3">
                                Author {stringValue(entry.author_agent_id, "")}
                              </div>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    </GlassCard>
                  </div>

                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                    <RecommendationColumn title="Recommendations" items={recommendations} />
                    <RecommendationColumn title="Risks / Minority View Watchouts" items={risks} />
                  </div>
                </>
              )}
            </div>
          )}
        </TabsContent>

        <TabsContent value="opinions" className="mt-0">
          <MockStageCard
            title="Opinions Feed"
            description="Screen 4B remains on mock data in this phase. Navigation stays live, but the real opinion feed will be implemented after Reports & Insights is locked."
          />
        </TabsContent>

        <TabsContent value="friction" className="mt-0">
          <MockStageCard
            title="Friction Map"
            description="Screen 4C remains on mock data in this phase. The live Singapore friction map will be wired after Screen 4A is approved."
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function ThemeColumn({ title, icon, items }: { title: string; icon: JSX.Element; items: Array<Record<string, unknown>> }) {
  return (
    <GlassCard className="p-5">
      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.22em] text-muted-foreground mb-3">
        {icon}
        {title}
      </div>
      <div className="space-y-3">
        {items.map((item, index) => (
          <div key={`${item.theme ?? item.title ?? index}`} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
            <div className="text-sm font-semibold text-foreground">{stringValue(item.theme ?? item.title, "Untitled theme")}</div>
            <p className="text-sm text-muted-foreground mt-2">{stringValue(item.summary, "")}</p>
            {Array.isArray(item.evidence) && item.evidence.length > 0 ? (
              <div className="mt-3 text-xs text-muted-foreground">
                “{stringValue(item.evidence[0], "")}”
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </GlassCard>
  );
}

function RecommendationColumn({ title, items }: { title: string; items: Array<Record<string, unknown>> }) {
  return (
    <GlassCard className="p-5">
      <div className="text-xs uppercase tracking-[0.22em] text-muted-foreground mb-3">{title}</div>
      <div className="space-y-3">
        {items.map((item, index) => (
          <div key={`${item.title ?? index}`} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="text-sm font-semibold text-foreground">{stringValue(item.title, "Untitled item")}</div>
              {item.priority || item.severity ? (
                <span className="text-[10px] uppercase tracking-[0.18em] text-primary">{stringValue(item.priority ?? item.severity, "")}</span>
              ) : null}
            </div>
            <p className="text-sm text-muted-foreground mt-2">{stringValue(item.rationale ?? item.summary, "")}</p>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}

function RateCard({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
      <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">{label}</div>
      <div className={`text-lg font-mono font-semibold mt-1 ${tone}`}>{value}</div>
    </div>
  );
}

function MockStageCard({ title, description }: { title: string; description: string }) {
  return (
    <GlassCard className="p-8 text-center">
      <div className="text-lg font-semibold text-foreground">{title}</div>
      <p className="text-sm text-muted-foreground mt-2 max-w-2xl mx-auto">{description}</p>
    </GlassCard>
  );
}

function stringValue(value: unknown, fallback: string): string {
  if (typeof value === "string" && value.trim()) {
    return value.trim();
  }
  return fallback;
}

function numberValue(value: unknown): string {
  const number = Number(value ?? 0);
  if (!Number.isFinite(number)) return "0";
  return String(number);
}

function formatRate(value: unknown): string {
  const number = Number(value ?? 0);
  if (!Number.isFinite(number)) return "0%";
  return `${Math.round(number * 100)}%`;
}

function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "just now";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}
