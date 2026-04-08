import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  FileText, Loader2, Download, Send, Search, X,
  MessageSquare, Users, User, TrendingUp, TrendingDown,
  AlertTriangle, ArrowRight, BadgeCheck, BriefcaseBusiness, MapPin, Wallet
} from 'lucide-react';
import { useApp } from '@/contexts/AppContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  StructuredReportState,
  exportReportDocx,
  generateReport,
  getStructuredReport,
  sendAgentChatMessage,
  sendGroupChatMessage,
  isLiveBootMode,
} from '@/lib/console-api';
import { agentResponses, Agent, type SimPost } from '@/data/mockData';
import { toast } from '@/hooks/use-toast';

const POLL_INTERVAL_MS = 1500;

type ViewMode = 'report' | 'split' | 'chat';
type ChatSegment = 'dissenters' | 'supporters' | 'one-on-one';

const EMPTY_REPORT: StructuredReportState = {
  session_id: '',
  status: 'idle',
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

/* ── Mock report data for demo mode ── */
const DEMO_REPORT: StructuredReportState = {
  session_id: 'demo',
  status: 'complete',
  generated_at: new Date().toISOString(),
  executive_summary:
    'The simulation reveals a deeply divided population regarding Budget 2026 policies. Initial approval of 65% eroded to 34% over 5 rounds of discourse, driven primarily by concerns about cost of living, AI-driven job displacement, and insufficient support for gig workers. The most influential agents were dissenters from lower-income brackets who reframed policy benefits as insufficient relative to rising costs.',
  insight_cards: [
    { title: 'Generational Divide', description: 'Under-35s are 29pp less likely to approve than over-55s. Housing and CPF concerns dominate.', icon: 'trend' },
    { title: 'Income Correlation', description: 'Below $4k income bracket shows 35% approval vs 64% for above $8k. Inequality is the key driver.', icon: 'chart' },
    { title: 'Cascade Effect', description: 'A single viral post about AI job displacement shifted 42 agents from supporter to dissenter.', icon: 'alert' },
  ],
  support_themes: [
    { theme: 'AI investment is forward-thinking and positions Singapore competitively', evidence_count: 23 },
    { theme: 'SkillsFuture enhancements address workforce readiness', evidence_count: 18 },
    { theme: 'Family support measures are practical and well-targeted', evidence_count: 15 },
  ],
  dissent_themes: [
    { theme: 'Cost of living not adequately addressed — wage growth lags inflation', evidence_count: 47 },
    { theme: 'AI benefits accrue to top earners while displacing middle-income jobs', evidence_count: 31 },
    { theme: 'Carbon tax increases will hit transport-dependent workers hardest', evidence_count: 22 },
  ],
  demographic_breakdown: [
    { group: '21–30', approval: 38, count: 62 },
    { group: '31–40', approval: 47, count: 58 },
    { group: '41–55', approval: 58, count: 72 },
    { group: '55+', approval: 67, count: 58 },
  ],
  influential_content: [
    { title: 'Innovation hubs only benefit top earners', author: 'Raj Kumar', engagement: 142, shift: -0.42 },
    { title: 'SkillsFuture is a band-aid on structural inequality', author: 'Siti Ibrahim', engagement: 98, shift: -0.28 },
  ],
  recommendations: [
    { title: 'Address cost-of-living gap', description: 'Introduce targeted wage supplements for income brackets below $4,000 to reduce the approval gap.' },
    { title: 'AI transition support', description: 'Create an AI Displacement Fund with retraining credits specifically for middle-income workers in at-risk sectors.' },
    { title: 'Carbon tax rebates', description: 'Expand U-Save rebates and introduce transport subsidies for workers in non-CBD areas.' },
  ],
  risks: [],
  error: null,
};

function hasRenderableReportContent(report: StructuredReportState): boolean {
  return Boolean(
    String(report.executive_summary ?? '').trim() ||
      (Array.isArray(report.metric_deltas) && report.metric_deltas.length > 0) ||
      (Array.isArray(report.sections) && report.sections.length > 0) ||
      (Array.isArray(report.insight_blocks) && report.insight_blocks.length > 0) ||
      (Array.isArray(report.preset_sections) && report.preset_sections.length > 0) ||
      (Array.isArray(report.insight_cards) && report.insight_cards.length > 0),
  );
}

export default function ReportChat() {
  const {
    sessionId,
    simulationComplete,
    agents,
    simPosts,
    chatHistory,
    addChatMessage,
    completeStep,
    setCurrentStep,
    country,
    useCase,
    simulationRounds,
  } = useApp();
  const liveMode = isLiveBootMode();

  const [viewMode, setViewMode] = useState<ViewMode>('split');
  const [reportState, setReportState] = useState<StructuredReportState>(EMPTY_REPORT);
  const [reportError, setReportError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const startedRef = useRef<string | null>(null);
  const hydratedReportSessionRef = useRef<string | null>(null);
  const hydrateRequestSeqRef = useRef(0);

  // Chat state
  const [chatSegment, setChatSegment] = useState<ChatSegment>('dissenters');
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [profileAgent, setProfileAgent] = useState<Agent | null>(null);
  const [search, setSearch] = useState('');
  const [message, setMessage] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);

  const topSupporters = useMemo(
    () => agents.filter((agent) => agent.sentiment === 'positive').slice(0, 5),
    [agents],
  );
  const topDissenters = useMemo(
    () => agents.filter((agent) => agent.sentiment === 'negative').slice(0, 5),
    [agents],
  );
  const agentsById = useMemo(() => new Map(agents.map((agent) => [agent.id, agent])), [agents]);

  const loadDemoReport = useCallback(async (): Promise<void> => {
    try {
      const response = await fetch('/demo-output.json');
      if (response.ok) {
        const data = await response.json();
        if (data?.report || data?.reportFull) {
          const reportFromDemo = data.reportFull || data.report;
          setReportState({ ...DEMO_REPORT, ...reportFromDemo, status: 'complete' });
          return;
        }
      }
    } catch {
      // Fall through to built-in demo report.
    }
    setReportState(DEMO_REPORT);
  }, []);

  // Load demo data if no backend
  useEffect(() => {
    if (isLiveBootMode()) {
      return;
    }
    if (reportState.status === 'idle' && !loading) {
      void loadDemoReport();
    }
  }, [loadDemoReport, reportState.status, loading]);

  const beginReportGeneration = useCallback(async () => {
    if (!sessionId) {
      setReportError('Complete a simulation before generating a report.');
      return;
    }
    startedRef.current = sessionId;
    setLoading(true);
    setReportError(null);
    try {
      const generated = await generateReport(sessionId);
      setReportState(generated);
    } catch (error) {
      startedRef.current = null;
      if (!isLiveBootMode()) {
        await loadDemoReport();
        setReportError(null);
        toast({
          title: 'Demo report loaded',
          description: error instanceof Error ? `${error.message}. Showing cached demo report.` : 'Backend unavailable. Showing cached demo report.',
        });
      } else {
        const message = error instanceof Error ? error.message : 'Report generation failed.';
        setReportState(EMPTY_REPORT);
        setReportError(message);
        toast({
          title: 'Report generation failed',
          description: message,
          variant: 'destructive',
        });
      }
    } finally {
      setLoading(false);
    }
  }, [loadDemoReport, sessionId]);

  useEffect(() => {
    if (!simulationComplete || !sessionId) return;
    if (hydratedReportSessionRef.current === sessionId) return;

    let cancelled = false;
    const requestSeq = ++hydrateRequestSeqRef.current;
    const hydrateReport = async () => {
      setLoading(true);
      setReportError(null);
      try {
        const report = await getStructuredReport(sessionId);
        if (cancelled || requestSeq !== hydrateRequestSeqRef.current) return;

        if (hasRenderableReportContent(report)) {
          setReportState(report);
          startedRef.current = sessionId;
          hydratedReportSessionRef.current = sessionId;
          return;
        }

        if (startedRef.current !== sessionId) {
          await beginReportGeneration();
        }
        hydratedReportSessionRef.current = sessionId;
      } catch {
        if (cancelled || requestSeq !== hydrateRequestSeqRef.current) return;
        hydratedReportSessionRef.current = null;
        await beginReportGeneration();
      } finally {
        if (!cancelled && requestSeq === hydrateRequestSeqRef.current) {
          setLoading(false);
        }
      }
    };

    void hydrateReport();

    return () => {
      cancelled = true;
      if (requestSeq === hydrateRequestSeqRef.current) {
        setLoading(false);
      }
    };
  }, [beginReportGeneration, sessionId, simulationComplete]);

  useEffect(() => {
    if (!sessionId || reportState.status !== 'running') return;
    const timer = window.setInterval(async () => {
      try {
        const next = await getStructuredReport(sessionId);
        setReportState(next);
      } catch { /* ignore */ }
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [sessionId, reportState.status]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView?.({ behavior: 'smooth' });
  }, [chatHistory, selectedAgent]);

  const enqueueDemoGroupReplies = useCallback((threadId: string, responders: Agent[]) => {
    responders.slice(0, 5).forEach((agent, index) => {
      window.setTimeout(() => {
        const responses = agentResponses[agent.sentiment] || agentResponses.neutral;
        const reply = responses[Math.floor(Math.random() * responses.length)];
        addChatMessage(threadId, 'agent', reply, agent.id);
      }, 420 + index * 220 + Math.random() * 300);
    });
  }, [addChatMessage]);

  const enqueueDemoOneToOneReply = useCallback((threadId: string, selected: Agent) => {
    window.setTimeout(() => {
      const responses = agentResponses[selected.sentiment] || agentResponses.neutral;
      const reply = responses[Math.floor(Math.random() * responses.length)];
      addChatMessage(threadId, 'agent', reply, selected.id);
    }, 520 + Math.random() * 500);
  }, [addChatMessage]);

  const sendMessage = useCallback(async () => {
    const trimmed = message.trim();
    if (!trimmed) return;

    if (chatSegment === 'one-on-one') {
      if (!selectedAgent) return;
      const threadId = selectedAgent.id;
      addChatMessage(threadId, 'user', trimmed, selectedAgent.id);
      setMessage('');
      if (!sessionId) {
        enqueueDemoOneToOneReply(threadId, selectedAgent);
        return;
      }
      try {
        const response = await sendAgentChatMessage(sessionId, {
          agent_id: selectedAgent.id,
          message: trimmed,
        });
        if (response.responses.length > 0) {
          response.responses.forEach((entry) => {
            addChatMessage(threadId, 'agent', entry.content, entry.agent_id ?? selectedAgent.id);
          });
          return;
        }
        if (liveMode) {
          toast({
            title: 'Live chat unavailable',
            description: 'The backend returned no agent response.',
            variant: 'destructive',
          });
          return;
        }
        enqueueDemoOneToOneReply(threadId, selectedAgent);
      } catch (error) {
        if (liveMode) {
          toast({
            title: 'Live chat unavailable',
            description: error instanceof Error ? error.message : 'The backend request failed.',
            variant: 'destructive',
          });
          return;
        }
        enqueueDemoOneToOneReply(threadId, selectedAgent);
      }
      return;
    }

    const threadId = `group-${chatSegment}`;
    const responders = chatSegment === 'supporters' ? topSupporters : topDissenters;
    if (!responders.length) {
      if (liveMode) {
        toast({
          title: 'Live chat unavailable',
          description: 'No live agents are available for this chat segment.',
          variant: 'destructive',
        });
      }
      return;
    }

    addChatMessage(threadId, 'user', trimmed);
    setMessage('');
    if (!sessionId) {
      enqueueDemoGroupReplies(threadId, responders);
      return;
    }
    try {
      const response = await sendGroupChatMessage(sessionId, {
        segment: chatSegment,
        message: trimmed,
      });
      if (response.responses.length > 0) {
        response.responses.forEach((entry, index) => {
          addChatMessage(
            threadId,
            'agent',
            entry.content,
            entry.agent_id ?? responders[index]?.id,
          );
        });
        return;
      }
      if (liveMode) {
        toast({
          title: 'Live chat unavailable',
          description: 'The backend returned no agent responses.',
          variant: 'destructive',
        });
        return;
      }
      enqueueDemoGroupReplies(threadId, responders);
    } catch (error) {
      if (liveMode) {
        toast({
          title: 'Live chat unavailable',
          description: error instanceof Error ? error.message : 'The backend request failed.',
          variant: 'destructive',
        });
        return;
      }
      enqueueDemoGroupReplies(threadId, responders);
    }
  }, [
    addChatMessage,
    chatSegment,
    enqueueDemoGroupReplies,
    enqueueDemoOneToOneReply,
    message,
    selectedAgent,
    sessionId,
    liveMode,
    topDissenters,
    topSupporters,
  ]);

  const handleExport = useCallback(async () => {
    if (!sessionId) {
      toast({ title: 'Export failed', description: 'No active session found.' });
      return;
    }
    try {
      const file = await exportReportDocx(sessionId);
      const url = URL.createObjectURL(file);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `mckainsey-report-${sessionId}.docx`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast({
        title: 'Export unavailable',
        description: error instanceof Error ? error.message : 'Unable to export DOCX right now.',
      });
    }
  }, [sessionId]);

  const handleProceed = useCallback(() => {
    completeStep(4);
    setCurrentStep(5);
  }, [completeStep, setCurrentStep]);

  const report = reportState;
  const filteredAgents = agents.filter(a => {
    const matchSearch = a.name.toLowerCase().includes(search.toLowerCase()) ||
      a.occupation.toLowerCase().includes(search.toLowerCase());
    return matchSearch;
  }).slice(0, 30);

  const activeThreadId = chatSegment === 'one-on-one'
    ? selectedAgent?.id ?? null
    : `group-${chatSegment}`;
  const history = activeThreadId ? (chatHistory[activeThreadId] || []) : [];
  const hasReportContent = hasRenderableReportContent(reportState);

  const showReport = viewMode === 'report' || viewMode === 'split';
  const showChat = viewMode === 'chat' || viewMode === 'split';

  const activeProfilePosts = useMemo(() => {
    if (!profileAgent) return [];
    return simPosts
      .filter((post) => post.agentId === profileAgent.id)
      .sort((left, right) => (right.upvotes + right.commentCount) - (left.upvotes + left.commentCount))
      .slice(0, 3);
  }, [profileAgent, simPosts]);

  const openOneToOneChat = useCallback((agent: Agent) => {
    setSelectedAgent(agent);
    setChatSegment('one-on-one');
    setViewMode('split');
    setProfileAgent(null);
  }, []);

  const openEvidenceDrilldown = useCallback((agentId: string) => {
    const agent = agentsById.get(agentId);
    if (!agent) {
      return;
    }
    openOneToOneChat(agent);
    setProfileAgent(agent);
  }, [agentsById, openOneToOneChat]);

  const reportQuickStats = (report.quick_stats ?? {}) as Record<string, unknown>;
  const reportAgentCount = String(reportQuickStats.agent_count ?? reportQuickStats.agents_simulated ?? reportQuickStats.population_size ?? (agents.length > 0 ? agents.length : '—'));
  const reportRoundCount = String(reportQuickStats.round_count ?? simulationRounds);

  return (
    <div className="relative flex h-full flex-col overflow-hidden bg-background">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-border flex-shrink-0">
        <div>
          <h2 className="text-lg font-semibold text-foreground tracking-tight">Analysis Report</h2>
          <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
            {formatCountry(country)} · {formatUseCase(useCase)} · {reportAgentCount} agents · {reportRoundCount} rounds
          </p>
        </div>
        <div className="flex items-center gap-3">
          <SegmentedControl
            value={viewMode}
            options={[
              { value: 'report', label: 'Report' },
              { value: 'split', label: 'Report + Chat' },
              { value: 'chat', label: 'Chat' },
            ]}
            onChange={(v) => setViewMode(v as ViewMode)}
          />
          <Button onClick={handleExport} variant="outline" size="sm" className="border-border text-foreground gap-1.5 h-8">
            <Download className="w-3.5 h-3.5" /> Export
          </Button>
          <Button onClick={handleProceed} size="sm" className="bg-success/20 text-success hover:bg-success/30 border border-success/30 h-8 px-4 font-mono uppercase tracking-wider">
            Proceed <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* ── Report Panel ── */}
        {showReport && (
          <div className={`overflow-y-auto scrollbar-thin p-6 space-y-6 ${showChat ? 'w-[60%] border-r border-border' : 'w-full max-w-4xl mx-auto'}`}>
            {loading && !hasReportContent ? (
              <div className="flex flex-col items-center justify-center h-64 gap-3">
                <Loader2 className="w-6 h-6 animate-spin text-white/40" />
                <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">Generating report...</span>
              </div>
            ) : reportError ? (
              <div className="text-center py-16">
                <AlertTriangle className="w-8 h-8 text-destructive mx-auto mb-3" />
                <p className="text-sm text-destructive">{reportError}</p>
                <Button onClick={beginReportGeneration} variant="outline" className="mt-4 border-border text-foreground">
                  Retry
                </Button>
              </div>
            ) : (
              <>
                {/* Executive Summary */}
                <section className="surface-card p-5">
                  <div className="flex items-center gap-2 mb-3">
                    <FileText className="w-4 h-4 text-muted-foreground" />
                    <span className="label-meta">Executive Summary</span>
                  </div>
                  <p className="text-sm text-foreground/80 leading-relaxed">
                    {report.executive_summary || 'No summary available.'}
                  </p>
                  {/* Quick stats from new structure */}
                  <div className="mt-4 pt-4 border-t border-border flex items-center gap-6 flex-wrap">
                    <QuickStat label="Agents Simulated" value={reportAgentCount} />
                    <QuickStat label="Rounds" value={reportRoundCount} />
                  </div>
                </section>

                {/* Metric Deltas (from analysis_questions) */}
                {(report as any).metric_deltas && (report as any).metric_deltas.length > 0 && (
                  <section>
                    <span className="label-meta block mb-3">Key Metrics</span>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                      {((report as any).metric_deltas as any[]).map((delta: any, i: number) => (
                        <div key={i} className="surface-card p-4">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                              {formatPlainText(delta.metric_label || delta.metric_name)}
                            </span>
                            <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                              delta.direction === 'up' ? 'bg-emerald-500/10 text-emerald-400' :
                              delta.direction === 'down' ? 'bg-red-500/10 text-red-400' :
                              'bg-white/5 text-muted-foreground'
                            }`}>
                              {delta.direction === 'up' ? '▲' : delta.direction === 'down' ? '▼' : '—'} {formatMetricDelta(delta.delta, delta.metric_unit, delta.type)}
                            </span>
                          </div>
                          <div className="flex items-baseline gap-2 text-sm">
                            <span className="font-mono font-medium text-foreground">
                              {formatMetricValue(delta.initial_value, delta.metric_unit, delta.type)}
                              {' -> '}
                              {formatMetricValue(delta.final_value, delta.metric_unit, delta.type)}
                            </span>
                          </div>
                          {delta.report_title && (
                            <p className="text-[10px] text-muted-foreground mt-1">{formatPlainText(delta.report_title)}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                {/* Analysis Question Sections */}
                {(report as any).sections && (report as any).sections.length > 0 && (
                  <section className="space-y-4">
                    <span className="label-meta block">Analysis Findings</span>
                    {((report as any).sections as any[]).map((section: any, i: number) => (
                      <div key={i} className="surface-card p-5">
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-mono uppercase tracking-wider ${
                            section.type === 'scale' ? 'bg-blue-500/10 text-blue-400' :
                            section.type === 'yes-no' ? 'bg-emerald-500/10 text-emerald-400' :
                            'bg-white/5 text-muted-foreground'
                          }`}>
                            {formatPlainText(section.type || 'open-ended')}
                          </span>
                          <span className="text-sm font-medium text-foreground">{formatPlainText(section.report_title || section.question)}</span>
                        </div>
                        {section.metric && (
                          <div className="flex items-center gap-3 mb-3 px-3 py-2 rounded bg-white/[0.03] border border-white/5">
                            <span className="text-lg font-mono font-medium text-foreground">
                              {formatMetricValue(section.metric.initial_value, section.metric.metric_unit, section.type)}
                              {' -> '}
                              {formatMetricValue(section.metric.final_value, section.metric.metric_unit, section.type)}
                            </span>
                            <span className={`text-sm font-mono ${
                              section.metric.direction === 'up' ? 'text-emerald-400' :
                              section.metric.direction === 'down' ? 'text-red-400' :
                              'text-muted-foreground'
                            }`}>
                              {formatMetricDelta(section.metric.delta, section.metric.metric_unit, section.type)}
                            </span>
                          </div>
                        )}
                        <p className="text-xs text-foreground/80 leading-relaxed">{formatPlainText(section.answer)}</p>
                        {Array.isArray(section.evidence) && section.evidence.length > 0 && (
                          <div className="mt-4 space-y-2 border-t border-border pt-3">
                            <div className="label-meta">Evidence</div>
                            {section.evidence.slice(0, 4).map((item: any, evidenceIndex: number) => (
                              <div key={`${item.agent_id || 'evidence'}-${evidenceIndex}`} className="rounded border border-white/10 bg-white/[0.02] p-3">
                                <div className="mb-1 flex flex-wrap items-center gap-2 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                                  {item.agent_id ? (
                                    <button
                                      type="button"
                                      onClick={() => openEvidenceDrilldown(String(item.agent_id))}
                                      className="text-foreground underline-offset-2 hover:underline"
                                    >
                                      {resolveAgentDisplayName(String(item.agent_id), agentsById) ?? String(item.agent_id)}
                                    </button>
                                  ) : (
                                    <span>Unknown agent</span>
                                  )}
                                  {item.post_id && <span>· {String(item.post_id)}</span>}
                                </div>
                                <p className="text-xs leading-relaxed text-foreground/80">{String(item.quote || item.content || '')}</p>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </section>
                )}

                {/* Insight Blocks */}
                {(report as any).insight_blocks && (report as any).insight_blocks.length > 0 && (
                  <section className="space-y-4">
                    <span className="label-meta block">Insight Blocks</span>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {((report as any).insight_blocks as any[]).map((block: any, i: number) => (
                        <div key={i} className="surface-card p-5">
                          <div className="flex items-center gap-2 mb-3">
                            <BadgeCheck className="w-4 h-4 text-muted-foreground" />
                            <span className="text-sm font-medium text-foreground">{block.title}</span>
                          </div>
                          {block.description && (
                            <p className="text-xs text-muted-foreground mb-3">{block.description}</p>
                          )}
                          {block.data && block.data.status !== 'not_applicable' ? (
                            <InsightBlockData data={block.data} type={block.type} />
                          ) : (
                            <p className="text-xs text-muted-foreground/50 italic">Not applicable for this use case.</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                {/* Preset Sections */}
                {(report as any).preset_sections && (report as any).preset_sections.length > 0 && (
                  <section className="space-y-4">
                    {((report as any).preset_sections as any[]).map((preset: any, i: number) => (
                      <div key={i} className="surface-card p-5">
                        <span className="label-meta block mb-3">{formatPlainText(preset.title)}</span>
                        <p className="text-sm text-foreground/80 leading-relaxed">{formatPlainText(preset.answer)}</p>
                      </div>
                    ))}
                  </section>
                )}

                {/* Legacy fallback: Insight Cards */}
                {report.insight_cards && report.insight_cards.length > 0 && !(report as any).metric_deltas && (
                  <section>
                    <span className="label-meta block mb-3">Key Insights</span>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      {report.insight_cards.map((card: any, i: number) => (
                        <div key={i} className="surface-card p-4">
                          <div className="text-sm font-medium text-foreground mb-1">{card.title || card.headline}</div>
                          <p className="text-xs text-muted-foreground leading-relaxed">{card.description}</p>
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                {/* Legacy fallback: Supporting vs Dissenting */}
                {!(report as any).sections && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <ThemeCard
                      title="Supporting Views"
                      color="hsl(var(--data-green))"
                      themes={report.support_themes}
                    />
                    <ThemeCard
                      title="Dissenting Views"
                      color="hsl(var(--data-red))"
                      themes={report.dissent_themes}
                    />
                  </div>
                )}

                {/* Legacy fallback: Recommendations */}
                {report.recommendations && report.recommendations.length > 0 && !(report as any).preset_sections && (
                  <section className="surface-card p-5">
                    <span className="label-meta block mb-4">Recommendations</span>
                    <div className="space-y-4">
                      {report.recommendations.map((rec: any, i: number) => (
                        <div key={i} className="flex gap-3">
                          <div className="w-5 h-5 rounded flex items-center justify-center bg-white/5 text-[9px] font-mono text-muted-foreground flex-shrink-0 mt-0.5">
                            {i + 1}
                          </div>
                          <div>
                            <div className="text-sm font-medium text-foreground">{rec.title}</div>
                            <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{rec.description}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </section>
                )}
              </>
            )}
          </div>
        )}

        {/* ── Chat Panel ── */}
        {showChat && (
          <div className={`flex flex-col ${showReport ? 'w-[40%]' : 'w-full'}`}>
            {/* Chat Header */}
            <div className="px-4 py-3 border-b border-border flex items-center justify-between flex-shrink-0">
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm font-medium text-foreground">Agent Chat</span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[hsl(210,100%,56%)]/15 text-[hsl(210,100%,56%)] uppercase tracking-wider">
                  {chatSegment === 'one-on-one' ? '1:1' : 'Group'}
                </span>
              </div>
              {viewMode === 'split' && (
                <button
                  onClick={() => setViewMode('report')}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            {/* Segment Tabs */}
            <div className="px-4 py-2.5 border-b border-border flex gap-1.5 flex-shrink-0">
              {(['dissenters', 'supporters', 'one-on-one'] as ChatSegment[]).map(seg => (
                <button
                  key={seg}
                  onClick={() => setChatSegment(seg)}
                  className={`px-3 py-1.5 rounded text-[10px] font-mono uppercase tracking-wider transition-colors ${
                    chatSegment === seg
                      ? 'bg-white/10 text-foreground'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {seg === 'one-on-one' ? '1:1 Chat' : `Top ${seg}`}
                </button>
              ))}
            </div>

            {/* Agent selector for 1:1 */}
            {chatSegment === 'one-on-one' && (
              <div className="px-4 py-2.5 border-b border-border flex-shrink-0">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                  <Input
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    placeholder="Search agents..."
                    className="pl-9 h-8 text-sm bg-card border-border"
                  />
                </div>
                {search && filteredAgents.length > 0 && (
                  <div className="mt-1.5 max-h-36 overflow-y-auto space-y-0.5 scrollbar-thin">
                    {filteredAgents.map(agent => (
                      <button
                        key={agent.id}
                        onClick={() => { setSelectedAgent(agent); setSearch(''); }}
                        onDoubleClick={() => setProfileAgent(agent)}
                        className={`w-full text-left px-3 py-2 rounded text-xs transition-colors ${
                          selectedAgent?.id === agent.id
                            ? 'bg-white/10 text-foreground'
                            : 'text-muted-foreground hover:bg-white/5 hover:text-foreground'
                        }`}
                      >
                        <span className="font-medium">{agent.name}</span>
                        <span className="text-muted-foreground ml-1.5">{agent.occupation}</span>
                      </button>
                    ))}
                  </div>
                )}
                {selectedAgent && (
                  <div className="mt-2 flex items-center gap-2 px-3 py-2 rounded bg-card border border-border">
                    <div className="w-6 h-6 rounded-full bg-white/10 flex items-center justify-center text-[9px] font-mono text-foreground">
                      {selectedAgent.name.split(' ').map(n => n[0]).join('').slice(0, 2)}
                    </div>
                    <button
                      type="button"
                      onClick={() => setProfileAgent(selectedAgent)}
                      className="text-xs text-foreground hover:text-white underline-offset-2 hover:underline"
                    >
                      {selectedAgent.name}
                    </button>
                    <StanceDot sentiment={selectedAgent.sentiment} />
                    <button
                      onClick={() => setSelectedAgent(null)}
                      className="ml-auto text-muted-foreground hover:text-foreground"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3 scrollbar-thin">
              {chatSegment !== 'one-on-one' ? (
                /* Group chat: show a welcome prompt */
                history.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-3">
                    <Users className="w-8 h-8 opacity-30" />
                    <p className="text-sm">Ask a question to the {chatSegment}</p>
                    <p className="text-[10px] font-mono uppercase tracking-wider opacity-50">
                      Top 5 most influential agents will respond
                    </p>
                  </div>
                ) : (
                  history.map((msg, i) => {
                    const sourceAgent = msg.agentId ? agentsById.get(msg.agentId) : null;
                    return (
                      <ChatBubble
                        key={i}
                        msg={msg}
                        isUser={msg.role === 'user'}
                        agent={sourceAgent}
                        onAgentClick={setProfileAgent}
                      />
                    );
                  })
                )
              ) : selectedAgent ? (
                history.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-3">
                    <User className="w-8 h-8 opacity-30" />
                    <p className="text-sm">Chat with {selectedAgent.name.split(' ')[0]}</p>
                  </div>
                ) : (
                  history.map((msg, i) => (
                    <ChatBubble
                      key={i}
                      msg={msg}
                      isUser={msg.role === 'user'}
                      agent={selectedAgent}
                      onAgentClick={setProfileAgent}
                    />
                  ))
                )
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-3">
                  <Search className="w-8 h-8 opacity-30" />
                  <p className="text-sm">Select an agent above</p>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t border-border flex gap-2 flex-shrink-0">
              <Input
                value={message}
                onChange={e => setMessage(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') {
                    void sendMessage();
                  }
                }}
                placeholder={
                  chatSegment === 'one-on-one' && selectedAgent
                    ? `Ask ${selectedAgent.name.split(' ')[0]}...`
                    : 'Ask the group a question...'
                }
                className="bg-card border-border text-sm h-10"
              />
              <Button
                onClick={() => void sendMessage()}
                size="icon"
                className="h-10 w-10 shrink-0 bg-[hsl(210,100%,56%)] hover:bg-[hsl(210,100%,50%)] text-white border-0"
              >
                <Send className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}

        {profileAgent && (
          <AgentProfileDrawer
            agent={profileAgent}
            posts={activeProfilePosts}
            onClose={() => setProfileAgent(null)}
            onOpenOneToOne={() => openOneToOneChat(profileAgent)}
          />
        )}
      </div>
    </div>
  );
}

/* ── Sub-components ── */

function SegmentedControl({ value, options, onChange }: {
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <div className="inline-flex items-center gap-0.5 rounded border border-border bg-card p-0.5">
      {options.map(opt => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`rounded px-3 py-1 text-[10px] font-mono uppercase tracking-wider transition-colors ${
            opt.value === value
              ? 'bg-white/10 text-foreground'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

function QuickStat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <div className="text-lg font-mono font-medium" style={color ? { color } : { color: 'hsl(var(--foreground))' }}>
        {value}
      </div>
      <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-[0.16em]">{label}</div>
    </div>
  );
}

function ThemeCard({ title, color, themes }: { title: string; color: string; themes: any[] }) {
  if (!themes || themes.length === 0) return null;
  return (
    <div className="surface-card p-5">
      <div className="flex items-center gap-2 mb-3">
        {color.includes('green') ? (
          <TrendingUp className="w-3.5 h-3.5" style={{ color }} />
        ) : (
          <TrendingDown className="w-3.5 h-3.5" style={{ color }} />
        )}
        <span className="label-meta" style={{ color }}>{title}</span>
      </div>
      <ul className="space-y-2">
        {themes.map((t: any, i: number) => (
          <li key={i} className="text-xs text-foreground/80 leading-relaxed flex gap-2">
            <span className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0" style={{ backgroundColor: color }} />
            <span>
              {t.theme || t}
              {t.evidence_count && (
                <span className="text-muted-foreground ml-1">({t.evidence_count} citations)</span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function InsightBlockData({ data, type }: { data: any; type: string }) {
  if (!data) return null;

  // If data is an array (e.g. pain_points, top_advocates, viral_posts)
  if (Array.isArray(data)) {
    return (
      <ul className="space-y-1.5">
        {data.slice(0, 8).map((item: any, i: number) => (
          <li key={i} className="text-xs text-foreground/80 leading-relaxed flex gap-2">
            <span className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 bg-white/20" />
            <span>{typeof item === 'string' ? item : JSON.stringify(item)}</span>
          </li>
        ))}
      </ul>
    );
  }

  // If data has items/entries array
  const entries = data.items || data.entries || data.segments || data.rows;
  if (Array.isArray(entries)) {
    return (
      <div className="space-y-2">
        {entries.slice(0, 8).map((entry: any, i: number) => (
          <div key={i} className="flex items-center justify-between text-xs">
            <span className="text-foreground/80 truncate mr-2">
              {entry.label || entry.name || entry.segment || `Item ${i + 1}`}
            </span>
            <span className="font-mono text-muted-foreground flex-shrink-0">
              {entry.value ?? entry.count ?? entry.score ?? ''}
            </span>
          </div>
        ))}
      </div>
    );
  }

  // If data is an object with key-value pairs
  if (typeof data === 'object' && data !== null) {
    const displayKeys = Object.keys(data).filter(k => k !== 'status');
    if (displayKeys.length === 0) return null;
    return (
      <div className="space-y-1.5">
        {displayKeys.slice(0, 8).map((key) => (
          <div key={key} className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">{key.replace(/_/g, ' ')}</span>
            <span className="font-mono text-foreground/80">
              {typeof data[key] === 'object' ? JSON.stringify(data[key]).slice(0, 40) : String(data[key])}
            </span>
          </div>
        ))}
      </div>
    );
  }

  return <p className="text-xs text-muted-foreground">{String(data)}</p>;
}

function ChatBubble({
  msg,
  isUser,
  agent,
  onAgentClick,
}: {
  msg: { role: string; content: string };
  isUser: boolean;
  agent?: Agent | null;
  onAgentClick?: (agent: Agent) => void;
}) {
  const agentLabel = agent ? `${agent.name} · ${sentimentLabel(agent.sentiment)}` : 'Agent';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[80%] rounded-xl px-4 py-2.5 text-sm ${
        isUser
          ? 'bg-[hsl(210,100%,56%)]/15 text-foreground border border-[hsl(210,100%,56%)]/25 rounded-br-sm'
          : 'bg-card border border-border text-foreground/80 rounded-bl-sm'
      }`}>
        {!isUser && (
          <div className="mb-1.5">
            {agent ? (
              <button
                type="button"
                onClick={() => onAgentClick?.(agent)}
                className="inline-flex items-center gap-2 text-[10px] font-mono uppercase tracking-wider text-muted-foreground hover:text-foreground"
              >
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-white/10 text-[9px] text-foreground">
                  {agent.name.split(' ').map((name) => name[0]).join('').slice(0, 2)}
                </span>
                <span>{agentLabel}</span>
              </button>
            ) : (
              <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Agent</span>
            )}
          </div>
        )}
        {msg.content}
      </div>
    </div>
  );
}

function StanceDot({ sentiment }: { sentiment: string }) {
  const color = sentiment === 'positive'
    ? 'bg-[hsl(var(--data-green))]'
    : sentiment === 'negative'
    ? 'bg-[hsl(var(--data-red))]'
    : 'bg-white/30';
  return <span className={`w-2 h-2 rounded-full ${color}`} />;
}

function AgentProfileDrawer({
  agent,
  posts,
  onClose,
  onOpenOneToOne,
}: {
  agent: Agent;
  posts: SimPost[];
  onClose: () => void;
  onOpenOneToOne: () => void;
}) {
  const score = Math.max(1, Math.min(10, Math.round(agent.approvalScore / 10)));
  const scoreColor = agent.sentiment === 'positive'
    ? 'hsl(var(--data-green))'
    : agent.sentiment === 'negative'
    ? 'hsl(var(--data-red))'
    : 'hsl(var(--muted-foreground))';

  return (
    <aside className="absolute inset-y-0 right-0 z-30 w-[340px] border-l border-white/10 bg-[#0B0B0B]/95 backdrop-blur-sm">
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="text-[10px] font-mono uppercase tracking-[0.16em] text-muted-foreground">Agent Profile</div>
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-4 scrollbar-thin">
          <div className="surface-card p-4">
            <div className="mb-3 flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white/10 font-mono text-sm text-foreground">
                {agent.name.split(' ').map((name) => name[0]).join('').slice(0, 2)}
              </div>
              <div>
                <div className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
                  {agent.name}
                  <BadgeCheck className="h-3.5 w-3.5 text-[hsl(var(--data-blue))]" />
                </div>
                <div className="text-[11px] text-muted-foreground">{sentimentLabel(agent.sentiment)}</div>
              </div>
            </div>

            <div className="space-y-2 text-xs text-muted-foreground">
              <div className="flex items-center gap-2"><BriefcaseBusiness className="h-3.5 w-3.5" /> {agent.occupation}</div>
              <div className="flex items-center gap-2"><MapPin className="h-3.5 w-3.5" /> {agent.planningArea}</div>
              <div className="flex items-center gap-2"><Wallet className="h-3.5 w-3.5" /> {agent.incomeBracket}</div>
              <div className="text-muted-foreground/90">Age {agent.age} · {agent.gender} · {agent.ethnicity}</div>
            </div>
          </div>

          <div className="surface-card p-4">
            <div className="label-meta mb-2">Core Viewpoint</div>
            <p className="text-xs leading-relaxed text-foreground/80">{buildCoreViewpoint(agent)}</p>

            <div className="mt-3 border-t border-border pt-3">
              <div className="mb-2 flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                <span>Stance Score</span>
                <span style={{ color: scoreColor }}>{score}/10</span>
              </div>
              <div className="h-2 rounded-full bg-white/10">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${score * 10}%`, backgroundColor: scoreColor }}
                />
              </div>
            </div>
          </div>

          <div className="surface-card p-4">
            <div className="label-meta mb-3">Key Posts</div>
            <div className="space-y-3">
              {posts.length > 0 ? posts.map((post) => (
                <div key={post.id} className="rounded border border-white/10 bg-black/20 p-2.5">
                  <div className="text-xs font-medium text-foreground">{post.title}</div>
                  <div className="mt-1 text-[10px] text-muted-foreground">▲ {post.upvotes} · ▼ {post.downvotes} · 💬 {post.commentCount}</div>
                </div>
              )) : (
                <div className="text-xs text-muted-foreground">No tracked posts yet for this agent.</div>
              )}
            </div>
          </div>
        </div>

        <div className="border-t border-border p-4">
          <Button onClick={onOpenOneToOne} className="h-10 w-full bg-primary text-primary-foreground">
            Chat 1:1
          </Button>
        </div>
      </div>
    </aside>
  );
}

function sentimentLabel(sentiment: Agent['sentiment']): string {
  if (sentiment === 'positive') return 'Supporter';
  if (sentiment === 'negative') return 'Dissenter';
  return 'Neutral';
}

function buildCoreViewpoint(agent: Agent): string {
  if (agent.sentiment === 'positive') {
    return `${agent.name.split(' ')[0]} generally supports the policy direction, while asking for implementation details that protect everyday households in ${agent.planningArea}.`;
  }
  if (agent.sentiment === 'negative') {
    return `${agent.name.split(' ')[0]} believes the current approach puts disproportionate pressure on working residents and wants stronger cost-of-living safeguards for ${agent.occupation.toLowerCase()} households.`;
  }
  return `${agent.name.split(' ')[0]} sees tradeoffs on both sides and asks for clearer data transparency before committing to a stronger stance.`;
}

function formatCountry(country: string): string {
  const normalized = String(country || '').trim().toLowerCase();
  if (normalized === 'usa') return 'USA';
  return normalized ? normalized[0].toUpperCase() + normalized.slice(1) : 'Singapore';
}

function formatUseCase(useCase: string): string {
  const normalized = String(useCase || '').trim().toLowerCase();
  if (normalized === 'public-policy-testing') return 'Public Policy Testing';
  if (normalized === 'product-market-research') return 'Product & Market Research';
  if (normalized === 'campaign-content-testing') return 'Campaign & Content Testing';
  // V1 backward compat
  if (normalized === 'policy-review') return 'Public Policy Testing';
  if (normalized === 'ad-testing') return 'Campaign & Content Testing';
  if (normalized === 'pmf-discovery' || normalized === 'reviews') return 'Product & Market Research';
  return 'Public Policy Testing';
}

function resolveAgentDisplayName(agentId: string, agentsById: Map<string, Agent>): string | null {
  const match = agentsById.get(agentId);
  if (match?.name) {
    return match.name;
  }
  return null;
}

function formatMetricValue(value: unknown, unit: unknown, type?: unknown): string {
  const numeric = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(numeric)) {
    return '—';
  }

  const normalizedUnit = String(unit ?? '').trim().toLowerCase();
  const normalizedType = String(type ?? '').trim().toLowerCase();
  if (normalizedType === 'yes-no' || normalizedUnit === '%') {
    return `${Math.round(numeric)}%`;
  }
  if (normalizedUnit === '/10' || normalizedType === 'scale') {
    return `${numeric.toFixed(1)}/10`;
  }
  if (normalizedUnit === 'count') {
    return `${Math.round(numeric)}`;
  }
  return Number.isInteger(numeric) ? `${numeric}` : numeric.toFixed(1);
}

function formatMetricDelta(value: unknown, unit: unknown, type?: unknown): string {
  const numeric = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(numeric)) {
    return '—';
  }
  const display = formatMetricValue(Math.abs(numeric), unit, type);
  return `${numeric >= 0 ? '+' : '−'} ${display}`;
}

function formatPlainText(value: unknown): string {
  const text = String(value ?? '');
  return text
    .replace(/^\s{0,3}#{1,6}\s+/gm, '')
    .replace(/^\s{0,3}[-*+]\s+/gm, '')
    .replace(/^\s{0,3}\d+\.\s+/gm, '')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/__(.*?)__/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\[(.*?)\]\((.*?)\)/g, '$1')
    .replace(/\s+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}
