import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowRight, Flame, Loader2, MessageSquare, Play, ThumbsDown, ThumbsUp, Clock, TrendingUp, Sparkles, Users, Zap } from "lucide-react";

import { GlassCard } from "@/components/GlassCard";
import { Button } from "@/components/ui/button";
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
const OCCUPATION_COLORS: Record<string, { bg: string; text: string; border: string; glow: string }> = {
  "Teacher": { bg: "bg-emerald-500/15", text: "text-emerald-400", border: "border-emerald-500/30", glow: "shadow-emerald-500/20" },
  "Professional": { bg: "bg-blue-500/15", text: "text-blue-400", border: "border-blue-500/30", glow: "shadow-blue-500/20" },
  "Manager": { bg: "bg-violet-500/15", text: "text-violet-400", border: "border-violet-500/30", glow: "shadow-violet-500/20" },
  "Engineer": { bg: "bg-cyan-500/15", text: "text-cyan-400", border: "border-cyan-500/30", glow: "shadow-cyan-500/20" },
  "Nurse": { bg: "bg-rose-500/15", text: "text-rose-400", border: "border-rose-500/30", glow: "shadow-rose-500/20" },
  "Clerical": { bg: "bg-amber-500/15", text: "text-amber-400", border: "border-amber-500/30", glow: "shadow-amber-500/20" },
  "Sales": { bg: "bg-orange-500/15", text: "text-orange-400", border: "border-orange-500/30", glow: "shadow-orange-500/20" },
  "Service": { bg: "bg-pink-500/15", text: "text-pink-400", border: "border-pink-500/30", glow: "shadow-pink-500/20" },
  "Retired": { bg: "bg-slate-500/15", text: "text-slate-400", border: "border-slate-500/30", glow: "shadow-slate-500/20" },
  "Student": { bg: "bg-indigo-500/15", text: "text-indigo-400", border: "border-indigo-500/30", glow: "shadow-indigo-500/20" },
  "Homemaker": { bg: "bg-teal-500/15", text: "text-teal-400", border: "border-teal-500/30", glow: "shadow-teal-500/20" },
  "Unemployed": { bg: "bg-gray-500/15", text: "text-gray-400", border: "border-gray-500/30", glow: "shadow-gray-500/20" },
  "Consultant": { bg: "bg-sky-500/15", text: "text-sky-400", border: "border-sky-500/30", glow: "shadow-sky-500/20" },
  "Analyst": { bg: "bg-lime-500/15", text: "text-lime-400", border: "border-lime-500/30", glow: "shadow-lime-500/20" },
  "default": { bg: "bg-primary/15", text: "text-primary", border: "border-primary/30", glow: "shadow-primary/20" },
};

function getOccupationColor(occupation?: string): { bg: string; text: string; border: string; glow: string } {
  if (!occupation) return OCCUPATION_COLORS["default"];
  const key = Object.keys(OCCUPATION_COLORS).find(k => 
    occupation.toLowerCase().includes(k.toLowerCase())
  );
  return OCCUPATION_COLORS[key || "default"];
}

type SortOption = "new" | "popular";

