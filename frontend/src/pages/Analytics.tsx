import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity, Flame, GitBranch, Megaphone, Users2 } from "lucide-react";

import { useApp } from "@/contexts/AppContext";
import { generateAgents, type Agent } from "@/data/mockData";
import {
  getAnalyticsAgentStances,
  getAnalyticsCascades,
  getAnalyticsInfluence,
  getAnalyticsOpinionFlow,
  getAnalyticsPolarization,
  isLiveBootMode,
} from "@/lib/console-api";
import { MetricSelector } from "@/components/MetricSelector";

type PolarizationPoint = {
  round: string;
  index: number;
  severity: "low" | "moderate" | "high";
};

type Stance = "supporter" | "neutral" | "dissenter";
type DemographicDimension = "industry" | "occupation" | "planningArea" | "incomeBracket" | "ageBucket" | "gender";

type OpinionFlowData = {
  initial: Record<Stance, number>;
  final: Record<Stance, number>;
  flows: Array<{ from: Stance; to: Stance; count: number }>;
};

type Leader = {
  name: string;
  stance: Stance | "mixed";
  influence: number;
  topView: string;
  topPost: string;
};

type ViralComment = {
  author: string;
  stance: Stance | "mixed";
  content: string;
  likes: number;
  dislikes: number;
};

type ViralPost = {
  author: string;
  stance: Stance | "mixed";
  title: string;
  content: string;
  likes: number;
  dislikes: number;
  comments: ViralComment[];
};

type DemographicGroup = {
  name: string;
  agents: Agent[];
  supporters: number;
  neutral: number;
  dissenters: number;
};

type AnalyticsSnapshot = {
  polarizationData: PolarizationPoint[];
  opinionFlowData: OpinionFlowData;
  leaderData: Leader[];
  viralPostData: ViralPost[];
};

const POLARIZATION_DATA: PolarizationPoint[] = [
  { round: "R1", index: 0.12, severity: "low" },
  { round: "R2", index: 0.28, severity: "moderate" },
  { round: "R3", index: 0.45, severity: "moderate" },
  { round: "R4", index: 0.67, severity: "high" },
  { round: "R5", index: 0.82, severity: "high" },
];

const OPINION_FLOW: OpinionFlowData = {
  initial: { supporter: 162, neutral: 38, dissenter: 50 },
  final: { supporter: 85, neutral: 12, dissenter: 153 },
  flows: [
    { from: "supporter", to: "supporter", count: 80 },
    { from: "supporter", to: "dissenter", count: 72 },
    { from: "supporter", to: "neutral", count: 10 },
    { from: "neutral", to: "dissenter", count: 30 },
    { from: "neutral", to: "supporter", count: 5 },
    { from: "neutral", to: "neutral", count: 3 },
    { from: "dissenter", to: "dissenter", count: 48 },
    { from: "dissenter", to: "supporter", count: 2 },
  ],
};

const KEY_OPINION_LEADERS: Leader[] = [
  {
    name: "Raj Kumar",
    stance: "dissenter",
    influence: 0.92,
    topView: "Argues the policy disproportionately burdens low-income households and renters.",
    topPost: "Innovation hubs only benefit top earners and push out long-time residents.",
  },
  {
    name: "Siti Ibrahim",
    stance: "dissenter",
    influence: 0.86,
    topView: "Frames the policy as structurally unfair for working families with unstable income.",
    topPost: "If costs keep rising this way, ordinary families cannot keep up.",
  },
  {
    name: "Priya Nair",
    stance: "dissenter",
    influence: 0.79,
    topView: "Highlights service-sector stress and fear of being excluded from policy benefits.",
    topPost: "Support programs are not reaching the people who need them most.",
  },
  {
    name: "Janet Lee",
    stance: "supporter",
    influence: 0.78,
    topView: "Defends policy intent but asks for stronger safeguards and clearer rollout communication.",
    topPost: "The policy can work if implementation is transparent and phased carefully.",
  },
  {
    name: "Ahmad Hassan",
    stance: "supporter",
    influence: 0.73,
    topView: "Supports the direction while pushing for targeted adjustments for vulnerable groups.",
    topPost: "Keep the framework, but improve support for transition costs.",
  },
  {
    name: "Kavitha Pillai",
    stance: "supporter",
    influence: 0.69,
    topView: "Emphasizes long-term macro gains while acknowledging short-term friction.",
    topPost: "Short-term pain can be manageable if the compensations are concrete.",
  },
  {
    name: "Wei Ming Tan",
    stance: "mixed",
    influence: 0.65,
    topView: "Bridges camps by comparing tradeoffs and asking for data-based revisions.",
    topPost: "Can we publish clearer impact metrics by district before full rollout?",
  },
];

const VIRAL_POSTS: ViralPost[] = [
  {
    author: "Raj Kumar",
    stance: "dissenter",
    title: "Innovation hubs only help top earners",
    content:
      "The latest policy package is framed as future-ready, but on the ground it is accelerating rent pressure and squeezing families already near the edge.",
    likes: 142,
    dislikes: 28,
    comments: [
      {
        author: "Tan Li Wei",
        stance: "dissenter",
        content: "I see this in schools too. Families are moving further away and commute stress is rising.",
        likes: 86,
        dislikes: 5,
      },
      {
        author: "Mary Santos",
        stance: "mixed",
        content: "I supported this initially, but this argument changed my view after comparing household costs.",
        likes: 41,
        dislikes: 3,
      },
      {
        author: "Ahmad Y.",
        stance: "dissenter",
        content: "As a driver, this already affects where I can afford to live and work.",
        likes: 67,
        dislikes: 8,
      },
    ],
  },
  {
    author: "Janet Lee",
    stance: "supporter",
    title: "Policy direction is right, but rollout needs guardrails",
    content:
      "I still think the policy can work, but only if there are stronger short-term protections for lower-income households during transition.",
    likes: 120,
    dislikes: 19,
    comments: [
      {
        author: "Kelvin Ho",
        stance: "supporter",
        content: "Agree. Keep the direction, but announce support details upfront.",
        likes: 58,
        dislikes: 6,
      },
      {
        author: "Nora Lim",
        stance: "mixed",
        content: "I am neutral for now. The safeguards decide whether this is fair in practice.",
        likes: 44,
        dislikes: 7,
      },
      {
        author: "Siti Ibrahim",
        stance: "dissenter",
        content: "Without hard protections, this still lands hardest on lower-income workers.",
        likes: 52,
        dislikes: 12,
      },
    ],
  },
  {
    author: "Wei Ming Tan",
    stance: "mixed",
    title: "Show district-level impact data before expansion",
    content:
      "This debate is too abstract. Publish district-level impact metrics and revise the policy where downside risk is highest before scaling nationally.",
    likes: 109,
    dislikes: 11,
    comments: [
      {
        author: "Priya Nair",
        stance: "dissenter",
        content: "This would make accountability real. Right now people feel unheard.",
        likes: 61,
        dislikes: 4,
      },
      {
        author: "Ahmad Hassan",
        stance: "supporter",
        content: "Good compromise: data first, then calibrated rollout by district.",
        likes: 57,
        dislikes: 5,
      },
      {
        author: "Jia Wen",
        stance: "mixed",
        content: "Data transparency might reduce polarization more than any speech campaign.",
        likes: 48,
        dislikes: 3,
      },
    ],
  },
];

