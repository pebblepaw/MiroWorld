import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowRight, Flame, Loader2, MessageSquare, Play, Clock, TrendingUp, Sparkles, Users, Zap } from "lucide-react";

import { GlassCard } from "@/components/GlassCard";
import { MarkdownContent } from "@/components/MarkdownContent";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useApp } from "@/contexts/AppContext";
import { toast } from "@/hooks/use-toast";
import {
  buildSimulationStreamUrl,
  getBundledDemoSimulationPosts,
  getSimulationMetrics,
  getSimulationState,
  isLiveBootMode,
  isStaticDemoBootMode,
  SimulationState,
  startSimulation,
} from "@/lib/console-api";

type FeedComment = {
  id: string;
  actorName: string;
  content: string;
  roundNo: number;
  likes: number;
  dislikes: number;
};

/** Replace underscores and title-case a label string (e.g. "not_in_workforce" → "Not In Workforce"). */
function _humanizeLabel(raw: string): string {
  return raw
    .replace(/_/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

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
  avatarBg: "bg-muted/70",
  avatarText: "text-foreground/80",
  avatarBorder: "border-border",
  nameText: "text-foreground/85",
};

function getActorTone(thread: FeedThread): ActorTone {
  return thread.likes > thread.dislikes ? POSITIVE_TONE : DEFAULT_TONE;
}

function resolveSimulationError(error: unknown): string {
  const rawMessage =
    error instanceof Error
      ? error.message.trim()
      : typeof error === "string"
        ? error.trim()
        : "";

  if (!rawMessage) {
    return "The simulation could not be completed. Check the backend logs and try again.";
  }

  const lowered = rawMessage.toLowerCase();
  if (lowered.includes("no module named 'camel'") || lowered.includes("no module named 'oasis'") || lowered.includes("missing required packages")) {
    return "Simulation runtime is unavailable because the OASIS Python environment is missing required packages.";
  }
  if (lowered.includes("oasis python runtime is unavailable") || lowered.includes("oasis python runtime not found")) {
    return "Simulation runtime is unavailable. Reinstall the OASIS Python environment or point OASIS_PYTHON_BIN to backend/.venv311.";
  }
  if (lowered.includes("insufficient_quota") || lowered.includes("quota")) {
    return "The model provider rejected the simulation because the API quota or billing limit was reached.";
  }
  if (lowered.includes("no longer available") || lowered.includes("not_found")) {
    return "The selected model is no longer available from the provider. Choose a current model and try again.";
  }
  if (lowered.includes("timed out") || lowered.includes("timeout_seconds=")) {
    return "The simulation timed out before it could finish. Try fewer agents or rounds, or use a faster model.";
  }
  if (lowered.includes("run_log=") || lowered.includes("traceback") || lowered.includes("process_exit_code")) {
    return "The simulation failed in the OASIS runtime. Check the backend run log for details.";
  }
  if (rawMessage.length > 180) {
    return "The simulation could not be completed. Check the backend logs and try again.";
  }
  return rawMessage;
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
function RoundSlider({ value, onChange, min = 1, max = 50 }: { value: number; onChange: (v: number) => void; min?: number; max?: number }) {
  // Fixed increments: 1, 5, 10, 15, ..., max
  const marks = useMemo(() => {
    const result = [min];
    const step = 5;
    for (let i = step; i <= max; i += step) {
      if (i !== min) result.push(i);
    }
    if (result[result.length - 1] !== max) result.push(max);
    return result;
  }, [min, max]);

  // Snap to nearest allowed mark
  const snapToMark = (v: number) => {
    let closest = marks[0];
    let closestDist = Math.abs(v - closest);
    for (const m of marks) {
      const dist = Math.abs(v - m);
      if (dist < closestDist) {
        closest = m;
        closestDist = dist;
      }
    }
    return closest;
  };

  const markIndex = marks.indexOf(value);
  const percentage = markIndex >= 0 ? (markIndex / (marks.length - 1)) * 100 : 0;

  // Color zone: green ≤60%, amber ≤80%, red >80%
  const getFillColor = (val: number) => {
    const ratio = (val - min) / (max - min);
    if (ratio <= 0.4) return 'hsl(142, 60%, 45%)';
    if (ratio <= 0.7) return 'hsl(38, 92%, 50%)';
    return 'hsl(0, 84%, 60%)';
  };
  const fillColor = getFillColor(value);
  const estimatedMins = Math.round(value * 0.1);

  return (
    <div className="relative w-full pt-2 pb-9">
      <div className="relative h-8">
        <div className="absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full transition-all duration-300 ease-out"
            style={{ width: `${percentage}%`, background: fillColor }}
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
                  value >= mark ? "shadow-lg" : "bg-muted-foreground/25 group-hover:bg-muted-foreground/40"
                } ${value === mark ? "scale-150" : ""}`}
                style={value >= mark ? { background: fillColor } : undefined}
              />
              <span
                className={`absolute top-8 text-xs font-mono transition-all duration-300 ${
                  value === mark ? "font-bold" : "text-muted-foreground/50 group-hover:text-muted-foreground/80"
                }`}
                style={value === mark ? { color: fillColor } : undefined}
              >
                {mark}
              </span>
            </button>
          ))}
        </div>
      </div>

      <input
        type="range"
        min={0}
        max={marks.length - 1}
        step={1}
        value={marks.indexOf(value) >= 0 ? marks.indexOf(value) : 0}
        onChange={(e) => onChange(marks[Number(e.target.value)])}
        className="absolute left-0 right-0 top-2 h-8 cursor-pointer opacity-0"
      />

      {value > 10 && (
        <p className="absolute bottom-0 right-0 text-[10px] font-mono text-muted-foreground">
          ~{estimatedMins} min est.
        </p>
      )}
    </div>
  );
}

export default function Simulation() {
  const {
    sessionId,
    modelProvider,
    useCase,
    knowledgeArtifact,
    populationArtifact,
    agents,
    simPosts,
    simulationRounds,
    simulationComplete,
    simulationState,
    simSelectedRound,
    simSortBy,
    setSimulationRounds,
    setSimulationComplete,
    setSimulationState,
    setSimPosts,
    setSimSelectedRound,
    setSimSortBy,
    simControversyBoostEnabled,
    setSimControversyBoostEnabled,
    completeStep,
    setCurrentStep,
  } = useApp();

  const [feedThreads, setFeedThreads] = useState<FeedThread[]>(() => simPosts.map((post) => simPostToFeedThread(post)));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selectedRound = simSelectedRound;
  const setSelectedRound = setSimSelectedRound;
  const sortBy = simSortBy;
  const setSortBy = setSimSortBy;
  const controversyBoostEnabled = simControversyBoostEnabled;
  const setControversyBoostEnabled = setSimControversyBoostEnabled;
  const [expandedReplies, setExpandedReplies] = useState<Record<string, boolean>>({});
  const streamRef = useRef<EventSource | null>(null);
  const feedRef = useRef<HTMLDivElement>(null);
  const feedSessionRef = useRef<string | null>(sessionId);
  const hydratedFeedRef = useRef(false);
  const hydratedStateSessionRef = useRef<string | null>(null);
  const controversyBoost = controversyBoostEnabled ? 0.5 : 0;

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
  const liveMode = isLiveBootMode();
  const metricCards = useMemo(() => metricConfigForUseCase(useCase, !liveMode), [liveMode, useCase]);
  const roundProgressLabel = useMemo(() => readRoundProgressLabel(simulationState), [simulationState]);

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

  useEffect(() => {
    if (!sessionId || feedSessionRef.current !== sessionId || feedThreads.length === 0) {
      return;
    }
    setSimPosts(
      feedThreads.map((thread) => toSimPost(thread, agents)),
    );
  }, [agents, feedThreads, sessionId, setSimPosts]);

  useEffect(() => {
    closeStream();
    feedSessionRef.current = sessionId;
    hydratedFeedRef.current = false;
    hydratedStateSessionRef.current = null;
    setExpandedReplies({});
    setSelectedRound("all");
    setSortBy("new");
    setControversyBoostEnabled(false);
    setLoading(false);
    setError(null);
    setFeedThreads([]);
  }, [closeStream, sessionId]);

  useEffect(() => {
    if (hydratedFeedRef.current) {
      return;
    }
    if (feedThreads.length === 0 && simPosts.length > 0) {
      setFeedThreads(simPosts.map((post) => simPostToFeedThread(post)));
      hydratedFeedRef.current = true;
    }
  }, [feedThreads.length, setFeedThreads, simPosts]);

  useEffect(() => {
    if (!isStaticDemoBootMode() || !sessionId) {
      return;
    }
    if (feedThreads.length > 0 || simPosts.length > 0) {
      return;
    }

    let cancelled = false;
    void getBundledDemoSimulationPosts()
      .then((posts) => {
        if (cancelled || posts.length === 0) {
          return;
        }
        setSimPosts(posts);
        setFeedThreads(posts.map((post) => simPostToFeedThread(post)));
        hydratedFeedRef.current = true;
      })
      .catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, [feedThreads.length, sessionId, setFeedThreads, setSimPosts, simPosts.length]);

  useEffect(() => {
    if (!sessionId) {
      hydratedStateSessionRef.current = null;
      return;
    }
    if (simulationState) {
      return;
    }
    if (hydratedStateSessionRef.current === sessionId) {
      return;
    }

    hydratedStateSessionRef.current = sessionId;
    let cancelled = false;

    void getSimulationState(sessionId)
      .then((state) => {
        if (cancelled) {
          return;
        }
        setSimulationState(state);
      })
      .catch((caughtError) => {
        if (cancelled) {
          return;
        }
        hydratedStateSessionRef.current = null;
        if (isLiveBootMode()) {
          setError(resolveSimulationError(caughtError));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [sessionId, simulationState]);

  useEffect(() => {
    if (!sessionId || !(running || loading)) {
      return;
    }
    const timer = window.setInterval(() => {
      void getSimulationMetrics(sessionId)
        .then((payload) => {
          if (!payload || typeof payload !== "object") {
            return;
          }
          setSimulationState((previous) => mergeSimulationMetricsState(previous, payload as Record<string, unknown>));
        })
        .catch((error) => {
          if (isLiveBootMode()) {
            setError(resolveSimulationError(error));
          }
        });
    }, 2000);
    return () => window.clearInterval(timer);
  }, [loading, running, sessionId]);

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
        const actorOccupation = _humanizeLabel(String(payload.actor_occupation ?? ""));
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
                      likes: Number(payload.likes ?? 0),
                      dislikes: Number(payload.dislikes ?? 0),
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

    if (eventType === "comment_reaction_added") {
      setFeedThreads((previous) =>
        previous.map((thread) => {
          if (!isSamePostId(thread.postId, payload.post_id)) return thread;
          const commentId = String(payload.comment_id ?? "");
          const reaction = String(payload.reaction ?? "");
          return {
            ...thread,
            comments: thread.comments.map((c) => {
              if (c.id !== commentId) return c;
              return {
                ...c,
                likes: c.likes + (reaction === "like" ? 1 : 0),
                dislikes: c.dislikes + (reaction === "dislike" ? 1 : 0),
              };
            }),
          };
        }),
      );
      return;
    }

    if (eventType === "run_completed") {
      setSimulationComplete(true);
    }

    if (eventType === "run_failed") {
      setError(resolveSimulationError(String(payload.error ?? "Simulation failed.")));
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
      "comment_reaction_added",
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
    setSimPosts([]);
    setExpandedReplies({});
    setSimulationComplete(false);
    hydratedStateSessionRef.current = null;
    setSimulationState(null);
    try {
      const state = await startSimulation(sessionId, {
        policy_summary: knowledgeArtifact.summary,
        rounds: simulationRounds,
        controversy_boost: controversyBoost,
      });
      setSimulationState(state);
      if (isLiveBootMode()) {
        openStream(sessionId);
      } else if (isStaticDemoBootMode()) {
        const posts = await getBundledDemoSimulationPosts();
        setSimPosts(posts);
        setFeedThreads(posts.map((post) => simPostToFeedThread(post)));
        setSimulationComplete(state.status === "completed");
      }
    } catch (caughtError) {
      setError(resolveSimulationError(caughtError));
    } finally {
      setLoading(false);
    }
  }, [closeStream, controversyBoost, knowledgeArtifact, openStream, sessionId, setSimulationComplete, simulationRounds]);

  const handleProceed = useCallback(() => {
    completeStep(3);
    setCurrentStep(4);
  }, [completeStep, setCurrentStep]);

  return (
    <TooltipProvider delayDuration={0}>
      <div className="flex h-full min-h-0 gap-6 overflow-hidden p-6">
      <div className="flex-1 flex flex-col gap-4 min-w-0">
        {/* Header - removed Generate Report button from here */}
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-page-title font-semibold text-foreground">Live Social Simulation</h2>
            <p className="text-sm text-muted-foreground">Real-time Reddit discourse from native OASIS, grounded in the MiroWorld knowledge graph.</p>
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
                    max={50} 
                  />
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto] items-center gap-3 text-xs">
                  <div className="flex flex-wrap items-center gap-2">
                    <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                    <span className="font-mono font-semibold text-foreground">
                      ~{formatSeconds(estimatedTime)}
                    </span>
                    <span className="text-border">|</span>
                    <span className="text-muted-foreground font-mono">{populationArtifact?.sample_count ?? 250} agents × {simulationRounds} rounds</span>
                  </div>
                  <div className="justify-self-start lg:justify-self-end font-mono text-primary/85 bg-primary/10 px-2 py-0.5 rounded border border-primary/20">
                    ~${(0.85 * simulationRounds).toFixed(2)} cost
                  </div>
                </div>
              </GlassCard>

              <GlassCard className="p-4 min-h-[168px] flex h-full flex-col gap-3">
                <div className="flex items-center gap-2">
                  <Flame className="w-4 h-4 text-[hsl(var(--data-red))] shrink-0" />
                  <h3 className="text-sm font-medium text-foreground">Controversy Boost</h3>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed flex-1">
                  Amplifies divisive content in the social feed, simulating how real platforms boost engagement through controversial posts.
                </p>
                <div className="flex items-center justify-between pt-1">
                  <span className="text-xs text-muted-foreground font-mono">
                    {controversyBoostEnabled ? 'On' : 'Off'}
                  </span>
                  <Switch
                    aria-label="Controversy Boost"
                    checked={controversyBoostEnabled}
                    onCheckedChange={setControversyBoostEnabled}
                  />
                </div>
              </GlassCard>
            </div>

            {/* Feed - takes remaining space */}
            <GlassCard className="p-0 min-h-0 flex flex-col overflow-hidden flex-1">
              <div className="p-4 border-b border-border bg-card/50">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <MessageSquare className="w-4 h-4 text-muted-foreground" />
                    <div>
                      <h3 className="text-sm font-semibold text-foreground">Topic Community</h3>
                      <p className="text-[11px] text-muted-foreground">Live discourse feed</p>
                    </div>
                  </div>
                  <div className="px-2 py-1 rounded-md bg-muted border border-border">
                    <span className="text-sm font-mono font-bold text-primary">{simulationState?.current_round ?? 0}</span>
                    <span className="text-xs text-muted-foreground">/{simulationRounds}</span>
                  </div>
                </div>
                {roundProgressLabel && (
                  <p className="mb-3 text-[11px] font-mono text-primary/80">{roundProgressLabel}</p>
                )}
                
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground uppercase tracking-wider">View:</span>
                    <select
                      value={selectedRound === "all" ? "all" : String(selectedRound)}
                      onChange={(e) => setSelectedRound(e.target.value === "all" ? "all" : Number(e.target.value))}
                      className="bg-input border border-border rounded-lg px-3 py-2 pr-8 text-xs text-foreground focus:outline-none focus:border-primary/30 appearance-none cursor-pointer min-w-[100px]"
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
                  
                  <div className="flex items-center gap-1 bg-muted rounded-lg p-1 border border-border">
                    <button
                      onClick={() => setSortBy("new")}
                      className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all flex items-center gap-1.5
                        ${sortBy === "new" 
                          ? 'bg-card text-foreground border border-border' 
                          : 'text-muted-foreground hover:text-foreground'
                        }`}
                    >
                      <Clock className="w-3 h-3" /> New
                    </button>
                    <button
                      onClick={() => setSortBy("popular")}
                      className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all flex items-center gap-1.5
                        ${sortBy === "popular" 
                          ? 'bg-card text-foreground border border-border' 
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
                    <GlassCard key={thread.id} className="p-4 bg-card/50 border border-border hover:border-muted-foreground/30 transition-all duration-200 group">
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
                        <div className="px-2 py-1 rounded-full text-[10px] font-medium bg-muted text-muted-foreground border border-border">
                          {thread.actorOccupation || "Agent"}
                        </div>
                      </div>
                      
                      <h4 className="text-sm font-semibold text-foreground mb-2 leading-tight">{thread.title}</h4>
                      <MarkdownContent className="text-body text-muted-foreground" clampLines={6}>{thread.content}</MarkdownContent>
                      
                      <div className="flex items-center gap-5 mt-4 text-xs font-mono text-muted-foreground">
                        <span className="text-[hsl(var(--data-green))]">▲ {thread.likes}</span>
                        <span className="text-[hsl(var(--data-red))]">▼ {thread.dislikes}</span>
                        <span className="flex items-center gap-1.5 text-muted-foreground">
                          <MessageSquare className="w-3.5 h-3.5" /> 
                          <span className="font-mono font-medium">{thread.comments.length}</span>
                          <span>comments</span>
                        </span>
                      </div>
                      
                      {thread.comments.length > 0 && (
                        <div className="mt-4 space-y-2.5 border-l-2 border-border pl-3">
                          {visibleComments.map((comment) => (
                            <div key={comment.id} className="text-body flex items-start gap-2">
                              <div className="w-5 h-5 rounded-full bg-white/5 flex items-center justify-center text-[9px] font-bold text-white/40 flex-shrink-0">
                                {comment.actorName.split(' ').map(n => n[0]).join('').slice(0, 1).toUpperCase()}
                              </div>
                              <div className="flex-1 min-w-0">
                                <span className={`font-medium text-[11px] ${tone.nameText}`}>{comment.actorName}</span>
                                <MarkdownContent className="text-xs text-muted-foreground ml-2">{comment.content}</MarkdownContent>
                                <span className="flex items-center gap-3 mt-1 text-[10px] font-mono text-muted-foreground">
                                  <span className="text-[hsl(var(--data-green))]">▲ {comment.likes}</span>
                                  <span className="text-[hsl(var(--data-red))]">▼ {comment.dislikes}</span>
                                </span>
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
          <div className="grid min-h-0 grid-rows-[minmax(136px,auto)_minmax(136px,auto)_1fr] gap-4 overflow-y-auto scrollbar-thin">
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

              {/* Phase progress strip */}
              <div className="mt-3 space-y-1.5">
                {[
                  {
                    label: "Setting up OASIS",
                    done: simulationState !== null,
                    active: !simulationState,
                  },
                  {
                    label: "Initial interview of all agents",
                    done: baselineStatus === "completed",
                    active: baselineStatus === "running",
                  },
                  {
                    label: `Round ${Math.max(1, simulationState?.current_round ?? 0)} of ${Math.max(1, simulationState?.planned_rounds ?? simulationRounds)}`,
                    done: completed,
                    active: running && (simulationState?.current_round ?? 0) > 0,
                  },
                  {
                    label: "Final interview of all agents",
                    done: finalStatus === "completed",
                    active: finalStatus === "running",
                  },
                ].map((phase, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <div className={`w-1.5 h-1.5 rounded-full shrink-0 transition-colors ${
                      phase.done
                        ? "bg-emerald-400"
                        : phase.active
                          ? "bg-primary animate-pulse"
                          : "bg-white/15"
                    }`} />
                    <span className={`text-[10px] font-mono transition-colors ${
                      phase.done
                        ? "text-emerald-400"
                        : phase.active
                          ? "text-foreground"
                          : "text-muted-foreground/50"
                    }`}>
                      {phase.label}
                    </span>
                  </div>
                ))}
              </div>

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
                <div className="p-3 rounded-lg bg-muted/40 border border-border">
                  <div className="text-xs text-muted-foreground mb-1">Posts</div>
                  <div className="text-2xl font-mono font-bold text-foreground">{counters.posts}</div>
                </div>
                <div className="p-3 rounded-lg bg-muted/40 border border-border">
                  <div className="text-xs text-muted-foreground mb-1">Comments</div>
                  <div className="text-2xl font-mono font-bold text-foreground">{counters.comments}</div>
                </div>
                <div className="p-3 rounded-lg bg-muted/40 border border-border">
                  <div className="text-xs text-muted-foreground mb-1">Reactions</div>
                  <div className="text-2xl font-mono font-bold text-foreground">{counters.reactions}</div>
                </div>
                <div className="p-3 rounded-lg bg-muted/40 border border-border">
                  <div className="text-xs text-muted-foreground mb-1">Authors</div>
                  <div className="text-2xl font-mono font-bold text-foreground">{counters.active_authors}</div>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-3 pt-1">
                {metricCards.map((card) => (
                  <Tooltip key={card.label}>
                    <TooltipTrigger asChild>
                      <div className="flex flex-col gap-1 px-3 py-2 bg-muted/40 border border-border rounded-lg cursor-help" title={card.description}>
                        <span className="text-[10px] text-muted-foreground uppercase tracking-wider">{card.label}</span>
                        <span className="text-xl font-mono font-bold text-success/90">
                          {formatMetricValue(readLatestMetric(simulationState, card.keys, card.fallback), card.kind)}
                        </span>
                      </div>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-[220px] text-xs leading-relaxed bg-popover text-popover-foreground border-border">
                      {card.description}
                    </TooltipContent>
                  </Tooltip>
                ))}
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
    </TooltipProvider>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles = {
    pending: "bg-muted text-muted-foreground border-border",
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
  return "bg-muted text-muted-foreground border-border";
}

function formatSeconds(value: number | null | undefined): string {
  const totalSeconds = Math.max(0, Math.round(Number(value ?? 0)));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}m ${String(seconds).padStart(2, "0")}s`;
}

function simPostToFeedThread(post: import("@/data/mockData").SimPost): FeedThread {
  return {
    id: post.id,
    postId: post.id,
    actorName: post.agentName,
    actorSubtitle: `${post.agentArea} · ${post.agentOccupation}`,
    actorOccupation: post.agentOccupation,
    title: post.title,
    content: post.content,
    roundNo: post.round,
    activityRounds: [post.round],
    likes: post.upvotes,
    dislikes: post.downvotes,
    comments: post.comments.map((comment, index) => ({
      id: comment.id || `${post.id}-comment-${index + 1}`,
      actorName: comment.agentName,
      content: comment.content,
      roundNo: post.round,
      likes: comment.upvotes ?? 0,
      dislikes: comment.downvotes ?? 0,
    })),
  };
}

type MetricKind = "percent" | "score";

type MetricCardConfig = {
  label: string;
  keys: string[];
  fallback: number | null;
  kind: MetricKind;
  description: string;
};

function metricConfigForUseCase(useCase: string, allowFallback: boolean): MetricCardConfig[] {
  const fallback = allowFallback ? (value: number) => value : () => null;
  const normalized = String(useCase || "").trim().toLowerCase();
  if (normalized === "ad-testing") {
    return [
      {
        label: "Estimated Conversion",
        keys: ["estimated_conversion", "conversion_rate"],
        fallback: fallback(42),
        kind: "percent",
        description: "Uses the latest conversion rate or estimated conversion metric from the current simulation checkpoint.",
      },
      {
        label: "Engagement Score",
        keys: ["engagement_score"],
        fallback: fallback(6.2),
        kind: "score",
        description: "Combines interaction depth and reaction intensity into a 10-point engagement score.",
      },
    ];
  }
  if (normalized === "pmf-discovery" || normalized === "product-market-fit" || normalized === "product-market-research") {
    return [
      {
        label: "Product Interest",
        keys: ["product_interest", "interest_rate"],
        fallback: fallback(55),
        kind: "percent",
        description: "Reflects the latest measured interest or interest-rate signal across the simulated audience.",
      },
      {
        label: "Target Fit / NPS",
        keys: ["target_fit_score", "nps_score"],
        fallback: fallback(6.6),
        kind: "score",
        description: "Summarizes target segment fit or net promoter score from the simulation checkpoint.",
      },
    ];
  }
  if (normalized === "customer-review" || normalized === "reviews") {
    return [
      {
        label: "Satisfaction",
        keys: ["satisfaction"],
        fallback: fallback(7.1),
        kind: "score",
        description: "Captures the latest satisfaction checkpoint reported by the simulation stream.",
      },
      {
        label: "Recommendation",
        keys: ["recommendation", "nps"],
        fallback: fallback(61),
        kind: "percent",
        description: "Uses the recommendation or NPS-style signal to show how likely the audience is to recommend.",
      },
    ];
  }
  return [
    {
      label: "Approval Rate",
      keys: ["approval_rate", "stage3b_approval_rate"],
      fallback: fallback(68),
      kind: "percent",
      description: "Reads the latest approval rate from the simulation metrics payload.",
    },
    {
      label: "Net Sentiment",
      keys: ["net_sentiment"],
      fallback: fallback(7.2),
      kind: "score",
      description: "Converts the latest net sentiment signal into the 10-point display used in the dashboard.",
    },
  ];
}

function readLatestMetric(simulationState: SimulationState | null, metricKeys: string[], fallback: number | null): number | null {
  const metrics = normalizeMetricsPayload(simulationState?.latest_metrics as Record<string, unknown> | undefined);
  for (const key of metricKeys) {
    const normalizedKey = String(key || "").trim();
    if (!normalizedKey) continue;
    const direct = Number(metrics[normalizedKey]);
    if (Number.isFinite(direct)) {
      // stage3b_approval_rate is a 0.0–1.0 fraction — scale to percentage
      if (normalizedKey === "stage3b_approval_rate" && direct <= 1.0) {
        return Math.round(direct * 100);
      }
      return direct;
    }
    const checkpoint = Number(metrics[`checkpoint_${normalizedKey}`]);
    if (Number.isFinite(checkpoint)) {
      return checkpoint;
    }
  }
  return fallback;
}

function formatMetricValue(value: number | null, kind: MetricKind): string {
  if (!Number.isFinite(value ?? NaN)) {
    return "—";
  }
  if (kind === "percent") {
    return `${Number(value).toFixed(1)}%`;
  }
  return `${Number(value).toFixed(1)}/10`;
}

function readRoundProgressLabel(simulationState: SimulationState | null): string {
  const metrics = normalizeMetricsPayload(simulationState?.latest_metrics as Record<string, unknown> | undefined);
  const candidate = metrics.round_progress_label;
  return typeof candidate === "string" ? candidate : "";
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

function toSimPost(thread: FeedThread, agents: { id: string; name: string; planningArea?: string }[]): SimPost {
  const matchedAgent = agents.find((agent) => agent.name === thread.actorName);
  return {
    id: String(thread.id),
    agentId: matchedAgent?.id ?? String(thread.postId),
    agentName: thread.actorName,
    agentOccupation: thread.actorOccupation ?? thread.actorSubtitle,
    agentArea: matchedAgent?.planningArea ?? "",
    title: thread.title,
    content: thread.content,
    upvotes: thread.likes,
    downvotes: thread.dislikes,
    commentCount: thread.comments.length,
    round: thread.roundNo,
    timestamp: `Round ${thread.roundNo}`,
    comments: thread.comments.map((comment) => ({
      id: String(comment.id),
      agentName: comment.actorName,
      agentOccupation: "",
      content: comment.content,
      upvotes: comment.likes,
      downvotes: comment.dislikes,
    })),
  };
}

function mergeSimulationMetricsState(
  previous: SimulationState | null,
  payload: Record<string, unknown>,
): SimulationState {
  const base: SimulationState = previous ?? {
    session_id: "",
    status: "running",
    event_count: 0,
    last_round: 0,
    counters: { posts: 0, comments: 0, reactions: 0, active_authors: 0 },
    checkpoint_status: {},
    top_threads: [],
    discussion_momentum: {},
    latest_metrics: {},
    recent_events: [],
  };
  const normalized = normalizeMetricsPayload(payload);
  return {
    ...base,
    counters: {
      posts: Number(normalized.posts ?? base.counters.posts ?? 0),
      comments: Number(normalized.comments ?? base.counters.comments ?? 0),
      reactions: Number(normalized.reactions ?? base.counters.reactions ?? 0),
      active_authors: Number(normalized.active_authors ?? base.counters.active_authors ?? 0),
    },
    latest_metrics: {
      ...(base.latest_metrics ?? {}),
      ...normalized,
    },
  };
}

function normalizeMetricsPayload(payload: Record<string, unknown> | undefined): Record<string, unknown> {
  if (!payload || typeof payload !== "object") {
    return {};
  }

  const normalized: Record<string, unknown> = {};
  const rawMetrics = payload.metrics;
  const metricSource =
    rawMetrics && typeof rawMetrics === "object"
      ? (rawMetrics as Record<string, unknown>)
      : payload;

  for (const [key, value] of Object.entries(metricSource)) {
    if (value && typeof value === "object" && "value" in (value as Record<string, unknown>)) {
      const parsed = Number((value as Record<string, unknown>).value);
      normalized[key] = Number.isFinite(parsed) ? parsed : (value as Record<string, unknown>).value;
      normalized[`${key}_meta`] = value;
      continue;
    }
    normalized[key] = value;
  }

  const roundProgressSource = payload.round_progress ?? metricSource.round_progress;
  if (roundProgressSource && typeof roundProgressSource === "object") {
    normalized.round_progress = roundProgressSource;
    const label = (roundProgressSource as Record<string, unknown>).label;
    if (typeof label === "string" && label.trim()) {
      normalized.round_progress_label = label;
    }
  }

  if (typeof payload.round_progress_label === "string" && payload.round_progress_label.trim()) {
    normalized.round_progress_label = payload.round_progress_label;
  }

  return normalized;
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
  const eventRound = Math.max(
    Number(payload.round_no ?? 0),
    Number(payload.round ?? 0),
  );
  const next: SimulationState = {
    ...base,
    event_count: base.event_count + 1,
    last_round: Math.max(base.last_round, Number.isFinite(eventRound) ? eventRound : 0, base.last_round ?? 0),
    current_round: Math.max(base.current_round ?? 0, Number.isFinite(eventRound) ? eventRound : 0, base.current_round ?? 0),
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

  if (eventType === "round_batch_flushed") {
    const round = Number(payload.round ?? payload.round_no ?? next.current_round ?? 0);
    const batch = Number(payload.batch ?? payload.batch_index ?? 0);
    const totalBatches = Number(payload.total_batches ?? payload.batch_count ?? 0);
    const percentageRaw = Number(payload.percentage ?? 0);
    const percentage = Number.isFinite(percentageRaw) && percentageRaw > 0
      ? percentageRaw
      : totalBatches > 0
        ? (batch / totalBatches) * 100
        : 0;
    const label = String(payload.label ?? `Round ${round} (${Math.round(percentage)}%)`);
    next.latest_metrics = {
      ...base.latest_metrics,
      round_progress: {
        round,
        batch,
        total_batches: totalBatches,
        percentage: Number(percentage.toFixed(1)),
        label,
      },
      round_progress_label: label,
    };
  }

  if (eventType === "metrics_updated") {
    const normalizedMetrics = normalizeMetricsPayload(payload);
    const rawCounters = payload.counters && typeof payload.counters === "object"
      ? (payload.counters as Record<string, unknown>)
      : {};
    next.counters = {
      posts: Number(rawCounters.posts ?? normalizedMetrics.posts ?? base.counters.posts),
      comments: Number(rawCounters.comments ?? normalizedMetrics.comments ?? base.counters.comments),
      reactions: Number(rawCounters.reactions ?? normalizedMetrics.reactions ?? base.counters.reactions),
      active_authors: Number(rawCounters.active_authors ?? normalizedMetrics.active_authors ?? base.counters.active_authors),
    };
    next.elapsed_seconds = Number(payload.elapsed_seconds ?? base.elapsed_seconds ?? 0);
    next.estimated_total_seconds = Number(payload.estimated_total_seconds ?? base.estimated_total_seconds ?? 0);
    next.estimated_remaining_seconds = Number(payload.estimated_remaining_seconds ?? base.estimated_remaining_seconds ?? 0);
    next.top_threads = Array.isArray(payload.top_threads) ? (payload.top_threads as Array<Record<string, unknown>>) : base.top_threads;
    next.discussion_momentum = (payload.discussion_momentum as Record<string, unknown>) ?? base.discussion_momentum;
    next.latest_metrics = {
      ...base.latest_metrics,
      ...normalizedMetrics,
    };
  }

  if (eventType === "run_completed") {
    next.status = "completed";
    next.elapsed_seconds = Number(payload.elapsed_seconds ?? next.elapsed_seconds ?? 0);
  } else if (eventType === "run_failed") {
    next.status = "failed";
  } else if (eventType === "run_started" || eventType === "checkpoint_started" || eventType === "round_started" || eventType === "metrics_updated" || eventType === "round_batch_flushed") {
    next.status = "running";
  } else {
    next.status = base.status ?? "running";
  }

  return next;
}