// Custom styled slider with marks
function RoundSlider({ value, onChange, min = 1, max = 8 }: { value: number; onChange: (v: number) => void; min?: number; max?: number }) {
  const marks = useMemo(() => Array.from({ length: max - min + 1 }, (_, i) => min + i), [min, max]);
  const percentage = ((value - min) / (max - min)) * 100;
  
  return (
    <div className="relative w-full py-6">
      {/* Track background */}
      <div className="absolute left-0 right-0 h-2 bg-white/5 rounded-full overflow-hidden top-1/2 -translate-y-1/2">
        {/* Filled track */}
        <div 
          className="h-full bg-gradient-to-r from-primary/60 via-primary to-primary/80 transition-all duration-300 ease-out"
          style={{ width: `${percentage}%` }}
        />
      </div>
      
      {/* Marks */}
      <div className="absolute left-0 right-0 top-1/2 -translate-y-1/2 flex justify-between items-center px-0">
        {marks.map((mark) => (
          <button
            key={mark}
            onClick={() => onChange(mark)}
            className={`relative w-8 h-8 -ml-4 rounded-full flex items-center justify-center transition-all duration-300 group
              ${value === mark 
                ? 'scale-110' 
                : 'hover:scale-105'
              }
            `}
          >
            {/* Mark dot */}
            <div className={`w-3 h-3 rounded-full transition-all duration-300 
              ${value >= mark 
                ? 'bg-primary shadow-lg shadow-primary/40' 
                : 'bg-white/20 group-hover:bg-white/40'
              }
              ${value === mark ? 'scale-150' : ''}
            `} />
            
            {/* Mark label - positioned below with more space */}
            <span className={`absolute top-full mt-3 text-xs font-mono transition-all duration-300
              ${value === mark 
                ? 'text-primary font-bold scale-110' 
                : 'text-white/30 group-hover:text-white/60'
              }
            `}>
              {mark}
            </span>
          </button>
        ))}
      </div>
      
      {/* Invisible range input for accessibility and drag */}
      <input
        type="range"
        min={min}
        max={max}
        step={1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="absolute left-0 right-0 h-8 top-1/2 -translate-y-1/2 opacity-0 cursor-pointer"
      />
    </div>
  );
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
  const [selectedRound, setSelectedRound] = useState<number | "all">("all");
  const [sortBy, setSortBy] = useState<SortOption>("new");
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
      threads = threads.filter(t => t.roundNo === selectedRound);
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
              className="border-success/30 text-success hover:bg-success/10"
            >
              <ArrowRight className="w-4 h-4" /> Generate Report
            </Button>
          )}
        </div>

        {/* Main Content: Number Picker + Feed + Stats */}
        <div className="grid grid-cols-1 xl:grid-cols-[1.4fr_0.6fr] gap-5 min-h-0 flex-1">
          {/* Left Column: Number Picker + Feed */}
          <div className="flex flex-col gap-4 min-h-0">
            {/* Number Picker - same width as feed */}
            <GlassCard className="p-5 shrink-0">
              <div className="flex items-center gap-6">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <Sparkles className="w-4 h-4 text-primary/70" />
                    <h3 className="text-sm font-medium text-foreground">Simulation Rounds</h3>
                  </div>
                  
                  <RoundSlider 
                    value={simulationRounds} 
                    onChange={setSimulationRounds} 
                    min={1} 
                    max={8} 
                  />
                  
                  <div className="flex items-center gap-2 mt-6 text-xs text-muted-foreground font-mono">
                    <Clock className="w-3 h-3" />
                    <span>~{formatSeconds(estimatedTime)}</span>
                    <span className="text-white/20">|</span>
                    <span>{populationArtifact?.sample_count ?? 250} agents × {simulationRounds} rounds</span>
                  </div>
                </div>
                
                <div className="flex flex-col items-center justify-center px-6 border-l border-white/10">
                  <div className="text-4xl font-mono font-bold text-foreground">{simulationRounds}</div>
                  <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Rounds</div>
                </div>
              </div>
            </GlassCard>

            {/* Feed - takes remaining space */}
            <GlassCard className="p-0 min-h-0 flex flex-col overflow-hidden flex-1">
              <div className="p-4 border-b border-white/5 bg-white/[0.02]">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <MessageSquare className="w-4 h-4 text-violet-400" />
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
                  const colors = getOccupationColor(thread.actorOccupation);
                  return (
                    <GlassCard key={thread.id} className="p-4 bg-white/[0.02] border border-white/10 hover:bg-white/[0.04] transition-all duration-200 group">
                      <div className="flex items-start justify-between gap-4 mb-3">
                        <div className="flex items-center gap-3">
                          <div className={`w-10 h-10 rounded-full ${colors.bg} flex items-center justify-center text-sm font-bold ${colors.text} border ${colors.border}`}>
                            {thread.actorName.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()}
                          </div>
                          <div>
                            <div className={`text-sm font-semibold ${colors.text}`}>{thread.actorName}</div>
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
                      <p className="text-xs text-muted-foreground leading-relaxed line-clamp-3">{thread.content}</p>
                      
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
                          {thread.comments.slice(0, 3).map((comment) => (
                            <div key={comment.id} className="text-xs flex items-start gap-2">
                              <div className="w-5 h-5 rounded-full bg-white/5 flex items-center justify-center text-[9px] font-bold text-white/40 flex-shrink-0">
                                {comment.actorName.split(' ').map(n => n[0]).join('').slice(0, 1).toUpperCase()}
                              </div>
                              <div className="flex-1 min-w-0">
                                <span className="font-medium text-foreground/80 text-[11px]">{comment.actorName}</span>
                                <span className="text-muted-foreground ml-2 line-clamp-2">{comment.content}</span>
                              </div>
                            </div>
                          ))}
                          {thread.comments.length > 3 && (
                            <div className="text-[10px] text-muted-foreground pl-7">
                              +{thread.comments.length - 3} more replies
                            </div>
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
          <div className="space-y-4 flex flex-col">
            {/* Hottest Thread */}
            <GlassCard className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <Flame className="w-4 h-4 text-orange-400" />
                <h4 className="text-xs uppercase tracking-wider text-orange-400 font-semibold">Hottest Thread</h4>
              </div>
              
              {hottestThread?.title ? (
                <div>
                  <h3 className="text-base font-semibold text-foreground leading-tight mb-3 line-clamp-2">
                    {String(hottestThread.title)}
                  </h3>
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-orange-500/10 border border-orange-500/20 w-fit">
                    <TrendingUp className="w-3.5 h-3.5 text-orange-400" />
                    <span className="text-sm font-mono font-bold text-orange-400">
                      {Number(hottestThread.engagement ?? 0).toLocaleString()}
                    </span>
                    <span className="text-xs text-orange-400/70">engagement</span>
                  </div>
                </div>
              ) : (
                <div className="py-6 text-center">
                  <p className="text-sm text-muted-foreground">Awaiting activity...</p>
                </div>
              )}
            </GlassCard>

            {/* Time Elapsed - Big */}
            <GlassCard className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <Clock className="w-4 h-4 text-cyan-400" />
                <h4 className="text-xs uppercase tracking-wider text-cyan-400 font-semibold">Time Elapsed</h4>
              </div>
              
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-mono font-bold text-foreground">
                  {formatSeconds(simulationState?.elapsed_seconds ?? 0)}
                </span>
              </div>
              
              {running && (
                <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  <span>Simulation in progress...</span>
                </div>
              )}
              
              {completed && (
                <div className="mt-3 flex items-center gap-2 text-xs text-emerald-400">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  <span>Completed</span>
                </div>
              )}
            </GlassCard>

            {/* Expanded Metrics */}
            <GlassCard className="p-4 flex-1">
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
              
              <div className="flex items-center justify-between py-3 border-t border-white/5">
                <span className="text-sm text-muted-foreground">Dominant Stance</span>
                <span className="text-sm font-medium text-primary capitalize">
                  {String(simulationState?.discussion_momentum?.dominant_stance ?? "mixed")}
                </span>
              </div>
              
              <div className="mt-4 pt-4 border-t border-white/5 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Baseline Checkpoint</span>
                  <StatusBadge status={baselineStatus} />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Final Checkpoint</span>
                  <StatusBadge status={finalStatus} />
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
