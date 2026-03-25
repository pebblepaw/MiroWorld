import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowRight, Loader2, MessageSquare, Play, ThumbsDown, ThumbsUp, TimerReset, Waves, Clock } from "lucide-react";

import { GlassCard } from "@/components/GlassCard";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Slider } from "@/components/ui/slider";
import { useApp } from "@/contexts/AppContext";
import { buildSimulationStreamUrl, SimulationState, startSimulation } from "@/lib/console-api";

type FeedComment = {
  id: string;
  actorName: string;
  content: string;
};

type FeedThread = {
  id: string;
  postId: string | number;
  actorName: string;
  actorSubtitle: string;
  actorOccupation?: string;
  actorAge?: number;
  title: string;
  content: string;
  roundNo: number;
  likes: number;
  dislikes: number;
  comments: FeedComment[];
};

// Occupation color mapping for visual variety
const OCCUPATION_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  "Teacher": { bg: "bg-emerald-500/15", text: "text-emerald-400", border: "border-emerald-500/30" },
  "Professional": { bg: "bg-blue-500/15", text: "text-blue-400", border: "border-blue-500/30" },
  "Manager": { bg: "bg-violet-500/15", text: "text-violet-400", border: "border-violet-500/30" },
  "Engineer": { bg: "bg-cyan-500/15", text: "text-cyan-400", border: "border-cyan-500/30" },
  "Nurse": { bg: "bg-rose-500/15", text: "text-rose-400", border: "border-rose-500/30" },
  "Clerical": { bg: "bg-amber-500/15", text: "text-amber-400", border: "border-amber-500/30" },
  "Sales": { bg: "bg-orange-500/15", text: "text-orange-400", border: "border-orange-500/30" },
  "Service": { bg: "bg-pink-500/15", text: "text-pink-400", border: "border-pink-500/30" },
  "Retired": { bg: "bg-slate-500/15", text: "text-slate-400", border: "border-slate-500/30" },
  "Student": { bg: "bg-indigo-500/15", text: "text-indigo-400", border: "border-indigo-500/30" },
  "default": { bg: "bg-primary/15", text: "text-primary", border: "border-primary/30" },
};

function getOccupationColor(occupation?: string): { bg: string; text: string; border: string } {
  if (!occupation) return OCCUPATION_COLORS["default"];
  const key = Object.keys(OCCUPATION_COLORS).find(k => 
    occupation.toLowerCase().includes(k.toLowerCase())
  );
  return OCCUPATION_COLORS[key || "default"];
}

