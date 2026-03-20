import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { forceCollide, forceManyBody } from 'd3-force-3d';
import ForceGraph2D from 'react-force-graph-2d';
import { ArrowRight, Eye, EyeOff, Loader2, Shuffle, Sparkles, Users } from 'lucide-react';
import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { GlassCard } from '@/components/GlassCard';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { Textarea } from '@/components/ui/textarea';
import { useApp } from '@/contexts/AppContext';
import { Agent } from '@/data/mockData';
import { previewPopulation } from '@/lib/console-api';
import { toast } from '@/hooks/use-toast';

const INDUSTRY_COLORS = [
  'hsl(193, 100%, 50%)',
  'hsl(38, 92%, 50%)',
  'hsl(160, 84%, 39%)',
  'hsl(280, 70%, 60%)',
  'hsl(0, 72%, 51%)',
  'hsl(215, 20%, 55%)',
];
const MIN_NODE_RADIUS = 4;
const MAX_NODE_RADIUS = 12;
const NODE_LABEL_GAP = 8;
const STAGE2_RELATIONSHIP_LABEL_STORAGE_KEY = 'screen2-relationship-labels';

type SampleMode = 'affected_groups' | 'population_baseline';
type GraphNodeDatum = {
  id: string;
  name: string;
  label: string;
  subtitle?: string;
  industryKey: string;
  score: number;
  renderRadius: number;
  x?: number;
  y?: number;
};
type GraphLinkDatum = {
  source: string | GraphNodeDatum;
  target: string | GraphNodeDatum;
  label?: string;
  reason?: string;
};

