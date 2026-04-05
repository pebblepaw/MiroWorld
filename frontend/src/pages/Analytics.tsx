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

export default function Analytics() {
  const { agents, useCase, country, simulationRounds } = useApp();

  const [dimension, setDimension] = useState<DemographicDimension>(() => defaultDimensionForUseCase(useCase));

  useEffect(() => {
    setDimension(defaultDimensionForUseCase(useCase));
  }, [useCase]);

  const sourceAgents = useMemo<Agent[]>(() => {
    if (agents.length > 0) return agents;
    return generateAgents(220);
  }, [agents]);

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
        const supporters = agentsInGroup.filter((agent) => agent.sentiment === "positive").length;
        const dissenters = agentsInGroup.filter((agent) => agent.sentiment === "negative").length;
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
    const supporters = overflowAgents.filter((agent) => agent.sentiment === "positive").length;
    const dissenters = overflowAgents.filter((agent) => agent.sentiment === "negative").length;

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
  }, [dimension, sourceAgents]);

  const dimensionOptions = useMemo(() => {
    if (useCase === "policy-review") {
      return [
        { key: "industry", label: "Industry" },
        { key: "planningArea", label: "Planning Area" },
        { key: "incomeBracket", label: "Income" },
        { key: "ageBucket", label: "Age" },
        { key: "occupation", label: "Occupation" },
        { key: "gender", label: "Gender" },
      ] as Array<{ key: DemographicDimension; label: string }>;
    }

    if (useCase === "ad-testing") {
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

  return (
    <div className="h-full overflow-y-auto scrollbar-thin bg-background">
      <div className="mx-auto flex w-full max-w-[1700px] flex-col gap-5 px-6 py-6">
        <header className="surface-card px-5 py-4">
          <h2 className="text-xl font-semibold tracking-tight text-white">Simulation Analytics</h2>
          <p className="mt-1 text-[11px] font-mono uppercase tracking-[0.15em] text-muted-foreground">
            {formatCountry(country)} · {formatUseCase(useCase)} · {sourceAgents.length} agents · {simulationRounds} rounds
          </p>
        </header>

        <section className="space-y-3">
          <div className="flex items-center gap-2 px-1">
            <Activity className="h-4 w-4 text-white/70" />
            <h3 className="text-xs font-mono uppercase tracking-[0.15em] text-white/80">Sentiment Dynamics</h3>
          </div>
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
            <PolarizationCard />
            <OpinionFlowCard />
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
                  {group.agents.map((agent) => (
                    <span
                      key={agent.id}
                      className="h-3.5 w-3.5 cursor-crosshair rounded-[2px] border border-black/20 transition-transform hover:z-10 hover:scale-125"
                      style={{ backgroundColor: sentimentColor(agent.sentiment) }}
                      title={`${agent.name} · ${agent.sentiment}`}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="space-y-3">
          <div className="flex items-center gap-2 px-1">
            <Megaphone className="h-4 w-4 text-white/70" />
            <h3 className="text-xs font-mono uppercase tracking-[0.15em] text-white/80">KOL & Viral Posts</h3>
          </div>
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <KeyOpinionLeadersCard />
            <ViralPostsCard />
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

function PolarizationCard() {
  const latest = POLARIZATION_DATA[POLARIZATION_DATA.length - 1];

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
          <LineChart data={POLARIZATION_DATA} margin={{ top: 8, right: 16, left: -16, bottom: 4 }}>
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

function OpinionFlowCard() {
  const total = STANCE_ORDER.reduce((sum, stance) => sum + OPINION_FLOW.initial[stance], 0);
  const maxFlow = Math.max(...OPINION_FLOW.flows.map((flow) => flow.count));
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
        <FlowDistributionColumn title="Initial" values={OPINION_FLOW.initial} total={total} />

        <div className="h-[178px] rounded border border-white/10 bg-white/[0.02] p-2">
          <svg viewBox="0 0 220 172" className="h-full w-full" preserveAspectRatio="none">
            {OPINION_FLOW.flows.map((flow, index) => {
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

        <FlowDistributionColumn title="Final" values={OPINION_FLOW.final} total={total} />
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

function KeyOpinionLeadersCard() {
  const sections = useMemo(() => {
    const supporters = KEY_OPINION_LEADERS.filter((leader) => leader.stance === "supporter").slice(0, 3);
    const dissenters = KEY_OPINION_LEADERS.filter((leader) => leader.stance === "dissenter").slice(0, 3);

    if (supporters.length > 0 && dissenters.length > 0) {
      return [
        { title: "Top Supporters", leaders: supporters },
        { title: "Top Dissenters", leaders: dissenters },
      ];
    }

    return [
      {
        title: "Top Opinion Leaders",
        leaders: [...KEY_OPINION_LEADERS].sort((left, right) => right.influence - left.influence).slice(0, 3),
      },
    ];
  }, []);

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
                <p className="text-xs leading-relaxed text-white/80">{leader.topView}</p>
                <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
                  <span className="font-mono uppercase tracking-wide text-white/65">Top Post:</span> {leader.topPost}
                </p>
              </article>
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}

function ViralPostsCard() {
  return (
    <section className="surface-card p-5">
      <div className="mb-4 flex items-center gap-2">
        <Flame className="h-4 w-4 text-white/70" />
        <h3 className="text-sm font-semibold uppercase tracking-[0.11em] text-white">Viral Posts</h3>
      </div>

      <div className="space-y-4">
        {VIRAL_POSTS.slice(0, 3).map((post, index) => (
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
  if (useCase === "policy-review") return "industry";
  if (useCase === "ad-testing") return "ageBucket";
  if (useCase === "pmf-discovery") return "occupation";
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
  if (normalized === "policy-review") return "Policy Review";
  if (normalized === "ad-testing") return "Ad Testing";
  if (normalized === "pmf-discovery") return "PMF Discovery";
  if (normalized === "reviews") return "Reviews";
  return "Policy Review";
}
