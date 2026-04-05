import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowRight, Flame, Loader2, MessageSquare, Play, ThumbsDown, ThumbsUp, Clock, TrendingUp, Sparkles, Users, Zap } from "lucide-react";

import { GlassCard } from "@/components/GlassCard";
import { Button } from "@/components/ui/button";
import { useApp } from "@/contexts/AppContext";
import { generateSimPosts, type SimComment, type SimPost } from "@/data/mockData";
import { toast } from "@/hooks/use-toast";
import { buildSimulationStreamUrl, SimulationState, startSimulation } from "@/lib/console-api";

type FeedComment = {
  id: string;
  actorName: string;
  content: string;
  roundNo: number;
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
  activityRounds: number[];
  likes: number;
  dislikes: number;
  comments: FeedComment[];
};

type ActorTone = {
  avatarBg: string;
  avatarText: string;
  avatarBorder: string;
  nameText: string;
};

const POSITIVE_TONE: ActorTone = {
  avatarBg: "bg-success/15",
  avatarText: "text-success",
  avatarBorder: "border-success/30",
  nameText: "text-success",
};

const DEFAULT_TONE: ActorTone = {
  avatarBg: "bg-white/10",
  avatarText: "text-foreground/80",
  avatarBorder: "border-white/15",
  nameText: "text-foreground/85",
};

function getActorTone(thread: FeedThread): ActorTone {
  return thread.likes > thread.dislikes ? POSITIVE_TONE : DEFAULT_TONE;
}

type SortOption = "new" | "popular";
type StageStatus = "pending" | "running" | "completed";
type ProcessStage = {
  id: string;
  title: string;
  detail: string;
  status: StageStatus;
};