export default function AgentConfig() {
  const {
    sessionId,
    knowledgeArtifact,
    agentCount,
    sampleMode,
    samplingInstructions,
    sampleSeed,
    populationArtifact,
    populationLoading,
    populationError,
    setAgentCount,
    setSampleMode,
    setSamplingInstructions,
    setSampleSeed,
    setPopulationArtifact,
    setPopulationLoading,
    setPopulationError,
    setAgents,
    setAgentsGenerated,
    setSimulationComplete,
    setSimPosts,
    completeStep,
    setCurrentStep,
  } = useApp();
  const [dimensions, setDimensions] = useState({ width: 500, height: 300 });
  const [showRelationshipLabels, setShowRelationshipLabels] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return window.sessionStorage.getItem(STAGE2_RELATIONSHIP_LABEL_STORAGE_KEY) === 'on';
  });
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver(([entry]) => setDimensions({ width: entry.contentRect.width, height: entry.contentRect.height }));
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.sessionStorage.setItem(STAGE2_RELATIONSHIP_LABEL_STORAGE_KEY, showRelationshipLabels ? 'on' : 'off');
    }
  }, [showRelationshipLabels]);

  const resetPopulationPreview = useCallback(() => {
    setPopulationArtifact(null);
    setPopulationError(null);
    setSampleSeed(null);
    setAgentsGenerated(false);
    setAgents([]);
    setSimulationComplete(false);
    setSimPosts([]);
  }, [
    setAgents,
    setAgentsGenerated,
    setPopulationArtifact,
    setPopulationError,
    setSampleSeed,
    setSimPosts,
    setSimulationComplete,
  ]);

  const handleCountChange = useCallback((value: number[]) => {
    setAgentCount(value[0]);
    resetPopulationPreview();
  }, [resetPopulationPreview, setAgentCount]);

  const handleSampleModeChange = useCallback((mode: SampleMode) => {
    setSampleMode(mode);
    resetPopulationPreview();
  }, [resetPopulationPreview, setSampleMode]);

  const handleInstructionsChange = useCallback((nextValue: string) => {
    setSamplingInstructions(nextValue);
    if (populationArtifact) {
      resetPopulationPreview();
    }
  }, [populationArtifact, resetPopulationPreview, setSamplingInstructions]);

  const requestSampling = useCallback(async (mode: 'generate' | 'resample') => {
    if (!sessionId || !knowledgeArtifact) {
      const message = 'Complete Screen 1 document extraction before generating agents.';
      setPopulationError(message);
      toast({
        title: 'Screen 1 required',
        description: message,
        variant: 'destructive',
      });
      return;
    }

    const requestedSeed = nextSeed(sampleSeed);
    try {
      setPopulationLoading(true);
      setPopulationError(null);
      const artifact = await previewPopulation(sessionId, {
        agent_count: agentCount,
        sample_mode: sampleMode,
        sampling_instructions: samplingInstructions.trim() || undefined,
        seed: requestedSeed,
      });
      setPopulationArtifact(artifact);
      setSampleSeed(artifact.sample_seed);
      setAgentsGenerated(true);
      setAgents(artifact.sampled_personas.map((row, index) => sampledPersonaToMockAgent(row, index)));
      setSimulationComplete(false);
      setSimPosts([]);
      if (mode === 'resample') {
        toast({
          title: 'Cohort re-sampled',
          description: `Generated a fresh cohort with seed ${artifact.sample_seed}.`,
        });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Population sampling failed.';
      setPopulationError(message);
      setPopulationArtifact(null);
      setAgentsGenerated(false);
      toast({
        title: 'Agent sampling failed',
        description: message,
        variant: 'destructive',
      });
    } finally {
      setPopulationLoading(false);
    }
  }, [
    agentCount,
    knowledgeArtifact,
    sampleMode,
    sampleSeed,
    samplingInstructions,
    sessionId,
    setAgents,
    setAgentsGenerated,
    setPopulationArtifact,
    setPopulationError,
    setPopulationLoading,
    setSampleSeed,
    setSimPosts,
    setSimulationComplete,
  ]);

  const handleGenerate = useCallback(() => {
    void requestSampling('generate');
  }, [requestSampling]);

  const handleResample = useCallback(() => {
    void requestSampling('resample');
  }, [requestSampling]);

  const handleProceed = () => {
    completeStep(2);
    setCurrentStep(3);
  };

  const artifact = populationArtifact;
  const sampledPersonas = artifact?.sampled_personas ?? [];
  const ageBuckets = useMemo(() => buildAgeBuckets(sampledPersonas), [sampledPersonas]);
  const industryData = useMemo(() => buildIndustryMix(sampledPersonas), [sampledPersonas]);
  const topAreas = useMemo(() => buildTopAreas(artifact?.representativeness?.planning_area_distribution ?? {}), [artifact]);
  const graphLegend = useMemo(() => buildIndustryLegend(artifact), [artifact]);

  const graphData = useMemo(() => {
    if (!artifact) {
      return { nodes: [] as GraphNodeDatum[], links: [] as GraphLinkDatum[] };
    }
    const colorGroups = graphLegend.map((entry) => entry.key);
    return {
      nodes: artifact.agent_graph.nodes.map((node) => {
        const industryKey = normalizeIndustryKey(String(node.industry ?? 'Other'), colorGroups);
        return {
          id: node.id,
          name: formatLabel(node.label),
          label: formatLabel(node.label),
          subtitle: node.subtitle,
          industryKey,
          score: normalizeNodeScore(node.score),
          renderRadius: radiusFromScore(node.score),
        };
      }),
      links: artifact.agent_graph.links.map((link) => ({
        source: link.source,
        target: link.target,
        label: link.label || link.reason || '',
        reason: link.reason,
      })),
    };
  }, [artifact, graphLegend]);

  useEffect(() => {
    if (!graphRef.current?.d3Force || graphData.nodes.length === 0) return;

    const maxRadius = Math.max(...graphData.nodes.map((node) => node.renderRadius), MIN_NODE_RADIUS);
    graphRef.current.d3Force('charge', forceManyBody().strength(-(120 + maxRadius * 16)));
    graphRef.current.d3Force('collide', forceCollide((node: GraphNodeDatum) => node.renderRadius + 24).iterations(2));

    const linkForce = graphRef.current.d3Force('link');
    if (linkForce && typeof linkForce.distance === 'function') {
      linkForce.distance((link: { source: GraphNodeDatum; target: GraphNodeDatum }) => {
        const sourceRadius = link.source?.renderRadius ?? MIN_NODE_RADIUS;
        const targetRadius = link.target?.renderRadius ?? MIN_NODE_RADIUS;
        return Math.max(90, (sourceRadius + targetRadius) * 8);
      });
    }
    graphRef.current.d3ReheatSimulation?.();
  }, [graphData]);

  const generationDisabled = populationLoading || !sessionId || !knowledgeArtifact;

  return (
    <div className="flex flex-col gap-6 h-full p-6 overflow-y-auto scrollbar-thin">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-foreground">Agent Configuration</h2>
          <p className="text-sm text-muted-foreground">Generate a live Singapore cohort from the Nemotron population dataset</p>
        </div>
        <div className="flex gap-3">
          <Button onClick={handleGenerate} disabled={generationDisabled} className="bg-primary text-primary-foreground">
            {populationLoading ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</> : <><Sparkles className="w-4 h-4" /> Generate Agents</>}
          </Button>
          {artifact && (
            <Button onClick={handleResample} disabled={populationLoading} variant="outline" className="border-white/12 text-foreground hover:bg-white/6">
              <Shuffle className="w-4 h-4" /> Re-sample
            </Button>
          )}
          {artifact && (
            <Button onClick={handleProceed} variant="outline" className="border-success/30 text-success hover:bg-success/10">
              <ArrowRight className="w-4 h-4" /> Proceed
            </Button>
          )}
        </div>
      </div>

      <GlassCard className="p-5">
        <div className="grid grid-cols-1 xl:grid-cols-[0.9fr_1.1fr] gap-6">
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm text-muted-foreground">Number of Agents</span>
              <span className="text-2xl font-mono font-bold text-primary">{agentCount.toLocaleString()}</span>
            </div>
            <Slider
              value={[agentCount]}
              onValueChange={handleCountChange}
              min={100}
              max={500}
              step={100}
              className="w-full"
            />
            <div className="flex justify-between mt-1 text-[10px] text-muted-foreground font-mono">
              <span>100</span><span>500</span>
            </div>

            <div className="mt-5">
              <div className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Sampling Mode</div>
              <div className="flex flex-wrap gap-2">
                <ModeButton
                  active={sampleMode === 'affected_groups'}
                  label="Affected Groups"
                  onClick={() => handleSampleModeChange('affected_groups')}
                />
                <ModeButton
                  active={sampleMode === 'population_baseline'}
                  label="Population Baseline"
                  onClick={() => handleSampleModeChange('population_baseline')}
                />
              </div>
            </div>
          </div>

          <div>
            <label htmlFor="sampling-instructions" className="text-sm font-medium text-foreground mb-2 block">
              Sampling Instructions
            </label>
            <Textarea
              id="sampling-instructions"
              value={samplingInstructions}
              onChange={(event) => handleInstructionsChange(event.target.value)}
              placeholder="Describe which groups to bias toward, compare against, or keep balanced."
              className="bg-background/50 border-border text-foreground min-h-[130px] resize-none"
            />
            <p className="text-[11px] text-muted-foreground mt-2">
              This is parsed into hard filters, soft boosts, exclusions, and distribution hints before sampling.
            </p>
          </div>
        </div>
      </GlassCard>

      {populationError && (
        <p className="text-xs text-destructive">{populationError}</p>
      )}

      {artifact ? (
        <>
          <GlassCard className="p-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <MetricCard label="Candidate Pool" value={artifact.candidate_count} />
              <MetricCard label="Sample Size" value={artifact.sample_count} />
              <MetricCard label="Sample Seed" value={artifact.sample_seed} />
            </div>
          </GlassCard>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <GlassCard className="p-4">
              <h4 className="text-xs text-muted-foreground uppercase tracking-wider mb-3">Age Distribution</h4>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={ageBuckets}>
                  <XAxis dataKey="name" tick={{ fill: 'hsl(215,20%,55%)', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis hide />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Bar dataKey="count" fill="hsl(193,100%,50%)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </GlassCard>

            <GlassCard className="p-4">
              <h4 className="text-xs text-muted-foreground uppercase tracking-wider mb-3">Industry Mix</h4>
              <ResponsiveContainer width="100%" height={160}>
                <PieChart>
                  <Pie data={industryData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={35} outerRadius={60} paddingAngle={2}>
                    {industryData.map((entry, index) => <Cell key={entry.name} fill={INDUSTRY_COLORS[index % INDUSTRY_COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} />
                </PieChart>
              </ResponsiveContainer>
            </GlassCard>

            <GlassCard className="p-4">
              <h4 className="text-xs text-muted-foreground uppercase tracking-wider mb-3">Top Planning Areas</h4>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={topAreas} layout="vertical">
                  <XAxis type="number" hide />
                  <YAxis type="category" dataKey="name" tick={{ fill: 'hsl(215,20%,55%)', fontSize: 9 }} axisLine={false} tickLine={false} width={70} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Bar dataKey="count" fill="hsl(38,92%,50%)" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </GlassCard>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-[0.92fr_1.08fr] gap-4">
            <GlassCard className="p-4">
              <h4 className="text-xs text-muted-foreground uppercase tracking-wider mb-3">Parsed Instructions</h4>
              {artifact.parsed_sampling_instructions.notes_for_ui.length > 0 ? (
                <div className="space-y-2 text-sm text-foreground">
                  {artifact.parsed_sampling_instructions.notes_for_ui.map((note) => (
                    <p key={note}>{note}</p>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No additional parsing notes for this cohort.</p>
              )}
              <div className="mt-4 space-y-3">
                <ParsedInstructionSection
                  title="Hard Filters"
                  values={flattenInstructionBucket(artifact.parsed_sampling_instructions.hard_filters)}
                  emptyLabel="No hard filters"
                />
                <ParsedInstructionSection
                  title="Soft Boosts"
                  values={flattenInstructionBucket(artifact.parsed_sampling_instructions.soft_boosts)}
                  emptyLabel="No soft boosts"
                />
                <ParsedInstructionSection
                  title="Exclusions"
                  values={flattenInstructionBucket(artifact.parsed_sampling_instructions.exclusions)}
                  emptyLabel="No exclusions"
                />
                <ParsedInstructionSection
                  title="Distribution Targets"
                  values={flattenInstructionBucket(artifact.parsed_sampling_instructions.distribution_targets)}
                  emptyLabel="No distribution targets"
                />
              </div>
              <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
                <DiagnosticStat label="Shortlist" value={artifact.selection_diagnostics.shortlist_count ?? 0} />
                <DiagnosticStat label="Semantic Rerank" value={artifact.selection_diagnostics.semantic_rerank_count ?? 0} />
                <DiagnosticStat label="Mode" value={artifact.sample_mode === 'affected_groups' ? 'Affected' : 'Baseline'} />
                <DiagnosticStat label="Status" value={artifact.representativeness.status} />
              </div>
            </GlassCard>

            <GlassCard className="p-4">
              <h4 className="text-xs text-muted-foreground uppercase tracking-wider mb-3">Selection Rationale</h4>
              <div className="space-y-3">
                {sampledPersonas.slice(0, 3).map((row) => (
                  <div key={row.agent_id} className="rounded-xl border border-white/8 bg-white/[0.03] p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-sm font-medium text-foreground">{formatLabel(String(row.persona.occupation ?? row.agent_id))}</div>
                        <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                          {String(row.persona.planning_area ?? 'Unknown')} · {String(row.persona.industry ?? 'Unknown')}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-mono text-primary">{Number(row.selection_reason.score).toFixed(2)}</div>
                        <div className="text-[10px] text-muted-foreground">selection score</div>
                      </div>
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">{row.selection_reason.semantic_summary}</p>
                  </div>
                ))}
              </div>
            </GlassCard>
          </div>
        </>
      ) : null}

      <GlassCard glow={artifact ? 'primary' : 'none'} className="p-4 flex-1 min-h-[320px]">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-sm font-semibold text-foreground">Agent Graph</h3>
            <p className="text-xs text-muted-foreground mt-1">Live cohort graph using shared planning area, industry, and occupation edges</p>
          </div>
          {artifact && graphLegend.length > 0 && (
            <div className="flex flex-wrap justify-end gap-3">
              {graphLegend.map((entry) => (
                <span key={entry.key} className="flex items-center gap-1 text-[10px] text-muted-foreground">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
                  {entry.label}
                </span>
              ))}
            </div>
          )}
        </div>

        {artifact && (
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div className="text-[11px] text-muted-foreground">
              {artifact.sample_mode === 'affected_groups'
                ? 'Targeted toward the most affected groups in the document.'
                : 'Balanced baseline sample across the broader Singapore population.'}
            </div>
            <button
              type="button"
              onClick={() => setShowRelationshipLabels((current) => !current)}
              className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[10px] uppercase tracking-[0.18em] transition-colors ${
                showRelationshipLabels
                  ? 'border-primary/60 bg-primary/10 text-foreground'
                  : 'border-white/8 bg-white/4 text-muted-foreground hover:border-white/15 hover:text-foreground'
              }`}
            >
              {showRelationshipLabels ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
              {showRelationshipLabels ? 'Relationship Labels On' : 'Relationship Labels Off'}
            </button>
          </div>
        )}

        <div ref={containerRef} className="w-full h-[320px] rounded-lg overflow-hidden bg-background/30">
          {artifact && graphData.nodes.length > 0 ? (
            <ForceGraph2D
              ref={graphRef}
              graphData={graphData}
              width={dimensions.width}
              height={dimensions.height}
              nodeColor={(node: GraphNodeDatum) => legendColorFor(node.industryKey, graphLegend)}
              nodeRelSize={1}
              linkColor={() => 'hsl(225, 20%, 25%)'}
              linkWidth={1.25}
              linkLabel={(link: GraphLinkDatum) => link.label || link.reason || ''}
              nodeCanvasObjectMode={() => 'replace'}
              nodeCanvasObject={(node: GraphNodeDatum, ctx, globalScale) => {
                if (typeof node.x !== 'number' || typeof node.y !== 'number') return;

                const radius = node.renderRadius;
                const fontSize = Math.max(8, 11 / globalScale);
                const labelX = node.x + radius + NODE_LABEL_GAP;
                const labelY = node.y;
                const labelWidth = ctx.measureText(node.name).width;

                ctx.save();
                ctx.beginPath();
                ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
                ctx.fillStyle = legendColorFor(node.industryKey, graphLegend);
                ctx.fill();
                ctx.lineWidth = 1;
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.18)';
                ctx.stroke();

                ctx.font = `${fontSize}px Inter, sans-serif`;
                ctx.fillStyle = 'rgba(8, 10, 16, 0.78)';
                ctx.fillRect(labelX - 4, labelY - fontSize / 2 - 3, labelWidth + 8, fontSize + 6);

                ctx.textAlign = 'left';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = 'hsl(210, 40%, 93%)';
                ctx.fillText(node.name, labelX, labelY);
                ctx.restore();
              }}
              linkCanvasObjectMode={() => 'after'}
              linkCanvasObject={(link: GraphLinkDatum, ctx, globalScale) => {
                if (!showRelationshipLabels) {
                  return;
                }
                const label = (link.label || link.reason || '').trim();
                const source = typeof link.source === 'string' ? undefined : link.source;
                const target = typeof link.target === 'string' ? undefined : link.target;
                if (!label || typeof source?.x !== 'number' || typeof source?.y !== 'number' || typeof target?.x !== 'number' || typeof target?.y !== 'number') {
                  return;
                }

                const midX = (source.x + target.x) / 2;
                const midY = (source.y + target.y) / 2;
                const dx = target.x - source.x;
                const dy = target.y - source.y;
                const length = Math.hypot(dx, dy) || 1;
                const normalX = -dy / length;
                const normalY = dx / length;
                const fontSize = Math.max(8.5, 10.5 / globalScale);
                const textWidth = ctx.measureText(label).width;
                const offset = Math.min(20, Math.max(8, length * 0.08));

                ctx.save();
                ctx.font = `${fontSize}px Inter, sans-serif`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = 'rgba(8, 10, 16, 0.84)';
                ctx.fillRect(midX + normalX * offset - (textWidth + 12) / 2, midY + normalY * offset - (fontSize + 8) / 2, textWidth + 12, fontSize + 8);
                ctx.fillStyle = 'hsl(210, 28%, 96%)';
                ctx.fillText(label, midX + normalX * offset, midY + normalY * offset);
                ctx.restore();
              }}
              backgroundColor="transparent"
              cooldownTicks={80}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              {populationLoading ? (
                <div className="flex flex-col items-center gap-3">
                  <Loader2 className="w-8 h-8 animate-spin text-primary" />
                  <span>Generating population cohort...</span>
                </div>
              ) : (
                <div className="text-center">
                  <Users className="w-8 h-8 mx-auto mb-3 text-muted-foreground/60" />
                  <p>Generate agents to preview the sampled cohort graph.</p>
                </div>
              )}
            </div>
          )}
        </div>
      </GlassCard>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="text-xl font-bold font-mono text-primary">{value}</div>
      <div className="text-[10px] text-muted-foreground uppercase tracking-wider">{label}</div>
    </div>
  );
}

function DiagnosticStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-white/8 bg-white/[0.02] px-3 py-2">
      <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm font-medium text-foreground">{value}</div>
    </div>
  );
}

function ParsedInstructionSection({
  title,
  values,
  emptyLabel,
}: {
  title: string;
  values: Array<{ key: string; value: string }>;
  emptyLabel: string;
}) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">{title}</div>
      {values.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-2">
          {values.map((entry) => (
            <span
              key={`${title}-${entry.key}-${entry.value}`}
              className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] text-foreground"
            >
              <span className="text-muted-foreground">{formatInstructionKey(entry.key)}</span>
              <span>{formatLabel(entry.value)}</span>
            </span>
          ))}
        </div>
      ) : (
        <p className="mt-2 text-xs text-muted-foreground">{emptyLabel}</p>
      )}
    </div>
  );
}

function ModeButton({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-4 py-2 text-xs uppercase tracking-[0.18em] transition-colors ${
        active
          ? 'border-primary/60 bg-primary/12 text-foreground'
          : 'border-white/8 bg-white/[0.03] text-muted-foreground hover:border-white/15 hover:text-foreground'
      }`}
    >
      {label}
    </button>
  );
}

function flattenInstructionBucket(bucket: Record<string, string[]>) {
  return Object.entries(bucket).flatMap(([key, values]) =>
    values.map((value) => ({ key, value })),
  );
}

function formatInstructionKey(key: string) {
  return key.replace(/_/g, ' ');
}

function buildAgeBuckets(sampledPersonas: Array<{ persona: Record<string, unknown> }>) {
  const buckets = [
    { name: '18-24', count: 0 },
    { name: '25-34', count: 0 },
    { name: '35-49', count: 0 },
    { name: '50+', count: 0 },
  ];
  sampledPersonas.forEach((row) => {
    const age = Number(row.persona.age ?? 0);
    if (age <= 24) buckets[0].count += 1;
    else if (age <= 34) buckets[1].count += 1;
    else if (age <= 49) buckets[2].count += 1;
    else buckets[3].count += 1;
  });
  return buckets;
}

function buildIndustryMix(sampledPersonas: Array<{ persona: Record<string, unknown> }>) {
  const counts = sampledPersonas.reduce((acc, row) => {
    const industry = formatLabel(String(row.persona.industry ?? 'Other'));
    acc[industry] = (acc[industry] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);
  return Object.entries(counts).map(([name, value]) => ({ name, value }));
}

function buildTopAreas(distribution: Record<string, number>) {
  return Object.entries(distribution)
    .sort((left, right) => right[1] - left[1])
    .slice(0, 8)
    .map(([name, count]) => ({ name: name.length > 10 ? `${name.slice(0, 10)}…` : name, count }));
}

function buildIndustryLegend(
  artifact: ReturnType<typeof useApp>['populationArtifact'],
): Array<{ key: string; label: string; color: string }> {
  if (!artifact) {
    return [];
  }
  const counts = artifact.agent_graph.nodes.reduce((acc, node) => {
    const key = normalizeIndustryKey(String(node.industry ?? 'Other'));
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);
  const ordered = Object.entries(counts)
    .sort((left, right) => right[1] - left[1])
    .slice(0, 4);
  const keys = ordered.map(([key]) => key);
  if (Object.keys(counts).length > keys.length) {
    keys.push('other');
  }
  return keys.map((key, index) => ({
    key,
    label: key === 'other' ? 'Other' : formatLabel(key),
    color: INDUSTRY_COLORS[index % INDUSTRY_COLORS.length],
  }));
}

function legendColorFor(key: string, legend: Array<{ key: string; color: string }>) {
  return legend.find((entry) => entry.key === key)?.color ?? INDUSTRY_COLORS[INDUSTRY_COLORS.length - 1];
}

function normalizeIndustryKey(rawIndustry: string, visibleKeys?: string[]) {
  const normalized = rawIndustry.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_') || 'other';
  if (visibleKeys && visibleKeys.length > 0 && !visibleKeys.includes(normalized)) {
    return 'other';
  }
  return normalized;
}

function normalizeNodeScore(value?: number | null) {
  const score = Number.isFinite(value) ? Number(value) : 0.4;
  return Math.max(0, Math.min(1, score));
}

function radiusFromScore(value?: number | null) {
  const normalized = normalizeNodeScore(value);
  return Math.ceil(MIN_NODE_RADIUS + ((MAX_NODE_RADIUS - MIN_NODE_RADIUS) * normalized));
}

function nextSeed(previousSeed: number | null) {
  let seed = Math.floor(Math.random() * 2_147_483_647);
  if (previousSeed !== null && seed === previousSeed) {
    seed = (seed + 1) % 2_147_483_647;
  }
  return seed;
}

function sampledPersonaToMockAgent(
  row: {
    agent_id: string;
    persona: Record<string, unknown>;
    selection_reason: { score: number };
  },
  index: number,
): Agent {
  const approvalScore = Math.round(Number(row.selection_reason.score ?? 0) * 100);
  return {
    id: row.agent_id,
    name: `${formatLabel(String(row.persona.occupation ?? 'Resident'))} ${index + 1}`,
    age: Number(row.persona.age ?? 0),
    gender: String(row.persona.sex ?? 'Unknown'),
    ethnicity: String(row.persona.country ?? 'Singapore'),
    occupation: formatLabel(String(row.persona.occupation ?? 'Resident')),
    planningArea: formatLabel(String(row.persona.planning_area ?? 'Unknown')),
    incomeBracket: 'Not specified',
    housingType: 'Not specified',
    sentiment: approvalScore >= 67 ? 'positive' : approvalScore >= 40 ? 'neutral' : 'negative',
    approvalScore,
  };
}

function formatLabel(raw: string) {
  return raw
    .replace(/_/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

const tooltipStyle = {
  background: 'hsl(225,40%,8%)',
  border: '1px solid hsl(225,20%,18%)',
  borderRadius: 8,
  color: 'hsl(210,40%,93%)',
};