export default function Simulation() {
  const {
    sessionId,
    knowledgeArtifact,
    populationArtifact,
    simulationRounds,
    setSimulationRounds,
    setSimulationComplete,
    completeStep,
    setCurrentStep,
  } = useApp();

  const [simulationState, setSimulationState] = useState<SimulationState | null>(null);
  const [feedThreads, setFeedThreads] = useState<FeedThread[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const streamRef = useRef<EventSource | null>(null);
  const feedRef = useRef<HTMLDivElement>(null);

  const counters = simulationState?.counters ?? { posts: 0, comments: 0, reactions: 0, active_authors: 0 };
  const running = simulationState?.status === "running";
  const completed = simulationState?.status === "completed";
  const baselineStatus = simulationState?.checkpoint_status?.baseline?.status ?? "pending";
  const finalStatus = simulationState?.checkpoint_status?.final?.status ?? "pending";

  const estimatedTime = useMemo(() => estimateRuntimeSeconds(populationArtifact?.sample_count ?? 0, simulationRounds), [populationArtifact?.sample_count, simulationRounds]);
  const hottestThread = simulationState?.top_threads?.[0] as { title?: string; engagement?: number } | undefined;

  const closeStream = useCallback(() => {
    streamRef.current?.close();
    streamRef.current = null;
  }, []);

  useEffect(() => () => closeStream(), [closeStream]);

  useEffect(() => {
    if (!feedRef.current) return;
    feedRef.current.scrollTop = feedRef.current.scrollHeight;
  }, [feedThreads.length]);

  const handleSimulationEvent = useCallback((payload: Record<string, unknown>) => {
    const eventType = String(payload.event_type ?? "");
    setSimulationState((previous) => reduceSimulationState(previous, payload));

    if (eventType === "post_created") {
      setFeedThreads((previous) => {
        const rawPostId = payload.post_id;
        const postId =
          typeof rawPostId === "number" || typeof rawPostId === "string"
            ? rawPostId
            : previous.length + 1;
        const content = String(payload.content ?? "").trim();
        const title = String(payload.title ?? (content.slice(0, 72) || "New discussion thread"));
        const actorName = String(payload.actor_name ?? payload.actor_agent_id ?? "Agent");
        const actorOccupation = String(payload.actor_occupation ?? "");
        const actorAge = payload.actor_age ? Number(payload.actor_age) : undefined;
        const actorSubtitle = actorOccupation && actorAge 
          ? `${actorOccupation}, ${actorAge}` 
          : String(payload.actor_subtitle ?? payload.actor_agent_id ?? "Sampled persona");
        return [
          ...previous,
          {
            id: `post-${postId}`,
            postId,
            actorName,
            actorSubtitle,
            actorOccupation,
            actorAge,
            title,
            content,
            roundNo: Number(payload.round_no ?? 0),
            likes: 0,
            dislikes: 0,
            comments: [],
          },
        ];
      });
      return;
    }

    if (eventType === "comment_created") {
      setFeedThreads((previous) => {
        const postId = payload.post_id;
        return previous.map((thread) =>
          thread.postId === postId
            ? {
                ...thread,
                comments: [
                  ...thread.comments,
                  {
                    id: String(payload.comment_id ?? `${thread.id}-${thread.comments.length + 1}`),
                    actorName: String(payload.actor_name ?? payload.actor_agent_id ?? "Agent"),
                    content: String(payload.content ?? ""),
                  },
                ],
              }
            : thread,
        );
      });
      return;
    }

    if (eventType === "reaction_added") {
      setFeedThreads((previous) =>
        previous.map((thread) => {
          if (thread.postId !== payload.post_id) return thread;
          const reaction = String(payload.reaction ?? "");
          return {
            ...thread,
            likes: thread.likes + (reaction === "like" ? 1 : 0),
            dislikes: thread.dislikes + (reaction === "dislike" ? 1 : 0),
          };
        }),
      );
      return;
    }

    if (eventType === "run_completed") {
      setSimulationComplete(true);
    }

    if (eventType === "run_failed") {
      setError(String(payload.error ?? "Simulation failed."));
      closeStream();
    }
  }, [closeStream, setSimulationComplete]);

  const openStream = useCallback((activeSessionId: string) => {
    closeStream();
    const source = new EventSource(buildSimulationStreamUrl(activeSessionId));
    streamRef.current = source;
    const eventTypes = [
      "run_started",
      "checkpoint_started",
      "checkpoint_completed",
      "round_started",
      "post_created",
      "comment_created",
      "reaction_added",
      "metrics_updated",
      "round_completed",
      "run_completed",
      "run_failed",
    ];
    eventTypes.forEach((type) => {
      source.addEventListener(type, (event) => {
        handleSimulationEvent(JSON.parse(event.data));
      });
    });
    source.addEventListener("heartbeat", () => undefined);
    source.onerror = () => {
      source.close();
    };
  }, [closeStream, handleSimulationEvent]);

  const handleStartSimulation = useCallback(async () => {
    if (!sessionId || !knowledgeArtifact) {
      setError("Complete Screen 1 and Screen 2 before starting the simulation.");
      return;
    }
    setLoading(true);
    setError(null);
    setFeedThreads([]);
    setSimulationComplete(false);
    try {
      const state = await startSimulation(sessionId, {
        policy_summary: knowledgeArtifact.summary,
        rounds: simulationRounds,
      });
      setSimulationState(state);
      openStream(sessionId);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to start simulation.");
    } finally {
      setLoading(false);
    }
  }, [knowledgeArtifact, openStream, sessionId, setSimulationComplete, simulationRounds]);

  const handleProceed = useCallback(() => {
    completeStep(3);
    setCurrentStep(4);
  }, [completeStep, setCurrentStep]);

  return (
    <div className="flex h-full p-6 gap-6 overflow-hidden">
      <div className="flex-1 flex flex-col gap-4 min-w-0">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-foreground">Live Social Simulation</h2>
            <p className="text-sm text-muted-foreground">Real-time Reddit discourse from native OASIS, grounded in the McKAInsey knowledge graph.</p>
          </div>
          <div className="flex gap-3">
            {!completed && (
              <Button onClick={handleStartSimulation} disabled={loading || running || !sessionId || !populationArtifact} className="bg-primary text-primary-foreground">
                {loading || running ? <><Loader2 className="w-4 h-4 animate-spin" /> Starting...</> : <><Play className="w-4 h-4" /> Start Simulation</>}
              </Button>
            )}
            {completed && (
              <Button onClick={handleProceed} variant="outline" className="border-success/30 text-success hover:bg-success/10">
                <ArrowRight className="w-4 h-4" /> Generate Report
              </Button>
            )}
          </div>
        </div>

        <GlassCard className="p-5">
          <div className="grid grid-cols-1 xl:grid-cols-[1.05fr_0.95fr] gap-5 items-start">
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm text-muted-foreground">Simulation Rounds</span>
                <span className="text-2xl font-mono font-bold text-primary">{simulationRounds}</span>
              </div>
              <Slider value={[simulationRounds]} onValueChange={(value) => setSimulationRounds(value[0])} min={1} max={8} step={1} />
              <div className="flex items-center gap-2 mt-3 text-[11px] text-muted-foreground font-mono">
                <Clock className="w-3.5 h-3.5" />
                <span>Estimated time: ~{formatSeconds(estimatedTime)}</span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <MetricCard label="Visible Events" value={String(simulationState?.event_count ?? 0)} icon={<Waves className="w-4 h-4 text-primary" />} />
              <MetricCard label="Elapsed" value={formatSeconds(simulationState?.elapsed_seconds ?? 0)} icon={<TimerReset className="w-4 h-4 text-primary" />} />
              <MetricCard label="ETA" value={formatSeconds(simulationState?.estimated_remaining_seconds ?? estimatedTime)} icon={<TimerReset className="w-4 h-4 text-primary" />} />
              <MetricCard
                label="Hottest Thread"
                value={hottestThread?.title ? `${String(hottestThread.title)} · ${Number(hottestThread.engagement ?? 0)}` : "Awaiting activity"}
                icon={<MessageSquare className="w-4 h-4 text-primary" />}
                compact
              />
            </div>
          </div>
        </GlassCard>

        <div className="grid grid-cols-1 xl:grid-cols-[1.35fr_0.65fr] gap-4 min-h-0 flex-1">
          <GlassCard className="p-4 min-h-0 flex flex-col">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-sm font-semibold text-foreground">Topic Community</h3>
                <p className="text-xs text-muted-foreground">Auto-scrolling live feed of Reddit posts, comments, and reactions.</p>
              </div>
              <div className="text-xs text-muted-foreground font-mono">
                Round {simulationState?.current_round ?? 0} / {simulationRounds}
              </div>
            </div>
            <Progress value={(((simulationState?.current_round ?? 0) / Math.max(1, simulationRounds)) * 100)} className="h-2 mb-4" />

            <div ref={feedRef} className="flex-1 overflow-y-auto space-y-3 pr-1 scrollbar-thin">
              {feedThreads.map((thread) => {
                const colors = getOccupationColor(thread.actorOccupation);
                return (
                  <GlassCard key={thread.id} className={`p-4 bg-white/[0.03] border ${colors.border} hover:bg-white/[0.05] transition-colors`}>
                    <div className="flex items-start justify-between gap-4 mb-2">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-full ${colors.bg} flex items-center justify-center text-sm font-bold ${colors.text} border ${colors.border}`}>
                          {thread.actorName.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()}
                        </div>
                        <div>
                          <div className={`text-sm font-semibold ${colors.text}`}>{thread.actorName}</div>
                          <div className="text-[11px] text-muted-foreground">{thread.actorSubtitle}</div>
                        </div>
                      </div>
                      <div className="text-[11px] text-muted-foreground font-mono bg-white/5 px-2 py-1 rounded">R{thread.roundNo}</div>
                    </div>
                    <h4 className="text-sm font-semibold text-foreground mb-1">{thread.title}</h4>
                    <p className="text-xs text-muted-foreground leading-relaxed">{thread.content}</p>
                    <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1 hover:text-emerald-400 transition-colors"><ThumbsUp className="w-3 h-3" /> {thread.likes}</span>
                      <span className="flex items-center gap-1 hover:text-rose-400 transition-colors"><ThumbsDown className="w-3 h-3" /> {thread.dislikes}</span>
                      <span className="flex items-center gap-1 hover:text-primary transition-colors"><MessageSquare className="w-3 h-3" /> {thread.comments.length}</span>
                    </div>
                    {thread.comments.length > 0 && (
                      <div className="mt-3 space-y-2 border-l-2 border-white/10 pl-3">
                        {thread.comments.map((comment) => (
                          <div key={comment.id} className="text-xs">
                            <span className="font-medium text-foreground">{comment.actorName}</span>
                            <span className="text-muted-foreground ml-2">{comment.content}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </GlassCard>
                );
              })}
              {feedThreads.length === 0 && (
                <div className="flex items-center justify-center h-48 text-muted-foreground text-sm">
                  Configure rounds and start the simulation
                </div>
              )}
            </div>
          </GlassCard>

          <div className="space-y-4">
            <GlassCard className="p-4">
              <h4 className="text-xs uppercase tracking-wider text-muted-foreground mb-3">Discussion Momentum</h4>
              <div className="space-y-3">
                <StatLine label="Posts" value={counters.posts} />
                <StatLine label="Comments" value={counters.comments} />
                <StatLine label="Reactions" value={counters.reactions} />
                <StatLine label="Active Authors" value={counters.active_authors} />
                <StatLine label="Dominant Stance" value={String(simulationState?.discussion_momentum?.dominant_stance ?? "mixed")} />
              </div>
            </GlassCard>

            <GlassCard className="p-4">
              <h4 className="text-xs uppercase tracking-wider text-muted-foreground mb-3">Checkpoint Status</h4>
              <div className="space-y-3">
                <CheckpointLine label="Baseline" status={baselineStatus} />
                <CheckpointLine label="Final" status={finalStatus} />
              </div>
            </GlassCard>

            {error && (
              <GlassCard className="p-4 border border-destructive/30">
                <div className="text-sm font-semibold text-destructive">Simulation Error</div>
                <p className="text-xs text-muted-foreground mt-1">{error}</p>
              </GlassCard>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ label, value, icon, compact = false }: { label: string; value: string; icon: ReactNode; compact?: boolean }) {
  return (
    <div className={`rounded-2xl border border-white/10 bg-white/[0.03] p-3 ${compact ? "col-span-2" : ""}`}>
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-muted-foreground mb-1">
        {icon}
        <span>{label}</span>
      </div>
      <div className={`text-foreground ${compact ? "text-sm font-semibold" : "text-lg font-mono font-bold"}`}>{value}</div>
    </div>
  );
}

function StatLine({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono text-foreground">{value}</span>
    </div>
  );
}

function CheckpointLine({ label, status }: { label: string; status: string }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono text-foreground capitalize">{status}</span>
    </div>
  );
}

function formatSeconds(value: number | null | undefined): string {
  const seconds = Math.max(0, Number(value ?? 0));
  return `${Math.round(seconds)}s`;
}

function estimateRuntimeSeconds(agentCount: number, rounds: number): number {
  const checkpointSeconds = Math.max(8, Math.floor(agentCount * 0.18));
  const roundSeconds = Math.max(10, Math.floor(agentCount * 0.05) + 6);
  return (checkpointSeconds * 2) + (roundSeconds * rounds);
}

function reduceSimulationState(previous: SimulationState | null, payload: Record<string, unknown>): SimulationState {
  const base: SimulationState = previous ?? {
    session_id: String(payload.session_id ?? ""),
    status: "running",
    event_count: 0,
    last_round: 0,
    platform: "reddit",
    planned_rounds: 0,
    current_round: 0,
    elapsed_seconds: 0,
    estimated_total_seconds: 0,
    estimated_remaining_seconds: 0,
    counters: { posts: 0, comments: 0, reactions: 0, active_authors: 0 },
    checkpoint_status: {
      baseline: { status: "pending", completed_agents: 0, total_agents: 0 },
      final: { status: "pending", completed_agents: 0, total_agents: 0 },
    },
    top_threads: [],
    discussion_momentum: {},
    latest_metrics: {},
    recent_events: [],
  };

  const eventType = String(payload.event_type ?? "");
  const next: SimulationState = {
    ...base,
    event_count: base.event_count + 1,
    last_round: Math.max(base.last_round, Number(payload.round_no ?? base.last_round ?? 0)),
    current_round: Math.max(base.current_round ?? 0, Number(payload.round_no ?? base.current_round ?? 0)),
    recent_events: [...base.recent_events, payload].slice(-10),
  };

  if (eventType === "checkpoint_started" || eventType === "checkpoint_completed") {
    const key = String(payload.checkpoint_kind ?? "baseline");
    next.checkpoint_status = {
      ...base.checkpoint_status,
      [key]: {
        status: eventType === "checkpoint_started" ? "running" : "completed",
        completed_agents: Number(payload.completed_agents ?? base.checkpoint_status?.[key]?.completed_agents ?? 0),
        total_agents: Number(payload.total_agents ?? base.checkpoint_status?.[key]?.total_agents ?? 0),
      },
    };
  }

  if (eventType === "metrics_updated") {
    next.counters = {
      posts: Number(payload.counters && typeof payload.counters === "object" ? (payload.counters as Record<string, unknown>).posts ?? base.counters.posts : base.counters.posts),
      comments: Number(payload.counters && typeof payload.counters === "object" ? (payload.counters as Record<string, unknown>).comments ?? base.counters.comments : base.counters.comments),
      reactions: Number(payload.counters && typeof payload.counters === "object" ? (payload.counters as Record<string, unknown>).reactions ?? base.counters.reactions : base.counters.reactions),
      active_authors: Number(payload.counters && typeof payload.counters === "object" ? (payload.counters as Record<string, unknown>).active_authors ?? base.counters.active_authors : base.counters.active_authors),
    };
    next.elapsed_seconds = Number(payload.elapsed_seconds ?? base.elapsed_seconds ?? 0);
    next.estimated_total_seconds = Number(payload.estimated_total_seconds ?? base.estimated_total_seconds ?? 0);
    next.estimated_remaining_seconds = Number(payload.estimated_remaining_seconds ?? base.estimated_remaining_seconds ?? 0);
    next.top_threads = Array.isArray(payload.top_threads) ? (payload.top_threads as Array<Record<string, unknown>>) : base.top_threads;
    next.discussion_momentum = (payload.discussion_momentum as Record<string, unknown>) ?? base.discussion_momentum;
    next.latest_metrics = payload;
  }

  if (eventType === "run_completed") {
    next.status = "completed";
    next.elapsed_seconds = Number(payload.elapsed_seconds ?? next.elapsed_seconds ?? 0);
  } else if (eventType === "run_failed") {
    next.status = "failed";
  } else {
    next.status = "running";
  }

  return next;
}