// Custom styled slider with marks
function RoundSlider({ value, onChange, min = 1, max = 8 }: { value: number; onChange: (v: number) => void; min?: number; max?: number }) {
  const marks = useMemo(() => Array.from({ length: max - min + 1 }, (_, i) => min + i), [min, max]);
  const percentage = ((value - min) / (max - min)) * 100;

  return (
    <div className="relative w-full pt-2 pb-9">
      <div className="relative h-8">
        <div className="absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 overflow-hidden rounded-full bg-white/5">
          <div
            className="h-full bg-gradient-to-r from-primary/60 via-primary to-primary/80 transition-all duration-300 ease-out"
            style={{ width: `${percentage}%` }}
          />
        </div>

        <div className="absolute inset-x-0 top-1/2 flex -translate-y-1/2 items-center justify-between">
          {marks.map((mark) => (
            <button
              key={mark}
              onClick={() => onChange(mark)}
              className={`group relative flex h-7 w-7 items-center justify-center rounded-full transition-all duration-300 ${
                value === mark ? "scale-110" : "hover:scale-105"
              }`}
            >
              <div
                className={`h-2.5 w-2.5 rounded-full transition-all duration-300 ${
                  value >= mark ? "bg-primary shadow-lg shadow-primary/40" : "bg-white/20 group-hover:bg-white/35"
                } ${value === mark ? "scale-150" : ""}`}
              />
              <span
                className={`absolute top-8 text-xs font-mono transition-all duration-300 ${
                  value === mark ? "font-bold text-primary" : "text-white/35 group-hover:text-white/60"
                }`}
              >
                {mark}
              </span>
            </button>
          ))}
        </div>
      </div>

      <input
        type="range"
        min={min}
        max={max}
        step={1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="absolute left-0 right-0 top-2 h-8 cursor-pointer opacity-0"
      />
    </div>
  );
}

export default function Simulation() {
  const {
    sessionId,
    modelProvider,
    knowledgeArtifact,
    populationArtifact,
    agents,
    simulationRounds,
    setSimulationRounds,
    setSimulationComplete,
    completeStep,
    setCurrentStep,
  } = useApp();

  const [simulationState, setSimulationState] = useState<SimulationState | null>(null);
  const [feedThreads, setFeedThreads] = useState<FeedThread[]>([]);
  const [controversyBoost, setControversyBoost] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedRound, setSelectedRound] = useState<number | "all">("all");
  const [sortBy, setSortBy] = useState<SortOption>("new");
  const [expandedReplies, setExpandedReplies] = useState<Record<string, boolean>>({});
  const streamRef = useRef<EventSource | null>(null);
  const feedRef = useRef<HTMLDivElement>(null);

  // Available rounds based on simulationRounds selection (1 to simulationRounds)
  const availableRounds = useMemo(() => {
    return Array.from({ length: simulationRounds }, (_, i) => i + 1);
  }, [simulationRounds]);

  // Filtered and sorted threads
  const displayedThreads = useMemo(() => {
    let threads = [...feedThreads];
    
    // Filter by round
    if (selectedRound !== "all") {
      threads = threads.filter((thread) => thread.activityRounds.includes(selectedRound));
    }
    
    // Sort
    if (sortBy === "popular") {
      threads.sort((a, b) => (b.likes + b.comments.length) - (a.likes + a.comments.length));
    } else {
      // Keep original order (newest first) - already in order they were received
      threads = threads.reverse();
    }
    
    return threads;
  }, [feedThreads, selectedRound, sortBy]);

  const counters = simulationState?.counters ?? { posts: 0, comments: 0, reactions: 0, active_authors: 0 };
  const running = simulationState?.status === "running";
  const completed = simulationState?.status === "completed";
  const baselineStatus = simulationState?.checkpoint_status?.baseline?.status ?? "pending";
  const finalStatus = simulationState?.checkpoint_status?.final?.status ?? "pending";

  const runtimeEstimate = useMemo(
    () => estimateRuntimeBreakdown(populationArtifact?.sample_count ?? 0, simulationRounds, modelProvider),
    [modelProvider, populationArtifact?.sample_count, simulationRounds],
  );
  const estimatedTime = runtimeEstimate.totalSeconds;
  const hottestThread = simulationState?.top_threads?.[0] as { title?: string; engagement?: number } | undefined;

  const closeStream = useCallback(() => {
    streamRef.current?.close();
    streamRef.current = null;
  }, []);

  useEffect(() => () => closeStream(), [closeStream]);

  useEffect(() => {
    if (!feedRef.current) return;
    const scrollDistanceFromBottom = feedRef.current.scrollHeight - feedRef.current.scrollTop - feedRef.current.clientHeight;
    if (scrollDistanceFromBottom < 120) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [feedThreads.length]);

  const processStages = useMemo<ProcessStage[]>(() => {
    const hasRun = simulationState !== null;
    const baseline = simulationState?.checkpoint_status?.baseline?.status ?? "pending";
    const final = simulationState?.checkpoint_status?.final?.status ?? "pending";
    const currentRound = Number(simulationState?.current_round ?? 0);
    const plannedRounds = Number(simulationState?.planned_rounds ?? simulationRounds);

    const recentEvents = Array.isArray(simulationState?.recent_events) ? simulationState?.recent_events : [];
    const latestBatchEvent = [...recentEvents].reverse().find(
      (event) => typeof event?.event_type === "string" && event.event_type === "round_batch_flushed",
    ) as Record<string, unknown> | undefined;

    const roundsStatus: StageStatus = completed
      ? "completed"
      : running && currentRound > 0
        ? "running"
        : "pending";
    const streamingStatus: StageStatus = completed
      ? "completed"
      : latestBatchEvent
        ? "running"
        : "pending";

    return [
      {
        id: "run-start",
        title: "Initialize OASIS runtime",
        detail: hasRun ? "Runner bootstrapped and event stream connected" : "Waiting for simulation start",
        status: hasRun ? "completed" : "pending",
      },
      {
        id: "baseline",
        title: "Baseline checkpoint",
        detail: `Status: ${baseline}`,
        status: baseline === "completed" ? "completed" : baseline === "running" ? "running" : "pending",
      },
      {
        id: "round-execution",
        title: "Round execution",
        detail: `Round ${Math.max(0, currentRound)} of ${Math.max(1, plannedRounds)}`,
        status: roundsStatus,
      },
      {
        id: "batch-stream",
        title: "Batch event streaming",
        detail: latestBatchEvent
          ? `Batch ${Number(latestBatchEvent.batch_index ?? 0)} of ${Number(latestBatchEvent.batch_count ?? 0)} in round ${Number(latestBatchEvent.round_no ?? currentRound)}`
          : "No flushed batches yet",
        status: streamingStatus,
      },
      {
        id: "final-checkpoint",
        title: "Final checkpoint",
        detail: `Status: ${final}`,
        status: final === "completed" ? "completed" : final === "running" ? "running" : "pending",
      },
      {
        id: "artifact-finalization",
        title: "Finalize artifacts",
        detail: completed ? "Simulation artifacts ready for report generation" : "Awaiting completion",
        status: completed ? "completed" : "pending",
      },
    ];
  }, [completed, running, simulationRounds, simulationState]);

  const handleSimulationEvent = useCallback((payload: Record<string, unknown>) => {
    const eventType = String(payload.event_type ?? "");
    setSimulationState((previous: SimulationState | null) => reduceSimulationState(previous, payload));

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
        const roundNo = Number(payload.round_no ?? 0);
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
            roundNo,
            activityRounds: mergeRoundActivity([], roundNo),
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
          isSamePostId(thread.postId, postId)
            ? (() => {
                const eventRound = Number(payload.round_no ?? thread.roundNo ?? 0);
                return {
                  ...thread,
                  activityRounds: mergeRoundActivity(thread.activityRounds, eventRound),
                  comments: [
                    ...thread.comments,
                    {
                      id: String(payload.comment_id ?? `${thread.id}-${thread.comments.length + 1}`),
                      actorName: String(payload.actor_name ?? payload.actor_agent_id ?? "Agent"),
                      content: String(payload.content ?? ""),
                      roundNo: eventRound,
                    },
                  ],
                };
              })()
            : thread,
        );
      });
      return;
    }

    if (eventType === "reaction_added") {
      setFeedThreads((previous) =>
        previous.map((thread) => {
          if (!isSamePostId(thread.postId, payload.post_id)) return thread;
          const reaction = String(payload.reaction ?? "");
          const eventRound = Number(payload.round_no ?? thread.roundNo ?? 0);
          return {
            ...thread,
            activityRounds: mergeRoundActivity(thread.activityRounds, eventRound),
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
      "round_batch_flushed",
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
    setExpandedReplies({});
    setSimulationComplete(false);
    try {
      const state = await startSimulation(sessionId, {
        policy_summary: knowledgeArtifact.summary,
        rounds: simulationRounds,
        controversy_boost: controversyBoost ? 0.5 : 0.0,
      });
      setSimulationState(state);
      openStream(sessionId);
    } catch (caughtError) {
      const fallbackAgents = agents.length > 0 ? agents : [];
      if (fallbackAgents.length > 0) {
        closeStream();

        const mockPosts = generateSimPosts(simulationRounds, fallbackAgents);
        const demoThreads: FeedThread[] = mockPosts.map((post: SimPost) => ({
          id: post.id,
          postId: post.id,
          actorName: post.agentName,
          actorSubtitle: `${post.agentOccupation} · ${post.agentArea}`,
          actorOccupation: post.agentOccupation,
          title: post.title,
          content: post.content,
          roundNo: post.round,
          activityRounds: [post.round],
          likes: post.upvotes,
          dislikes: post.downvotes,
          comments: post.comments.map((comment: SimComment) => ({
            id: comment.id,
            actorName: comment.agentName,
            content: comment.content,
            roundNo: post.round,
          })),
        }));

        const commentsTotal = demoThreads.reduce((total, thread) => total + thread.comments.length, 0);
        const reactionsTotal = demoThreads.reduce((total, thread) => total + thread.likes + thread.dislikes, 0);
        const activeAuthors = new Set(demoThreads.map((thread) => thread.actorName)).size;
        const topThreads = [...demoThreads]
          .map((thread) => ({
            title: thread.title,
            engagement: thread.likes + thread.dislikes + thread.comments.length,
          }))
          .sort((left, right) => Number(right.engagement) - Number(left.engagement))
          .slice(0, 3);

        const sampledAgents = populationArtifact?.sample_count ?? fallbackAgents.length;
        const elapsedSeconds = Math.max(45, Math.round(estimatedTime));

        setFeedThreads(demoThreads);
        setSimulationState({
          session_id: sessionId,
          status: "completed",
          event_count: demoThreads.length + commentsTotal,
          last_round: simulationRounds,
          platform: "reddit",
          planned_rounds: simulationRounds,
          current_round: simulationRounds,
          elapsed_seconds: elapsedSeconds,
          estimated_total_seconds: elapsedSeconds,
          estimated_remaining_seconds: 0,
          counters: {
            posts: demoThreads.length,
            comments: commentsTotal,
            reactions: reactionsTotal,
            active_authors: activeAuthors,
          },
          checkpoint_status: {
            baseline: { status: "completed", completed_agents: sampledAgents, total_agents: sampledAgents },
            final: { status: "completed", completed_agents: sampledAgents, total_agents: sampledAgents },
          },
          top_threads: topThreads,
          discussion_momentum: {},
          latest_metrics: {
            approval_rate: 68,
            net_sentiment: 7.2,
          },
          recent_events: [],
        });
        setSimulationComplete(true);
        toast({
          title: "Demo simulation loaded",
          description: "Backend is unavailable, so mock discussion posts were generated for UI preview.",
        });
        return;
      }

      setError(caughtError instanceof Error ? caughtError.message : "Unable to start simulation.");
    } finally {
      setLoading(false);
    }
  }, [agents, closeStream, estimatedTime, knowledgeArtifact, openStream, populationArtifact?.sample_count, sessionId, setSimulationComplete, simulationRounds]);

  const handleProceed = useCallback(() => {
    completeStep(3);
    setCurrentStep(4);
  }, [completeStep, setCurrentStep]);

  return (
    <div className="flex h-full min-h-0 gap-6 overflow-hidden p-6">
      <div className="flex-1 flex flex-col gap-4 min-w-0">
        {/* Header - removed Generate Report button from here */}
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-foreground">Live Social Simulation</h2>
            <p className="text-sm text-muted-foreground">Real-time Reddit discourse from native OASIS, grounded in the McKAInsey knowledge graph.</p>
          </div>
          {!completed ? (
            <Button 
              onClick={handleStartSimulation} 
              disabled={loading || running || !sessionId || !populationArtifact} 
              className="bg-primary text-primary-foreground"
            >
              {loading || running ? <><Loader2 className="w-4 h-4 animate-spin" /> Starting...</> : <><Play className="w-4 h-4" /> Start Simulation</>}
            </Button>
          ) : (
            <Button 
              onClick={handleProceed} 
              variant="outline" 
              className="h-10 border border-success/30 bg-success/20 px-4 font-mono text-xs uppercase tracking-wider text-success hover:bg-success/30"
            >
              <ArrowRight className="w-4 h-4" /> Generate Report
            </Button>
          )}
        </div>

        {/* Main Content: Number Picker + Feed + Stats */}
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.42fr)_minmax(340px,0.78fr)] gap-5 min-h-0 flex-1">
          {/* Left Column: Number Picker + Feed */}
          <div className="flex flex-col gap-4 min-h-0">
            <div className="grid grid-cols-1 2xl:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)] auto-rows-fr items-stretch gap-4 shrink-0">
              <GlassCard className="p-4 min-h-[168px] flex h-full flex-col gap-3">
                <div>
                  <div className="mb-2 flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-primary/70" />
                    <h3 className="text-sm font-medium text-foreground">Simulation Rounds</h3>
                  </div>

                  <RoundSlider 
                    value={simulationRounds} 
                    onChange={setSimulationRounds} 
                    min={1} 
                    max={8} 
                  />
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto] items-center gap-3 text-xs">
                  <div className="flex flex-wrap items-center gap-2">
                    <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                    <span className="font-mono font-semibold text-foreground">
                      ~{formatSeconds(estimatedTime)}
                    </span>
                    <span className="text-white/20">|</span>
                    <span className="text-muted-foreground font-mono">{populationArtifact?.sample_count ?? 250} agents × {simulationRounds} rounds</span>
                  </div>
                  <div className="justify-self-start lg:justify-self-end font-mono text-primary/85 bg-primary/10 px-2 py-0.5 rounded border border-primary/20">
                    ~${(0.85 * simulationRounds).toFixed(2)} cost
                  </div>
                </div>
              </GlassCard>

              <GlassCard className="p-4 min-h-[168px] flex h-full flex-col justify-between gap-3">
                <div className="flex items-center gap-2 w-full">
                  <Flame className={`w-4 h-4 ${controversyBoost ? "text-[hsl(var(--data-red))]" : "text-muted-foreground"}`} />
                  <h3 className="text-sm font-medium text-foreground flex-1">Controversy Boost</h3>
                  <button 
                    onClick={() => setControversyBoost(!controversyBoost)}
                    className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center justify-center rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${controversyBoost ? 'bg-[hsl(var(--data-red))]' : 'bg-white/10'}`}
                  >
                    <span className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200 ease-in-out ${controversyBoost ? 'translate-x-2' : '-translate-x-2'}`} />
                  </button>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Toggle to model social media ragebait logic. Engages highly controversial posts alongside universally liked content.
                </p>
              </GlassCard>
            </div>

            {/* Feed - takes remaining space */}
            <GlassCard className="p-0 min-h-0 flex flex-col overflow-hidden flex-1">
              <div className="p-4 border-b border-white/5 bg-white/[0.02]">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <MessageSquare className="w-4 h-4 text-muted-foreground" />
                    <div>
                      <h3 className="text-sm font-semibold text-foreground">Topic Community</h3>
                      <p className="text-[11px] text-muted-foreground">Live discourse feed</p>
                    </div>
                  </div>
                  <div className="px-2 py-1 rounded-md bg-white/5 border border-white/10">
                    <span className="text-sm font-mono font-bold text-primary">{simulationState?.current_round ?? 0}</span>
                    <span className="text-xs text-muted-foreground">/{simulationRounds}</span>
                  </div>
                </div>
                
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground uppercase tracking-wider">View:</span>
                    <select
                      value={selectedRound === "all" ? "all" : String(selectedRound)}
                      onChange={(e) => setSelectedRound(e.target.value === "all" ? "all" : Number(e.target.value))}
                      className="bg-white/[0.03] border border-white/10 rounded-lg px-3 py-2 pr-8 text-xs text-foreground focus:outline-none focus:border-primary/30 appearance-none cursor-pointer min-w-[100px]"
                      style={{ 
                        backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%239CA3AF' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E")`,
                        backgroundRepeat: 'no-repeat',
                        backgroundPosition: 'right 8px center'
                      }}
                    >
                      <option value="all">All Rounds</option>
                      {availableRounds.map((round) => (
                        <option key={round} value={round}>Round {round}</option>
                      ))}
                    </select>
                  </div>
                  
                  <div className="flex items-center gap-1 bg-white/[0.03] rounded-lg p-1 border border-white/5">
                    <button
                      onClick={() => setSortBy("new")}
                      className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all flex items-center gap-1.5
                        ${sortBy === "new" 
                          ? 'bg-white/10 text-foreground border border-white/10' 
                          : 'text-muted-foreground hover:text-foreground'
                        }`}
                    >
                      <Clock className="w-3 h-3" /> New
                    </button>
                    <button
                      onClick={() => setSortBy("popular")}
                      className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all flex items-center gap-1.5
                        ${sortBy === "popular" 
                          ? 'bg-white/10 text-foreground border border-white/10' 
                          : 'text-muted-foreground hover:text-foreground'
                        }`}
                    >
                      <TrendingUp className="w-3 h-3" /> Popular
                    </button>
                  </div>
                </div>
              </div>

              <div ref={feedRef} className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-thin">
                {displayedThreads.map((thread) => {
                  const tone = getActorTone(thread);
                  const isExpanded = Boolean(expandedReplies[thread.id]);
                  const visibleComments = isExpanded ? thread.comments : thread.comments.slice(0, 3);
                  return (
                    <GlassCard key={thread.id} className="p-4 bg-white/[0.02] border border-white/10 hover:bg-white/[0.04] transition-all duration-200 group">
                      <div className="flex items-start justify-between gap-4 mb-3">
                        <div className="flex items-center gap-3">
                          <div className={`w-10 h-10 rounded-full ${tone.avatarBg} flex items-center justify-center text-sm font-bold ${tone.avatarText} border ${tone.avatarBorder}`}>
                            {thread.actorName.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()}
                          </div>
                          <div>
                            <div className={`text-sm font-semibold ${tone.nameText}`}>{thread.actorName}</div>
                            <div className="text-[11px] text-muted-foreground flex items-center gap-1.5">
                              <span>{thread.actorSubtitle}</span>
                              <span className="w-1 h-1 rounded-full bg-white/20" />
                              <span className="font-mono text-white/40">R{thread.roundNo}</span>
                            </div>
                          </div>
                        </div>
                        <div className="px-2 py-1 rounded-full text-[10px] font-medium bg-white/5 text-muted-foreground border border-white/10">
                          {thread.actorOccupation || "Agent"}
                        </div>
                      </div>
                      
                      <h4 className="text-sm font-semibold text-foreground mb-2 leading-tight">{thread.title}</h4>
                      <p className="text-xs text-muted-foreground leading-relaxed whitespace-pre-wrap">{thread.content}</p>
                      
                      <div className="flex items-center gap-5 mt-4 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1.5 hover:text-foreground transition-colors cursor-pointer">
                          <ThumbsUp className="w-3.5 h-3.5" /> 
                          <span className="font-mono font-medium">{thread.likes}</span>
                        </span>
                        <span className="flex items-center gap-1.5 hover:text-foreground transition-colors cursor-pointer">
                          <ThumbsDown className="w-3.5 h-3.5" /> 
                          <span className="font-mono font-medium">{thread.dislikes}</span>
                        </span>
                        <span className="flex items-center gap-1.5 hover:text-foreground transition-colors cursor-pointer">
                          <MessageSquare className="w-3.5 h-3.5" /> 
                          <span className="font-mono font-medium">{thread.comments.length}</span>
                          <span className="text-muted-foreground">comments</span>
                        </span>
                      </div>
                      
                      {thread.comments.length > 0 && (
                        <div className="mt-4 space-y-2.5 border-l-2 border-white/[0.08] pl-3">
                          {visibleComments.map((comment) => (
                            <div key={comment.id} className="text-xs flex items-start gap-2">
                              <div className="w-5 h-5 rounded-full bg-white/5 flex items-center justify-center text-[9px] font-bold text-white/40 flex-shrink-0">
                                {comment.actorName.split(' ').map(n => n[0]).join('').slice(0, 1).toUpperCase()}
                              </div>
                              <div className="flex-1 min-w-0">
                                <span className={`font-medium text-[11px] ${tone.nameText}`}>{comment.actorName}</span>
                                <span className="text-muted-foreground ml-2 whitespace-pre-wrap">{comment.content}</span>
                              </div>
                            </div>
                          ))}
                          {thread.comments.length > 3 && (
                            <button
                              type="button"
                              className="text-[10px] text-muted-foreground hover:text-foreground pl-7 transition-colors"
                              onClick={() =>
                                setExpandedReplies((previous) => ({
                                  ...previous,
                                  [thread.id]: !previous[thread.id],
                                }))
                              }
                            >
                              {isExpanded
                                ? "Show fewer replies"
                                : `View ${thread.comments.length - 3} more replies`}
                            </button>
                          )}
                        </div>
                      )}
                    </GlassCard>
                  );
                })}
                
                {displayedThreads.length === 0 && (
                  <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
                    <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mb-4">
                      <MessageSquare className="w-8 h-8 text-white/20" />
                    </div>
                    <p className="text-sm">No posts to display</p>
                  </div>
                )}
              </div>
            </GlassCard>
          </div>

          {/* Right: Stats Panel - Now starts from top */}
          <div className="grid min-h-0 grid-rows-[minmax(136px,auto)_minmax(136px,auto)_1fr] gap-4">
            {/* Hottest Thread */}
            <GlassCard className="p-4 h-full">
              <div className="flex items-center gap-2 mb-3">
                <Flame className="w-4 h-4 text-primary" />
                <h4 className="text-xs uppercase tracking-wider text-primary font-semibold">Hottest Thread</h4>
              </div>
              
              {hottestThread?.title ? (
                <div>
                  <h3 className="text-base font-semibold text-foreground leading-tight mb-3 line-clamp-2">
                    {String(hottestThread.title)}
                  </h3>
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 border border-primary/20 w-fit">
                    <TrendingUp className="w-3.5 h-3.5 text-primary" />
                    <span className="text-sm font-mono font-bold text-primary">
                      {Number(hottestThread.engagement ?? 0).toLocaleString()}
                    </span>
                    <span className="text-xs text-primary/70">engagement</span>
                  </div>
                </div>
              ) : (
                <div className="py-6 text-center">
                  <p className="text-sm text-muted-foreground">Awaiting activity...</p>
                </div>
              )}
            </GlassCard>

            {/* Time Elapsed - Big */}
            <GlassCard className="p-3 h-full">
              <div className="mb-2 flex items-center gap-2">
                <Clock className="w-4 h-4 text-muted-foreground" />
                <h4 className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Time Elapsed</h4>
              </div>
              
              <div className="flex items-center">
                <span className="text-2xl font-mono font-bold text-foreground leading-none">
                  {formatSeconds(simulationState?.elapsed_seconds ?? 0)}
                </span>
              </div>
              
              {running && (
                <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  <span>Simulation in progress...</span>
                </div>
              )}
              
              {completed && (
                <div className="mt-2 flex items-center gap-2 text-xs text-emerald-400">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  <span>Completed</span>
                </div>
              )}
            </GlassCard>



            {/* Expanded Metrics */}
            <GlassCard className="p-4 flex min-h-0 h-full flex-col">
              <div className="flex items-center gap-2 mb-4">
                <Users className="w-4 h-4 text-primary" />
                <h4 className="text-xs uppercase tracking-wider text-muted-foreground font-medium">Metrics</h4>
              </div>
              
              <div className="grid grid-cols-2 gap-3 mb-4">
                <div className="p-3 rounded-lg bg-white/[0.03] border border-white/5">
                  <div className="text-xs text-muted-foreground mb-1">Posts</div>
                  <div className="text-2xl font-mono font-bold text-foreground">{counters.posts}</div>
                </div>
                <div className="p-3 rounded-lg bg-white/[0.03] border border-white/5">
                  <div className="text-xs text-muted-foreground mb-1">Comments</div>
                  <div className="text-2xl font-mono font-bold text-foreground">{counters.comments}</div>
                </div>
                <div className="p-3 rounded-lg bg-white/[0.03] border border-white/5">
                  <div className="text-xs text-muted-foreground mb-1">Reactions</div>
                  <div className="text-2xl font-mono font-bold text-foreground">{counters.reactions}</div>
                </div>
                <div className="p-3 rounded-lg bg-white/[0.03] border border-white/5">
                  <div className="text-xs text-muted-foreground mb-1">Authors</div>
                  <div className="text-2xl font-mono font-bold text-foreground">{counters.active_authors}</div>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-3 pt-1">
                <div className="flex flex-col gap-1 px-3 py-2 bg-white/[0.02] border border-white/5 rounded-lg">
                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Approval Rate</span>
                  <span className="text-xl font-mono font-bold text-success/90">
                    {readLatestMetric(simulationState, "approval_rate", 68).toFixed(1)}%
                  </span>
                </div>
                <div className="flex flex-col gap-1 px-3 py-2 bg-white/[0.02] border border-white/5 rounded-lg">
                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Net Sentiment</span>
                  <span className="text-xl font-mono font-bold text-success/90">
                    {readLatestMetric(simulationState, "net_sentiment", 7.2).toFixed(1)}/10
                  </span>
                </div>
              </div>
            </GlassCard>

            {error && (
              <GlassCard className="p-4 border border-destructive/30 bg-destructive/5">
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

function StatusBadge({ status }: { status: string }) {
  const styles = {
    pending: "bg-white/5 text-white/40 border-white/10",
    running: "bg-amber-500/10 text-amber-400 border-amber-500/20 animate-pulse",
    completed: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    failed: "bg-rose-500/10 text-rose-400 border-rose-500/20",
  };
  
  return (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium border capitalize ${styles[status as keyof typeof styles] || styles.pending}`}>
      {status}
    </span>
  );
}

function stageStatusClass(status: StageStatus): string {
  if (status === "completed") {
    return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
  }
  if (status === "running") {
    return "bg-amber-500/10 text-amber-400 border-amber-500/20";
  }
  return "bg-white/5 text-white/40 border-white/10";
}

function formatSeconds(value: number | null | undefined): string {
  const totalSeconds = Math.max(0, Math.round(Number(value ?? 0)));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}m ${String(seconds).padStart(2, "0")}s`;
}

function readLatestMetric(simulationState: SimulationState | null, metricName: string, fallback: number): number {
  const rawMetricValue = simulationState?.latest_metrics?.[metricName];
  const numericValue = Number(rawMetricValue);
  return Number.isFinite(numericValue) ? numericValue : fallback;
}

function estimateRuntimeBreakdown(agentCount: number, rounds: number, provider: string): {
  baselineCheckpointSeconds: number;
  roundWindowSeconds: number;
  finalCheckpointSeconds: number;
  totalSeconds: number;
} {
  const normalizedProvider = String(provider || "ollama").toLowerCase();
  const isOllama = normalizedProvider === "ollama";
  const safeAgentCount = Math.max(0, Number(agentCount || 0));
  const safeRounds = Math.max(1, Number(rounds || 1));

  const checkpointFloor = isOllama ? 40 : 8;
  const checkpointPerAgent = isOllama ? 3.6 : 0.22;
  const roundFloor = isOllama ? 45 : 10;
  const roundPerAgent = isOllama ? 6.8 : 0.06;
  const roundOverhead = isOllama ? 20 : 6;

  const baselineCheckpointSeconds = Math.max(
    checkpointFloor,
    Math.floor(safeAgentCount * checkpointPerAgent),
  );
  const finalCheckpointSeconds = baselineCheckpointSeconds;
  const perRoundSeconds = Math.max(roundFloor, Math.floor(safeAgentCount * roundPerAgent) + roundOverhead);
  const roundWindowSeconds = perRoundSeconds * safeRounds;

  return {
    baselineCheckpointSeconds,
    roundWindowSeconds,
    finalCheckpointSeconds,
    totalSeconds: baselineCheckpointSeconds + roundWindowSeconds + finalCheckpointSeconds,
  };
}

function mergeRoundActivity(existingRounds: number[], roundNo: number): number[] {
  const normalizedRound = Number(roundNo);
  if (!Number.isFinite(normalizedRound) || normalizedRound <= 0) {
    return existingRounds;
  }
  if (existingRounds.includes(normalizedRound)) {
    return existingRounds;
  }
  return [...existingRounds, normalizedRound].sort((left, right) => left - right);
}

function isSamePostId(left: string | number, right: unknown): boolean {
  if (right === null || right === undefined) {
    return false;
  }
  return String(left) === String(right);
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
