import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { 
  AlertTriangle, 
  CheckCircle2, 
  FileText, 
  Loader2, 
  MessagesSquare, 
  Radar, 
  RefreshCw,
  Users,
  TrendingUp,
  Lightbulb,
  ShieldAlert,
  Target,
  Filter,
  ChevronDown,
  Sparkles
} from "lucide-react";

import { GlassCard } from "@/components/GlassCard";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApp } from "@/contexts/AppContext";
import { StructuredReportState, generateReport, getStructuredReport } from "@/lib/console-api";

const POLL_INTERVAL_MS = 1500;

// Filter types for cohort explorer
type CohortFilter = "all" | "occupation" | "age" | "planning_area" | "gender";

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
  const { sessionId, simulationComplete, analysisActiveTab: activeTab, setAnalysisActiveTab: setActiveTab } = useApp();
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

  // Cohort Explorer State
  const [cohortFilter, setCohortFilter] = useState<CohortFilter>("all");
  const [selectedSegment, setSelectedSegment] = useState<string | null>(null);

  // Demo data for cohort explorer - in real mode this would come from API
  const cohortData = useMemo(() => {
    // Generate mock agent data based on population
    const agents = Array.from({ length: 250 }, (_, i) => {
      const occupations = ["Teacher", "Manager", "Engineer", "Nurse", "Sales", "Clerical", "Service", "Professional"];
      const areas = ["Central", "East", "West", "North", "North-East"];
      const occupation = occupations[Math.floor(Math.random() * occupations.length)];
      const age = Math.floor(Math.random() * 45) + 20; // 20-65
      const gender = Math.random() > 0.5 ? "Male" : "Female";
      const area = areas[Math.floor(Math.random() * areas.length)];
      
      // Generate stance based on demo approval rates (97.6% -> 0%)
      // Most agents shifted from approve to dissent
      const stance = Math.random() > 0.1 ? "dissent" : "approve";
      
      return {
        id: `agent-${i.toString().padStart(4, '0')}`,
        name: `Agent ${i + 1}`,
        occupation,
        age,
        gender,
        area,
        stance,
      };
    });

    // Group by filter type
    const grouped: Record<string, typeof agents> = {};
    
    if (cohortFilter === "occupation") {
      agents.forEach(agent => {
        if (!grouped[agent.occupation]) grouped[agent.occupation] = [];
        grouped[agent.occupation].push(agent);
      });
    } else if (cohortFilter === "age") {
      const ageRanges = {
        "20-29": agents.filter(a => a.age >= 20 && a.age < 30),
        "30-39": agents.filter(a => a.age >= 30 && a.age < 40),
        "40-49": agents.filter(a => a.age >= 40 && a.age < 50),
        "50+": agents.filter(a => a.age >= 50),
      };
      Object.entries(ageRanges).forEach(([range, agents]) => {
        if (agents.length > 0) grouped[range] = agents;
      });
    } else if (cohortFilter === "planning_area") {
      agents.forEach(agent => {
        if (!grouped[agent.area]) grouped[agent.area] = [];
        grouped[agent.area].push(agent);
      });
    } else if (cohortFilter === "gender") {
      agents.forEach(agent => {
        if (!grouped[agent.gender]) grouped[agent.gender] = [];
        grouped[agent.gender].push(agent);
      });
    } else {
      // "all" - show all agents
      grouped["All Agents"] = agents;
    }

    return { agents, grouped };
  }, [cohortFilter]);

  // Filter data for insights/themes based on selected segment
  const filteredInsights = useMemo(() => {
    if (!selectedSegment) return insightCards;
    return insightCards.slice(0, 3); // Show top 3 when filtered
  }, [insightCards, selectedSegment]);

  return (
    <div className="flex flex-col gap-6 h-full p-6 overflow-y-auto scrollbar-thin">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-foreground">Analysis</h2>
          <p className="text-sm text-muted-foreground">
            Comprehensive report with executive summary, cohort explorer, and actionable insights.
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
            className="border-border text-foreground hover:bg-muted/50"
          >
            {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> Starting...</> : <><RefreshCw className="w-4 h-4" /> Rebuild Report</>}
          </Button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col gap-4">
        <TabsList className="w-fit bg-muted/40 border border-border">
          <TabsTrigger value="report">Reports &amp; Insights</TabsTrigger>
          <TabsTrigger value="opinions">Opinions Feed</TabsTrigger>
          <TabsTrigger value="friction">Friction Map</TabsTrigger>
        </TabsList>

        <TabsContent value="report" className="mt-0 flex-1">
          {!simulationComplete && (
            <GlassCard className="p-8 text-center">
              <div className="text-lg font-semibold text-foreground">Run Screen 3 first</div>
              <p className="text-sm text-muted-foreground mt-2">
                Complete the simulation to generate the comprehensive analysis report.
              </p>
            </GlassCard>
          )}

          {simulationComplete && (
            <div className="space-y-6">
              {/* Loading / Error States */}
              {(loading || reportState.status === "running") && (
                <GlassCard className="p-6 border border-primary/25">
                  <div className="flex items-center gap-3 text-primary">
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span className="font-semibold">Generating AI Report...</span>
                  </div>
                  <p className="text-sm text-muted-foreground mt-2">
                    Analyzing checkpoint shifts, influential posts, and demographic patterns.
                  </p>
                </GlassCard>
              )}

              {(reportError || reportState.error || reportState.status === "failed") && (
                <GlassCard className="p-5 border border-destructive/30">
                  <div className="flex items-center gap-3 text-destructive">
                    <AlertTriangle className="w-4 h-4" />
                    <span className="font-semibold">Report generation failed</span>
                  </div>
                  <p className="text-sm text-muted-foreground mt-2">{reportError ?? reportState.error ?? "Gemini did not return a valid structured report."}</p>
                </GlassCard>
              )}

              {hasCompletedReport && (
                <>
                  {/* 1. Executive Summary - Prominent */}
                  <GlassCard className="p-6 relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
                    <div className="relative">
                      <div className="flex items-center gap-3 mb-4">
                        <div className="w-10 h-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center">
                          <FileText className="w-5 h-5 text-primary" />
                        </div>
                        <div>
                          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Executive Summary</h3>
                          <p className="text-xs text-muted-foreground/60">Generated {formatTimestamp(reportState.generated_at)}</p>
                        </div>
                      </div>
                      <p className="text-lg leading-relaxed text-foreground max-w-4xl">
                        {reportState.executive_summary}
                      </p>
                      
                      {/* Quick Stats Row */}
                      <div className="flex items-center gap-6 mt-6 pt-6 border-t border-border/40">
                        <div className="flex items-center gap-2">
                          <div className="text-2xl font-mono font-bold text-emerald-400">97.6%</div>
                          <div className="text-xs text-muted-foreground">Initial Approval</div>
                        </div>
                        <div className="text-muted-foreground/30">→</div>
                        <div className="flex items-center gap-2">
                          <div className="text-2xl font-mono font-bold text-rose-400">0.0%</div>
                          <div className="text-xs text-muted-foreground">Final Approval</div>
                        </div>
                        <div className="flex items-center gap-2 ml-4">
                          <div className="text-2xl font-mono font-bold text-foreground">250</div>
                          <div className="text-xs text-muted-foreground">Agents Simulated</div>
                        </div>
                      </div>
                    </div>
                  </GlassCard>

                  {/* 2. Cohort Explorer */}
                  <GlassCard className="p-6">
                    <div className="flex items-center justify-between mb-6">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center">
                          <Users className="w-5 h-5 text-violet-400" />
                        </div>
                        <div>
                          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Cohort Explorer</h3>
                          <p className="text-xs text-muted-foreground/60">Visualize agent stances by demographic segment</p>
                        </div>
                      </div>
                      
                      {/* Filter Tabs */}
                      <div className="flex items-center gap-1 bg-muted/30 rounded-lg p-1 border border-border">
                        {[
                          { key: "all", label: "Overall" },
                          { key: "occupation", label: "Occupation" },
                          { key: "age", label: "Age" },
                          { key: "planning_area", label: "Area" },
                          { key: "gender", label: "Gender" },
                        ].map((filter) => (
                          <button
                            key={filter.key}
                            onClick={() => { setCohortFilter(filter.key as CohortFilter); setSelectedSegment(null); }}
                            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all
                              ${cohortFilter === filter.key 
                                ? 'bg-foreground/[0.08] text-foreground border border-border' 
                                : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                              }`}
                          >
                            {filter.label}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Agent Grid */}
                    <div className="space-y-6">
                      {Object.entries(cohortData.grouped).map(([segment, agents]) => {
                        const approveCount = agents.filter(a => a.stance === "approve").length;
                        const dissentCount = agents.filter(a => a.stance === "dissent").length;
                        const isSelected = selectedSegment === segment;
                        
                        return (
                          <div key={segment} className={`space-y-3 ${isSelected ? 'opacity-100' : selectedSegment ? 'opacity-40' : 'opacity-100'}`}>
                            <div 
                              className="flex items-center justify-between cursor-pointer group"
                              onClick={() => setSelectedSegment(isSelected ? null : segment)}
                            >
                              <div className="flex items-center gap-3">
                                <h4 className="text-sm font-semibold text-foreground group-hover:text-primary transition-colors">{segment}</h4>
                                <span className="text-xs text-muted-foreground font-mono">n={agents.length}</span>
                              </div>
                              <div className="flex items-center gap-3 text-xs">
                                <span className="flex items-center gap-1.5 text-emerald-400">
                                  <CheckCircle2 className="w-3.5 h-3.5" /> {approveCount}
                                </span>
                                <span className="flex items-center gap-1.5 text-rose-400">
                                  <AlertTriangle className="w-3.5 h-3.5" /> {dissentCount}
                                </span>
                              </div>
                            </div>
                            
                            <div className="flex flex-wrap gap-1.5">
                              {agents.slice(0, 100).map((agent) => (
                                <div
                                  key={agent.id}
                                  title={`${agent.name} - ${agent.occupation}, ${agent.age}`}
                                  className={`w-4 h-4 rounded-sm transition-all hover:scale-125 cursor-pointer ${
                                    agent.stance === "approve" 
                                      ? "bg-emerald-500/60 hover:bg-emerald-400" 
                                      : "bg-rose-500/60 hover:bg-rose-400"
                                  }`}
                                />
                              ))}
                              {agents.length > 100 && (
                                <span className="text-xs text-muted-foreground ml-2">+{agents.length - 100} more</span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    {/* Legend */}
                    <div className="flex items-center gap-6 mt-6 pt-6 border-t border-white/5">
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-sm bg-emerald-500/60" />
                        <span className="text-xs text-muted-foreground">Approve</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-sm bg-rose-500/60" />
                        <span className="text-xs text-muted-foreground">Dissent</span>
                      </div>
                      <div className="text-xs text-muted-foreground/50 ml-auto">
                        Click a segment to filter insights below
                      </div>
                    </div>
                  </GlassCard>

                  {/* 3. Key Insights & Views */}
                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                    <GlassCard className="p-6">
                      <div className="flex items-center gap-3 mb-4">
                        <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
                          <Lightbulb className="w-4 h-4 text-amber-400" />
                        </div>
                        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Key Insights</h3>
                      </div>
                      <div className="space-y-3">
                        {filteredInsights.length > 0 ? filteredInsights.map((card, index) => (
                          <div key={`${card.title ?? index}`} className="p-4 rounded-xl border border-white/10 bg-white/[0.02] hover:bg-white/[0.04] transition-colors">
                            <div className="flex items-start justify-between gap-3">
                              <div className="text-sm font-semibold text-foreground">{stringValue(card.title, `Insight ${index + 1}`)}</div>
                              <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${
                                card.severity === "high" ? "bg-rose-500/20 text-rose-400" :
                                card.severity === "medium" ? "bg-amber-500/20 text-amber-400" :
                                "bg-blue-500/20 text-blue-400"
                              }`}>
                                {stringValue(card.severity, "info")}
                              </span>
                            </div>
                            <p className="text-sm text-muted-foreground mt-2">{stringValue(card.summary, "")}</p>
                          </div>
                        )) : (
                          <p className="text-sm text-muted-foreground text-center py-8">No insights available for this segment</p>
                        )}
                      </div>
                    </GlassCard>

                    <div className="space-y-6">
                      <GlassCard className="p-6">
                        <div className="flex items-center gap-3 mb-4">
                          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
                            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                          </div>
                          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Supporting Views</h3>
                        </div>
                        <div className="space-y-2">
                          {supportThemes.slice(0, 3).map((item, index) => (
                            <div key={`${item.theme ?? index}`} className="p-3 rounded-lg border border-white/5 bg-white/[0.02]">
                              <div className="text-sm text-foreground">{stringValue(item.theme ?? item.title, `View ${index + 1}`)}</div>
                            </div>
                          ))}
                          {supportThemes.length === 0 && (
                            <p className="text-xs text-muted-foreground text-center py-4">No supporting views recorded</p>
                          )}
                        </div>
                      </GlassCard>

                      <GlassCard className="p-6">
                        <div className="flex items-center gap-3 mb-4">
                          <div className="w-8 h-8 rounded-lg bg-rose-500/10 border border-rose-500/20 flex items-center justify-center">
                            <AlertTriangle className="w-4 h-4 text-rose-400" />
                          </div>
                          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Dissenting Views</h3>
                        </div>
                        <div className="space-y-2">
                          {dissentThemes.slice(0, 3).map((item, index) => (
                            <div key={`${item.theme ?? index}`} className="p-3 rounded-lg border border-white/5 bg-white/[0.02]">
                              <div className="text-sm text-foreground">{stringValue(item.theme ?? item.title, `View ${index + 1}`)}</div>
                            </div>
                          ))}
                          {dissentThemes.length === 0 && (
                            <p className="text-xs text-muted-foreground text-center py-4">No dissenting views recorded</p>
                          )}
                        </div>
                      </GlassCard>
                    </div>
                  </div>

                  {/* 4. Recommendations */}
                  <GlassCard className="p-6">
                    <div className="flex items-center gap-3 mb-6">
                      <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
                        <Target className="w-5 h-5 text-blue-400" />
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Recommendations</h3>
                        <p className="text-xs text-muted-foreground/60">Strategic actions based on simulation analysis</p>
                      </div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {recommendations.length > 0 ? recommendations.map((item, index) => (
                        <div key={`${item.title ?? index}`} className="p-4 rounded-xl border border-white/10 bg-white/[0.02] hover:border-blue-500/30 transition-colors">
                          <div className="flex items-center justify-between gap-3 mb-2">
                            <div className="text-sm font-semibold text-foreground">{stringValue(item.title, `Recommendation ${index + 1}`)}</div>
                            {item.priority && (
                              <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${
                                item.priority === "high" ? "bg-rose-500/20 text-rose-400" :
                                item.priority === "medium" ? "bg-amber-500/20 text-amber-400" :
                                "bg-blue-500/20 text-blue-400"
                              }`}>
                                {stringValue(item.priority, "")}
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-muted-foreground">{stringValue(item.rationale ?? item.summary, "")}</p>
                        </div>
                      )) : (
                        <p className="text-sm text-muted-foreground col-span-2 text-center py-8">No recommendations generated</p>
                      )}
                    </div>
                  </GlassCard>

                  {/* 5. Risks */}
                  {risks.length > 0 && (
                    <GlassCard className="p-6 border-rose-500/20">
                      <div className="flex items-center gap-3 mb-6">
                        <div className="w-10 h-10 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center">
                          <ShieldAlert className="w-5 h-5 text-rose-400" />
                        </div>
                        <div>
                          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Risk Watchouts</h3>
                          <p className="text-xs text-muted-foreground/60">Potential concerns and minority viewpoints</p>
                        </div>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {risks.map((item, index) => (
                          <div key={`${item.title ?? index}`} className="p-4 rounded-xl border border-rose-500/10 bg-rose-500/[0.02]">
                            <div className="text-sm font-semibold text-foreground mb-2">{stringValue(item.title, `Risk ${index + 1}`)}</div>
                            <p className="text-sm text-muted-foreground">{stringValue(item.rationale ?? item.summary, "")}</p>
                          </div>
                        ))}
                      </div>
                    </GlassCard>
                  )}
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