const STANCE_ORDER: Stance[] = ["supporter", "neutral", "dissenter"];

function analyticsCacheKey(sessionId: string): string {
  return `mckainsey-analytics-${sessionId}`;
}

function loadAnalyticsSnapshot(sessionId: string): AnalyticsSnapshot | null {
  if (!sessionId || typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.sessionStorage.getItem(analyticsCacheKey(sessionId));
    if (!raw) {
      return null;
    }
    return JSON.parse(raw) as AnalyticsSnapshot;
  } catch {
    return null;
  }
}

function saveAnalyticsSnapshot(sessionId: string, snapshot: AnalyticsSnapshot): void {
  if (!sessionId || typeof window === "undefined") {
    return;
  }
  try {
    window.sessionStorage.setItem(analyticsCacheKey(sessionId), JSON.stringify(snapshot));
  } catch {
    // Ignore browser storage write failures.
  }
}

export default function Analytics() {
  const { agents, useCase, country, simulationRounds, sessionId } = useApp();
  const liveMode = isLiveBootMode();
  const agentNamesById = useMemo<Map<string, string>>(
    () => new Map(agents.map((agent) => [agent.id, agent.name])),
    [agents],
  );

  const [dimension, setDimension] = useState<DemographicDimension>(() => defaultDimensionForUseCase(useCase));
  const [selectedMetric, setSelectedMetric] = useState<string | null>(null);
  const [polarizationData, setPolarizationData] = useState<PolarizationPoint[]>(() => (liveMode ? [] : POLARIZATION_DATA));
  const [opinionFlowData, setOpinionFlowData] = useState<OpinionFlowData>(() => (liveMode ? { initial: { supporter: 0, neutral: 0, dissenter: 0 }, final: { supporter: 0, neutral: 0, dissenter: 0 }, flows: [] } : OPINION_FLOW));
  const [leaderData, setLeaderData] = useState<Leader[]>(() => (liveMode ? [] : KEY_OPINION_LEADERS));
  const [viralPostData, setViralPostData] = useState<ViralPost[]>(() => (liveMode ? [] : VIRAL_POSTS));
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsError, setAnalyticsError] = useState<string | null>(null);
  const [agentStanceOverrides, setAgentStanceOverrides] = useState<Map<string, string>>(new Map());

  useEffect(() => {
    if (!liveMode || !sessionId) {
      return;
    }
    const cached = loadAnalyticsSnapshot(sessionId);
    if (!cached) {
      return;
    }
    if (polarizationData.length === 0 && cached.polarizationData.length > 0) {
      setPolarizationData(cached.polarizationData);
    }
    if (opinionFlowData.flows.length === 0 && cached.opinionFlowData.flows.length > 0) {
      setOpinionFlowData(cached.opinionFlowData);
    }
    if (leaderData.length === 0 && cached.leaderData.length > 0) {
      setLeaderData(cached.leaderData);
    }
    if (viralPostData.length === 0 && cached.viralPostData.length > 0) {
      setViralPostData(cached.viralPostData);
    }
  }, [leaderData.length, liveMode, opinionFlowData.flows.length, polarizationData.length, sessionId, viralPostData.length]);

  useEffect(() => {
    if (!liveMode || !sessionId) {
      return;
    }
    const hasAnyData =
      polarizationData.length > 0 ||
      opinionFlowData.flows.length > 0 ||
      leaderData.length > 0 ||
      viralPostData.length > 0;
    if (!hasAnyData) {
      return;
    }
    saveAnalyticsSnapshot(sessionId, {
      polarizationData,
      opinionFlowData,
      leaderData,
      viralPostData,
    });
  }, [leaderData, liveMode, opinionFlowData, polarizationData, sessionId, viralPostData]);

  useEffect(() => {
    setDimension(defaultDimensionForUseCase(useCase));
  }, [useCase]);

  useEffect(() => {
    const isLive = isLiveBootMode();
    if (!sessionId) {
      if (isLive) {
        setPolarizationData([]);
        setOpinionFlowData({ initial: { supporter: 0, neutral: 0, dissenter: 0 }, final: { supporter: 0, neutral: 0, dissenter: 0 }, flows: [] });
        setLeaderData([]);
        setViralPostData([]);
        setAnalyticsError("Complete Screen 3 before loading live analytics.");
      } else {
        setPolarizationData(POLARIZATION_DATA);
        setOpinionFlowData(OPINION_FLOW);
        setLeaderData(KEY_OPINION_LEADERS);
        setViralPostData(VIRAL_POSTS);
        setAnalyticsError(null);
      }
      setAnalyticsLoading(false);
      return;
    }

    let active = true;
    setAnalyticsLoading(true);
    setAnalyticsError(null);

    void Promise.allSettled([
      getAnalyticsPolarization(sessionId, selectedMetric ?? undefined),
      getAnalyticsOpinionFlow(sessionId, selectedMetric ?? undefined),
      getAnalyticsInfluence(sessionId),
      getAnalyticsCascades(sessionId),
    ]).then(([polarization, flow, influence, cascades]) => {
      if (!active) return;

      const normalizedPolarization = polarization.status === "fulfilled"
        ? normalizePolarizationPayload(polarization.value)
        : null;
      const normalizedFlow = flow.status === "fulfilled"
        ? normalizeOpinionFlowPayload(flow.value)
        : null;
      const normalizedLeaders = influence.status === "fulfilled"
        ? normalizeLeadersPayload(influence.value, agentNamesById)
        : null;
      const normalizedCascades = cascades.status === "fulfilled"
        ? normalizeCascadesPayload(cascades.value, agentNamesById)
        : null;

      if (isLive) {
        const hasPolarization = (normalizedPolarization?.length ?? 0) > 0;
        const hasFlow = Boolean(normalizedFlow && normalizedFlow.flows.length > 0);
        const hasLeaders = (normalizedLeaders?.length ?? 0) > 0;
        const hasCascades = (normalizedCascades?.length ?? 0) > 0;

        if (hasPolarization) {
          setPolarizationData(normalizedPolarization!);
        }
        if (hasFlow) {
          setOpinionFlowData(normalizedFlow!);
        }
        if (hasLeaders) {
          setLeaderData(normalizedLeaders!);
        }
        if (hasCascades) {
          setViralPostData(normalizedCascades!);
        }

        const anyFailure =
          [polarization, flow, influence, cascades].some((entry) => entry.status === "rejected") ||
          !hasPolarization ||
          !hasFlow ||
          !hasLeaders ||
          !hasCascades;
        if (anyFailure) {
          const missing: string[] = [];
          if (!hasPolarization) missing.push("polarization");
          if (!hasFlow) missing.push("opinion flow");
          if (!hasLeaders) missing.push("influence leaders");
          if (!hasCascades) missing.push("viral cascades");
          const suffix = missing.length > 0 ? ` Missing: ${missing.join(", ")}.` : "";
          setAnalyticsError(`Live analytics returned incomplete data.${suffix}`);
        } else {
          setAnalyticsError(null);
        }
      } else {
        setPolarizationData(normalizedPolarization ?? POLARIZATION_DATA);
        setOpinionFlowData(normalizedFlow ?? OPINION_FLOW);
        setLeaderData(normalizedLeaders ?? KEY_OPINION_LEADERS);
        setViralPostData(normalizedCascades ?? VIRAL_POSTS);

        const anyFailure = [polarization, flow, influence, cascades].some((entry) => entry.status === "rejected");
        setAnalyticsError(anyFailure ? "Showing demo analytics data while live analytics is unavailable." : null);
      }
      setAnalyticsLoading(false);
    }).catch(() => {
      if (!active) return;
      if (isLive) {
        setAnalyticsError("Live analytics request failed. Showing the latest available analytics snapshot.");
      } else {
        setPolarizationData(POLARIZATION_DATA);
        setOpinionFlowData(OPINION_FLOW);
        setLeaderData(KEY_OPINION_LEADERS);
        setViralPostData(VIRAL_POSTS);
        setAnalyticsError("Showing demo analytics data while live analytics is unavailable.");
      }
      setAnalyticsLoading(false);
    });

    return () => {
      active = false;
    };
  }, [agentNamesById, sessionId, selectedMetric]);

  useEffect(() => {
    if (!sessionId || !selectedMetric) {
      setAgentStanceOverrides(new Map());
      return;
    }
    getAnalyticsAgentStances(sessionId, selectedMetric).then((data: any) => {
      const overrides = new Map<string, string>();
      for (const item of (data.stances || [])) {
        const sentiment = item.score >= 7 ? "positive" : item.score < 5 ? "negative" : "neutral";
        overrides.set(item.agent_id, sentiment);
      }
      setAgentStanceOverrides(overrides);
    }).catch(() => setAgentStanceOverrides(new Map()));
  }, [sessionId, selectedMetric]);

  const sourceAgents = useMemo<Agent[]>(() => {
    if (agents.length > 0) return agents;
    if (liveMode) return [];
    if (sessionId) return [];
    return generateAgents(220);
  }, [agents, liveMode, sessionId]);

  const demographicGroups = useMemo(() => {
    const grouped = new Map<string, Agent[]>();

    sourceAgents.forEach((agent: Agent) => {
      const key = resolveDemographicKey(agent, dimension);
      if (!grouped.has(key)) {
        grouped.set(key, []);
      }
      grouped.get(key)?.push(agent);
    });

    const groups = Array.from(grouped.entries())
      .sort((left, right) => right[1].length - left[1].length)
      .map(([name, agentsInGroup]) => {
        const supporters = agentsInGroup.filter((agent) => {
          const eff = agentStanceOverrides.get(agent.id) ?? agent.sentiment;
          return eff === "positive";
        }).length;
        const dissenters = agentsInGroup.filter((agent) => {
          const eff = agentStanceOverrides.get(agent.id) ?? agent.sentiment;
          return eff === "negative";
        }).length;
        const neutral = agentsInGroup.length - supporters - dissenters;

        return {
          name,
          agents: agentsInGroup,
          supporters,
          neutral,
          dissenters,
        } satisfies DemographicGroup;
      });

    const topGroups = groups.slice(0, 10);
    const overflow = groups.slice(10);

    if (overflow.length === 0) return topGroups;

    const overflowAgents = overflow.flatMap((group) => group.agents);
    const supporters = overflowAgents.filter((agent) => {
      const eff = agentStanceOverrides.get(agent.id) ?? agent.sentiment;
      return eff === "positive";
    }).length;
    const dissenters = overflowAgents.filter((agent) => {
      const eff = agentStanceOverrides.get(agent.id) ?? agent.sentiment;
      return eff === "negative";
    }).length;

    return [
      ...topGroups,
      {
        name: "Other",
        agents: overflowAgents,
        supporters,
        neutral: overflowAgents.length - supporters - dissenters,
        dissenters,
      },
    ];
  }, [dimension, sourceAgents, agentStanceOverrides]);

  const dimensionOptions = useMemo(() => {
    if (useCase === "public-policy-testing" || useCase === "policy-review") {
      return [
        { key: "industry", label: "Industry" },
        { key: "planningArea", label: "Planning Area" },
        { key: "incomeBracket", label: "Income" },
        { key: "ageBucket", label: "Age" },
        { key: "occupation", label: "Occupation" },
        { key: "gender", label: "Gender" },
      ] as Array<{ key: DemographicDimension; label: string }>;
    }

    if (useCase === "campaign-content-testing" || useCase === "ad-testing") {
      return [
        { key: "ageBucket", label: "Age" },
        { key: "incomeBracket", label: "Income" },
        { key: "occupation", label: "Occupation" },
        { key: "gender", label: "Gender" },
        { key: "planningArea", label: "Planning Area" },
      ] as Array<{ key: DemographicDimension; label: string }>;
    }

    return [
      { key: "occupation", label: "Occupation" },
      { key: "industry", label: "Industry" },
      { key: "incomeBracket", label: "Income" },
      { key: "ageBucket", label: "Age" },
      { key: "planningArea", label: "Planning Area" },
      { key: "gender", label: "Gender" },
    ] as Array<{ key: DemographicDimension; label: string }>;
  }, [useCase]);

  const demographicLoading = analyticsLoading && !!sessionId && agents.length === 0;
  const showDemographicEmpty = !demographicLoading && demographicGroups.length === 0;

  return (
    <div className="h-full overflow-y-auto scrollbar-thin bg-background">
      <div className="mx-auto flex w-full max-w-[1700px] flex-col gap-5 px-6 py-6">
        <header className="surface-card px-5 py-4">
          <h2 className="text-xl font-semibold tracking-tight text-white">Simulation Analytics</h2>
          <p className="mt-1 text-[11px] font-mono uppercase tracking-[0.15em] text-muted-foreground">
            {formatCountry(country)} · {formatUseCase(useCase)} · {sourceAgents.length} agents · {simulationRounds} rounds
          </p>
          <MetricSelector
            sessionId={sessionId}
            value={selectedMetric}
            onChange={setSelectedMetric}
            className="mt-3 flex items-center"
          />
        </header>

        {analyticsLoading && (
          <section className="surface-card px-5 py-3">
            <p className="text-xs font-mono uppercase tracking-[0.14em] text-muted-foreground">
              Loading analytics data...
            </p>
          </section>
        )}

        {analyticsError && (
          <section className="surface-card border border-amber-500/30 bg-amber-500/5 px-5 py-3">
            <p className="text-xs text-amber-200">{analyticsError}</p>
          </section>
        )}

        <section className="space-y-3">
          <div className="flex items-center gap-2 px-1">
            <Activity className="h-4 w-4 text-white/70" />
            <h3 className="text-xs font-mono uppercase tracking-[0.15em] text-white/80">Sentiment Dynamics</h3>
          </div>
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
            <PolarizationCard data={polarizationData} loading={analyticsLoading} />
            <OpinionFlowCard data={opinionFlowData} loading={analyticsLoading} />
          </div>
        </section>

        <section className="surface-card p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Users2 className="h-4 w-4 text-white/70" />
              <h3 className="text-sm font-semibold uppercase tracking-[0.11em] text-white">Demographic Sentiment Map</h3>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {dimensionOptions.map((option) => (
                <button
                  key={option.key}
                  type="button"
                  onClick={() => setDimension(option.key)}
                  className={`rounded border px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider transition-colors ${
                    dimension === option.key
                      ? "border-white/25 bg-white/10 text-white"
                      : "border-white/10 text-muted-foreground hover:border-white/20 hover:text-white"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          {demographicLoading ? (
            <div className="flex min-h-[180px] items-center justify-center rounded border border-white/10 bg-white/[0.02] text-xs font-mono uppercase tracking-[0.14em] text-muted-foreground">
              Loading demographic data...
            </div>
          ) : showDemographicEmpty ? (
            <div className="flex min-h-[180px] items-center justify-center rounded border border-white/10 bg-white/[0.02] text-xs font-mono uppercase tracking-[0.14em] text-muted-foreground">
              No demographic data yet.
            </div>
          ) : (
            <>
              <div className="mb-4 flex flex-wrap items-center gap-3 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-[hsl(var(--data-green))]" /> Supporter</span>
                <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-white/35" /> Neutral</span>
                <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-[hsl(var(--data-red))]" /> Dissenter</span>
              </div>

              <div className="flex flex-wrap gap-x-8 gap-y-10">
                {demographicGroups.map((group) => (
                  <div key={group.name} className="flex min-w-[220px] max-w-[340px] shrink-0 flex-col">
                    <div className="mb-3 flex w-full items-baseline justify-between border-b border-white/5 pb-1">
                      <h4 className="max-w-[260px] truncate text-sm font-semibold text-white/90" title={group.name}>{group.name}</h4>
                      <span className="ml-3 rounded bg-white/5 px-2 py-0.5 text-[11px] font-mono text-muted-foreground">{group.agents.length}</span>
                    </div>

                    <div className="mb-3 flex flex-wrap items-center gap-2 text-[10px] font-mono text-muted-foreground">
                      <span className="text-[hsl(var(--data-green))]">{group.supporters}</span>
                      <span className="text-white/35">neutral {group.neutral}</span>
                      <span className="text-[hsl(var(--data-red))]">{group.dissenters}</span>
                    </div>

                    <div className="flex max-w-[340px] flex-wrap gap-1">
                      {group.agents.map((agent) => {
                        const eff = (agentStanceOverrides.get(agent.id) ?? agent.sentiment) as Agent["sentiment"];
                        return (
                          <span
                            key={agent.id}
                            className="h-3.5 w-3.5 cursor-crosshair rounded-[2px] border border-black/20 transition-transform hover:z-10 hover:scale-125"
                            style={{ backgroundColor: sentimentColor(eff) }}
                            title={`${agent.name} · ${eff}`}
                          />
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </section>

        <section className="space-y-3">
          <div className="flex items-center gap-2 px-1">
            <Megaphone className="h-4 w-4 text-white/70" />
            <h3 className="text-xs font-mono uppercase tracking-[0.15em] text-white/80">KOL & Viral Posts</h3>
          </div>
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <KeyOpinionLeadersCard leaders={leaderData} loading={analyticsLoading} />
            <ViralPostsCard posts={viralPostData} loading={analyticsLoading} />
          </div>
        </section>
      </div>
    </div>
  );
}

type PolarizationDotProps = {
  cx?: number;
  cy?: number;
  payload?: PolarizationPoint;
};

function PolarizationDot({ cx, cy, payload }: PolarizationDotProps) {
  if (cx === undefined || cy === undefined || !payload) return null;
  return (
    <circle
      cx={cx}
      cy={cy}
      r={5}
      fill={severityColor(payload.severity)}
      stroke="hsl(0 0% 15%)"
      strokeWidth={2}
    />
  );
}

type PolarizationTooltipProps = {
  active?: boolean;
  label?: string;
  payload?: Array<{ value?: number; payload?: PolarizationPoint }>;
};

function PolarizationTooltip({ active, label, payload }: PolarizationTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const rawValue = Number(payload[0]?.value ?? 0);
  const severity = payload[0]?.payload?.severity ?? "moderate";

  return (
    <div className="min-w-[140px] rounded-md border border-white/15 bg-[#101010] px-3 py-2 text-xs text-white shadow-xl">
      <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-white/80">{label}</div>
      <div className="mt-1 flex items-center justify-between gap-3">
        <span className="text-sm font-semibold text-white">{toPercent(rawValue)}</span>
        <span className="text-[10px] font-mono uppercase" style={{ color: severityColor(severity) }}>
          {severity}
        </span>
      </div>
    </div>
  );
}

function PolarizationCard({ data, loading }: { data: PolarizationPoint[]; loading: boolean }) {
  if (loading) {
    return <LoadingAnalyticsCard title="Polarization Index" label="Loading polarization data..." />;
  }
  if (data.length === 0) {
    return <EmptyAnalyticsCard title="Polarization Index" label="No polarization data yet." />;
  }
  const safeData = data;
  const latest = safeData[safeData.length - 1];

  return (
    <section className="surface-card p-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-white/70" />
          <h3 className="text-sm font-semibold uppercase tracking-[0.11em] text-white">Polarization Index</h3>
        </div>
        <span
          className="rounded px-2 py-1 text-[10px] font-mono uppercase tracking-wider"
          style={{ color: severityColor(latest.severity), backgroundColor: `${severityColor(latest.severity)}20` }}
        >
          {latest.severity === "high" ? "Highly Polarized" : "Low Polarization"}
        </span>
      </div>

      <div className="h-[210px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={safeData} margin={{ top: 8, right: 16, left: -16, bottom: 4 }}>
            <CartesianGrid stroke="hsl(0 0% 16%)" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="round" tick={{ fill: "hsl(0 0% 72%)", fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis
              domain={[0, 1]}
              tickFormatter={(value) => `${Math.round(Number(value) * 100)}%`}
              tick={{ fill: "hsl(0 0% 55%)", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip content={<PolarizationTooltip />} cursor={{ stroke: "hsl(0 0% 34%)", strokeWidth: 1 }} />
            <Line
              type="monotone"
              dataKey="index"
              stroke="hsl(0 0% 75%)"
              strokeWidth={2}
              dot={<PolarizationDot />}
              activeDot={{ r: 6, stroke: "hsl(0 0% 36%)", strokeWidth: 2, fill: "hsl(0 0% 14%)" }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
        Higher values indicate the population is splitting into opposing camps rather than converging.
      </p>
    </section>
  );
}

function OpinionFlowCard({ data, loading }: { data: OpinionFlowData; loading: boolean }) {
  if (loading) {
    return <LoadingAnalyticsCard title="Opinion Flow" label="Loading opinion flow data..." />;
  }
  if (data.flows.length === 0) {
    return <EmptyAnalyticsCard title="Opinion Flow" label="No opinion flow data yet." />;
  }
  const safeData = data;
  const total = STANCE_ORDER.reduce((sum, stance) => sum + safeData.initial[stance], 0);
  const maxFlow = Math.max(...safeData.flows.map((flow) => flow.count), 1);
  const rowY: Record<Stance, number> = {
    supporter: 28,
    neutral: 86,
    dissenter: 144,
  };

  return (
    <section className="surface-card p-5">
      <div className="mb-4 flex items-center gap-2">
        <GitBranch className="h-4 w-4 text-white/70" />
        <h3 className="text-sm font-semibold uppercase tracking-[0.11em] text-white">Opinion Flow</h3>
      </div>

      <div className="grid grid-cols-[94px_minmax(0,1fr)_94px] gap-3">
        <FlowDistributionColumn title="Initial" values={safeData.initial} total={total} />

        <div className="h-[178px] rounded border border-white/10 bg-white/[0.02] p-2">
          <svg viewBox="0 0 220 172" className="h-full w-full" preserveAspectRatio="none">
            {safeData.flows.map((flow, index) => {
              const width = Math.max(2, (flow.count / maxFlow) * 14);
              return (
                <path
                  key={`${flow.from}-${flow.to}-${index}`}
                  d={`M 0 ${rowY[flow.from]} C 80 ${rowY[flow.from]}, 140 ${rowY[flow.to]}, 220 ${rowY[flow.to]}`}
                  fill="none"
                  stroke={stanceColor(flow.to)}
                  strokeOpacity={0.55}
                  strokeWidth={width}
                />
              );
            })}
          </svg>
        </div>

        <FlowDistributionColumn title="Final" values={safeData.final} total={total} />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3">
        {STANCE_ORDER.map((stance) => (
          <span key={stance} className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: stanceColor(stance) }} />
            {stance}
          </span>
        ))}
      </div>
    </section>
  );
}

function FlowDistributionColumn({
  title,
  values,
  total,
}: {
  title: string;
  values: Record<Stance, number>;
  total: number;
}) {
  return (
    <div className="rounded border border-white/10 bg-white/[0.02] p-2">
      <div className="mb-2 text-center text-[10px] font-mono uppercase tracking-[0.14em] text-white/70">{title}</div>
      <div className="space-y-1.5">
        {STANCE_ORDER.map((stance) => {
          const count = values[stance];
          const percent = count / total;
          const height = Math.max(26, Math.round(percent * 112));
          return (
            <div
              key={stance}
              className="flex items-center justify-center rounded-sm text-[10px] font-mono text-white"
              style={{
                height,
                backgroundColor: stanceColor(stance),
              }}
              title={`${stance}: ${count}`}
            >
              {toPercent(percent)}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function KeyOpinionLeadersCard({ leaders, loading }: { leaders: Leader[]; loading: boolean }) {
  const sections = useMemo(() => {
    const safeLeaders = leaders;
    const supporters = safeLeaders.filter((leader) => leader.stance === "supporter").slice(0, 3);
    const dissenters = safeLeaders.filter((leader) => leader.stance === "dissenter").slice(0, 3);

    if (supporters.length > 0 && dissenters.length > 0) {
      return [
        { title: "Top Supporters", leaders: supporters },
        { title: "Top Dissenters", leaders: dissenters },
      ];
    }

    return [
      {
        title: "Top Opinion Leaders",
        leaders: [...safeLeaders].sort((left, right) => right.influence - left.influence).slice(0, 3),
      },
    ];
  }, [leaders]);

  if (loading) {
    return <LoadingAnalyticsCard title="Key Opinion Leaders" label="Loading leader data..." />;
  }
  if (leaders.length === 0) {
    return <EmptyAnalyticsCard title="Key Opinion Leaders" label="No leader data yet." />;
  }

  return (
    <section className="surface-card p-5">
      <div className="mb-4 flex items-center gap-2">
        <Megaphone className="h-4 w-4 text-white/70" />
        <h3 className="text-sm font-semibold uppercase tracking-[0.11em] text-white">Key Opinion Leaders</h3>
      </div>

      <div className="space-y-4">
        {sections.map((section) => (
          <div key={section.title} className="space-y-2.5">
            <h4 className="text-[11px] font-mono uppercase tracking-[0.13em] text-white/75">{section.title}</h4>
            {section.leaders.map((leader) => (
              <article key={leader.name} className="rounded border border-white/10 bg-white/[0.02] p-3">
                <div className="mb-1.5 flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-white">{leader.name}</span>
                  <span
                    className="rounded px-2 py-0.5 text-[10px] font-mono"
                    style={{ color: stanceColor(leader.stance), backgroundColor: `${stanceColor(leader.stance)}1f` }}
                  >
                    {Math.round(leader.influence * 100)}%
                  </span>
                </div>
                <p className="text-xs leading-relaxed text-white/80">{leader.topView || leader.topPost || "No viewpoint summary available."}</p>
              </article>
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}

function ViralPostsCard({ posts, loading }: { posts: ViralPost[]; loading: boolean }) {
  if (loading) {
    return <LoadingAnalyticsCard title="Viral Posts" label="Loading viral post data..." />;
  }
  if (posts.length === 0) {
    return <EmptyAnalyticsCard title="Viral Posts" label="No viral post data yet." />;
  }
  const safePosts = posts;
  return (
    <section className="surface-card p-5">
      <div className="mb-4 flex items-center gap-2">
        <Flame className="h-4 w-4 text-white/70" />
        <h3 className="text-sm font-semibold uppercase tracking-[0.11em] text-white">Viral Posts</h3>
      </div>

      <div className="space-y-4">
        {safePosts.slice(0, 3).map((post, index) => (
          <article key={`${post.author}-${index}`} className="rounded border border-white/10 bg-white/[0.02] p-4">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-white">{post.author}</span>
                <span
                  className="rounded px-2 py-0.5 text-[10px] font-mono uppercase"
                  style={{ color: stanceColor(post.stance), backgroundColor: `${stanceColor(post.stance)}1f` }}
                >
                  {post.stance}
                </span>
              </div>
              <span className="text-[10px] font-mono uppercase tracking-[0.12em] text-white/55">Post #{index + 1}</span>
            </div>

            <h4 className="text-sm font-semibold leading-snug text-white">{post.title}</h4>
            <p className="mt-2 text-sm leading-relaxed text-white/80">{post.content}</p>

            <div className="mt-3 flex flex-wrap items-center gap-3 text-[11px] font-mono text-muted-foreground">
              <span className="text-[hsl(var(--data-green))]">▲ {post.likes}</span>
              <span className="text-[hsl(var(--data-red))]">▼ {post.dislikes}</span>
              <span className="text-white/70">💬 {post.comments.length} comments</span>
            </div>

            <div className="mt-3 space-y-2 border-l border-white/10 pl-3">
              {post.comments.slice(0, 3).map((comment, commentIndex) => (
                <div key={`${post.author}-comment-${commentIndex}`} className="rounded border border-white/10 bg-black/20 p-2.5">
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <span className="text-xs font-medium text-white/90">{comment.author}</span>
                    <span
                      className="rounded px-1.5 py-0.5 text-[9px] font-mono uppercase"
                      style={{ color: stanceColor(comment.stance), backgroundColor: `${stanceColor(comment.stance)}1f` }}
                    >
                      {comment.stance}
                    </span>
                  </div>
                  <p className="text-xs leading-relaxed text-white/80">{comment.content}</p>
                  <div className="mt-1.5 flex items-center gap-3 text-[10px] font-mono text-muted-foreground">
                    <span className="text-[hsl(var(--data-green))]">▲ {comment.likes}</span>
                    <span className="text-[hsl(var(--data-red))]">▼ {comment.dislikes}</span>
                  </div>
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function LoadingAnalyticsCard({ title, label }: { title: string; label: string }) {
  return (
    <section className="surface-card p-5">
      <div className="mb-4 flex items-center gap-2">
        <span className="h-4 w-4 rounded-full bg-white/10" />
        <h3 className="text-sm font-semibold uppercase tracking-[0.11em] text-white">{title}</h3>
      </div>
      <div className="flex min-h-[180px] items-center justify-center rounded border border-white/10 bg-white/[0.02] text-xs font-mono uppercase tracking-[0.14em] text-muted-foreground">
        {label}
      </div>
    </section>
  );
}

function EmptyAnalyticsCard({ title, label }: { title: string; label: string }) {
  return (
    <section className="surface-card p-5">
      <div className="mb-4 flex items-center gap-2">
        <span className="h-4 w-4 rounded-full bg-white/10" />
        <h3 className="text-sm font-semibold uppercase tracking-[0.11em] text-white">{title}</h3>
      </div>
      <div className="flex min-h-[180px] items-center justify-center rounded border border-white/10 bg-white/[0.02] text-xs text-muted-foreground">
        {label}
      </div>
    </section>
  );
}

function normalizePolarizationPayload(payload: Record<string, unknown>): PolarizationPoint[] | null {
  const candidate = payload.series ?? payload.points ?? payload.polarization ?? payload.rounds ?? payload.data;
  if (!Array.isArray(candidate)) {
    return null;
  }
  const normalized = candidate
    .map((row, index) => {
      if (!row || typeof row !== "object") return null;
      const data = row as Record<string, unknown>;
      const roundNo = Number(data.round_no ?? data.round ?? index + 1);
      const indexValue = Number(data.index ?? data.polarization_index ?? data.value ?? 0);
      if (!Number.isFinite(indexValue)) return null;
      const severityRaw = String(data.severity ?? "");
      let severity: PolarizationPoint["severity"] = "moderate";
      if (severityRaw === "low") severity = "low";
      if (severityRaw === "moderate") severity = "moderate";
      if (severityRaw === "high" || severityRaw === "critical") severity = "high";
      return {
        round: typeof data.round === "string" ? data.round : `R${Math.max(1, roundNo)}`,
        index: Math.max(0, Math.min(1, indexValue)),
        severity,
      } satisfies PolarizationPoint;
    })
    .filter((row): row is PolarizationPoint => Boolean(row));
  return normalized;
}

function normalizeOpinionFlowPayload(payload: Record<string, unknown>): OpinionFlowData | null {
  const initial = payload.initial;
  const final = payload.final;
  const flows = payload.flows;
  if (!initial || !final || !Array.isArray(flows)) {
    return null;
  }
  const initialRecord = initial as Record<string, unknown>;
  const finalRecord = final as Record<string, unknown>;
  const normalizedFlows = flows
    .map((row) => {
      if (!row || typeof row !== "object") return null;
      const entry = row as Record<string, unknown>;
      const from = String(entry.from ?? "").toLowerCase() as Stance;
      const to = String(entry.to ?? "").toLowerCase() as Stance;
      if (!STANCE_ORDER.includes(from) || !STANCE_ORDER.includes(to)) {
        return null;
      }
      return {
        from,
        to,
        count: Math.max(0, Number(entry.count ?? 0)),
      };
    })
    .filter((row): row is { from: Stance; to: Stance; count: number } => Boolean(row));

  return {
    initial: {
      supporter: Math.max(0, Number(initialRecord.supporter ?? 0)),
      neutral: Math.max(0, Number(initialRecord.neutral ?? 0)),
      dissenter: Math.max(0, Number(initialRecord.dissenter ?? 0)),
    },
    final: {
      supporter: Math.max(0, Number(finalRecord.supporter ?? 0)),
      neutral: Math.max(0, Number(finalRecord.neutral ?? 0)),
      dissenter: Math.max(0, Number(finalRecord.dissenter ?? 0)),
    },
    flows: normalizedFlows,
  };
}

function normalizeLeadersPayload(payload: Record<string, unknown>, agentNamesById: Map<string, string>): Leader[] | null {
  const candidates = payload.top_influencers ?? payload.leaders ?? payload.items;
  if (!Array.isArray(candidates)) {
    return null;
  }
  const normalized = candidates
    .map((row) => {
      if (!row || typeof row !== "object") return null;
      const entry = row as Record<string, unknown>;
      const name = resolveAnalyticsDisplayName(
        String(entry.name ?? entry.agent_name ?? entry.agent_id ?? ""),
        agentNamesById,
      );
      if (!name) return null;
      const stanceRaw = String(entry.stance ?? entry.segment ?? "mixed").toLowerCase();
      const stance: Leader["stance"] =
        stanceRaw === "supporter" || stanceRaw === "dissenter" || stanceRaw === "mixed"
          ? stanceRaw
          : "mixed";
      return {
        name,
        stance,
        influence: Number(entry.influence ?? entry.influence_score ?? entry.score ?? 0),
        topView: normalizeViewpointText(
          entry.summary ?? entry.viewpoint_summary ?? entry.top_view ?? entry.topView ?? entry.core_viewpoint ?? "",
        ),
        topPost: normalizeTopPostText(entry.top_post ?? entry.topPost ?? entry.example_post ?? ""),
      } satisfies Leader;
    })
    .filter((row): row is NonNullable<typeof row> => Boolean(row));
  return normalized as Leader[];
}

function resolveAnalyticsDisplayName(value: string, agentNamesById: Map<string, string>): string {
  const trimmed = String(value ?? "").trim();
  if (!trimmed) {
    return "";
  }
  return agentNamesById.get(trimmed) ?? trimmed;
}

function normalizeViewpointText(value: unknown): string {
  const text = normalizeTopPostText(value);
  if (!text) return "";
  if (/^analysis question\s*\d+/i.test(text)) {
    return text.replace(/^analysis question\s*\d+\s*[:\-]?\s*/i, "").trim();
  }
  return text;
}

function formatPlainText(value: unknown): string {
  const text = String(value ?? "");
  return text
    .replace(/^\s{0,3}#{1,6}\s+/gm, "")
    .replace(/^\s{0,3}[-*+]\s+/gm, "")
    .replace(/^\s{0,3}\d+\.\s+/gm, "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/__(.*?)__/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\[(.*?)\]\((.*?)\)/g, "$1")
    .replace(/\s+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function normalizeTopPostText(value: unknown): string {
  let raw: string;
  if (typeof value === "string") {
    raw = formatPlainText(value);
  } else if (!value || typeof value !== "object") {
    raw = formatPlainText(String(value ?? ""));
  } else {
    const entry = value as Record<string, unknown>;
    const candidates = [entry.content, entry.body, entry.title, entry.text, entry.summary, entry.quote];
    for (const candidate of candidates) {
      if (typeof candidate === "string" && candidate.trim()) {
        return stripPromptBoilerplate(formatPlainText(candidate));
      }
      if (candidate != null && typeof candidate !== "object") {
        return stripPromptBoilerplate(formatPlainText(String(candidate)));
      }
    }
    return "";
  }
  return stripPromptBoilerplate(raw);
}

// Strip "Community prompt: [question]. Policy brief: [...]" boilerplate from backend-generated post summaries.
function stripPromptBoilerplate(text: string): string {
  // Remove "Community prompt: <text>. Policy brief: " template prefix
  const policyBriefIdx = text.indexOf("Policy brief:");
  if (policyBriefIdx > 0) {
    const after = text.slice(policyBriefIdx + "Policy brief:".length).trim();
    if (after.length > 0) return after;
  }
  // Remove standalone "Community prompt: <text>" prefix leaving only the agent's actual response
  const communityPromptMatch = text.match(/^Community prompt:\s*.+?\.\s*/s);
  if (communityPromptMatch) {
    const after = text.slice(communityPromptMatch[0].length).trim();
    if (after.length > 0) return after;
  }
  return text;
}

function normalizeCascadesPayload(payload: Record<string, unknown>, agentNamesById: Map<string, string>): ViralPost[] | null {
  const candidates = payload.viral_posts ?? payload.cascades ?? payload.top_threads ?? payload.posts;
  if (!Array.isArray(candidates)) {
    return null;
  }
  const normalized = candidates
    .map((row) => {
      if (!row || typeof row !== "object") return null;
      const entry = row as Record<string, unknown>;
      const commentsCandidate = entry.comments;
      const comments = Array.isArray(commentsCandidate)
        ? commentsCandidate
            .map((comment) => {
              if (!comment || typeof comment !== "object") return null;
              const commentRow = comment as Record<string, unknown>;
              return {
                author: resolveAnalyticsDisplayName(
                  String(commentRow.author ?? commentRow.agent_name ?? "Agent"),
                  agentNamesById,
                ),
                stance: normalizeStance(commentRow.stance),
                content: formatPlainText(String(commentRow.content ?? commentRow.text ?? "")),
                likes: Math.max(0, Number(commentRow.likes ?? commentRow.upvotes ?? 0)),
                dislikes: Math.max(0, Number(commentRow.dislikes ?? commentRow.downvotes ?? 0)),
              } satisfies ViralComment;
            })
            .filter((comment): comment is ViralComment => Boolean(comment))
        : [];

      return {
        author: resolveAnalyticsDisplayName(
          String(entry.author ?? entry.author_name ?? "Agent"),
          agentNamesById,
        ),
        stance: normalizeStance(entry.stance),
        title: formatPlainText(String(entry.title ?? entry.headline ?? "Untitled thread")),
        content: formatPlainText(String(entry.content ?? entry.body ?? "")),
        likes: Math.max(0, Number(entry.likes ?? entry.upvotes ?? 0)),
        dislikes: Math.max(0, Number(entry.dislikes ?? entry.downvotes ?? 0)),
        comments,
      } satisfies ViralPost;
    })
    .filter((row): row is ViralPost => Boolean(row));
  return normalized;
}

function normalizeStance(raw: unknown): Stance | "mixed" {
  const stance = String(raw ?? "").toLowerCase();
  if (stance === "supporter" || stance === "dissenter" || stance === "neutral" || stance === "mixed") {
    return stance;
  }
  return "mixed";
}

function stanceColor(stance: Stance | "mixed"): string {
  if (stance === "supporter") return "hsl(var(--data-green))";
  if (stance === "dissenter") return "hsl(var(--data-red))";
  if (stance === "mixed") return "hsl(var(--data-blue))";
  return "hsl(var(--muted-foreground))";
}

function sentimentColor(sentiment: Agent["sentiment"]): string {
  if (sentiment === "positive") return "hsl(var(--data-green))";
  if (sentiment === "negative") return "hsl(var(--data-red))";
  return "hsl(0 0% 45%)";
}

function severityColor(severity: PolarizationPoint["severity"]): string {
  if (severity === "low") return "hsl(var(--data-green))";
  if (severity === "moderate") return "hsl(var(--data-amber))";
  return "hsl(var(--data-red))";
}

function toPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function resolveDemographicKey(agent: Agent, dimension: DemographicDimension): string {
  if (dimension === "planningArea") return agent.planningArea;
  if (dimension === "occupation") return agent.occupation;
  if (dimension === "incomeBracket") return agent.incomeBracket;
  if (dimension === "gender") return agent.gender;
  if (dimension === "ageBucket") {
    if (agent.age <= 24) return "18-24";
    if (agent.age <= 34) return "25-34";
    if (agent.age <= 49) return "35-49";
    if (agent.age <= 64) return "50-64";
    return "65+";
  }
  return inferIndustry(agent.occupation);
}

function inferIndustry(occupation: string): string {
  const normalized = String(occupation || "").toLowerCase();
  if (normalized.includes("teacher") || normalized.includes("school") || normalized.includes("professor")) return "Education";
  if (normalized.includes("nurse") || normalized.includes("doctor") || normalized.includes("health")) return "Healthcare";
  if (normalized.includes("engineer") || normalized.includes("software") || normalized.includes("developer") || normalized.includes("technician")) return "Technology";
  if (normalized.includes("bank") || normalized.includes("account") || normalized.includes("finance")) return "Finance";
  if (normalized.includes("driver") || normalized.includes("transport") || normalized.includes("delivery")) return "Transport";
  if (normalized.includes("civil") || normalized.includes("public") || normalized.includes("government")) return "Public Service";
  if (normalized.includes("manager") || normalized.includes("marketing") || normalized.includes("sales") || normalized.includes("real estate")) return "Business";
  if (normalized.includes("f&b") || normalized.includes("hawker") || normalized.includes("service")) return "Services";
  return "General";
}

function defaultDimensionForUseCase(useCase: string): DemographicDimension {
  if (useCase === "public-policy-testing" || useCase === "policy-review") return "industry";
  if (useCase === "campaign-content-testing" || useCase === "ad-testing") return "ageBucket";
  if (useCase === "product-market-research" || useCase === "pmf-discovery") return "occupation";
  return "industry";
}

function formatCountry(country: string): string {
  const normalized = String(country || "").trim().toLowerCase();
  if (normalized === "usa") return "USA";
  if (!normalized) return "Singapore";
  return normalized[0].toUpperCase() + normalized.slice(1);
}

function formatUseCase(useCase: string): string {
  const normalized = String(useCase || "").trim().toLowerCase();
  if (normalized === "public-policy-testing") return "Public Policy Testing";
  if (normalized === "product-market-research") return "Product & Market Research";
  if (normalized === "campaign-content-testing") return "Campaign & Content Testing";
  // V1 backward compat
  if (normalized === "policy-review") return "Public Policy Testing";
  if (normalized === "ad-testing") return "Campaign & Content Testing";
  if (normalized === "pmf-discovery" || normalized === "reviews") return "Product & Market Research";
  return "Public Policy Testing";
}
