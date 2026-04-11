import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowRight, Loader2, Shuffle, Sparkles, Users, Info } from 'lucide-react';
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip as RechartsTooltip, XAxis, YAxis } from 'recharts';

import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { Textarea } from '@/components/ui/textarea';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { useApp } from '@/contexts/AppContext';
import {
  getBundledDemoOutput,
  getCountryUiConfig,
  isLiveBootMode,
  previewPopulation,
} from '@/lib/console-api';
import type { CountryUiConfig, CountryUiCohortDimension, CountryUiTooltipField } from '@/lib/console-api';
import { toast } from '@/hooks/use-toast';
import { SingaporeMap } from '@/components/SingaporeMap';

const CHART_COLORS = [
  'hsl(var(--data-green))',
  'hsl(var(--data-amber))',
  'hsl(var(--data-blue))',
  'hsl(var(--data-red))',
  'hsl(var(--data-purple))',
  'hsl(var(--data-cyan))',
];

type SampleMode = 'affected_groups' | 'population_baseline';

export default function AgentConfig() {
  const {
    sessionId,
    knowledgeArtifact,
    country,
    agentCount,
    sampleMode,
    samplingInstructions,
    sampleSeed,
    populationArtifact,
    populationLoading,
    populationError,
    simulationRounds,
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
    modelProvider,
  } = useApp();

  const [groupCategory, setGroupCategory] = useState<string>('');
  const [uiConfig, setUiConfig] = useState<CountryUiConfig | null>(null);
  const normalizedCountry = String(country || '').trim().toLowerCase();

  // Fetch UI config from YAML-driven backend endpoint
  useEffect(() => {
    if (!normalizedCountry) return;
    let cancelled = false;
    getCountryUiConfig(normalizedCountry).then((cfg) => {
      if (cancelled) return;
      setUiConfig(cfg);
      // Set default group category to first dimension
      const dims = cfg.cohort_dimensions;
      if (dims?.length && !groupCategory) {
        setGroupCategory(dims[0].key);
      }
    });
    return () => { cancelled = true; };
  }, [normalizedCountry]); // eslint-disable-line react-hooks/exhaustive-deps

  const cohortDimensions: CountryUiCohortDimension[] = useMemo(
    () => uiConfig?.cohort_dimensions ?? [
      { key: 'industry', label: 'Industry', persona_field: 'industry' },
      { key: 'ageBucket', label: 'Age', type: 'age_bucket' as const },
      { key: 'geography', label: 'Geography', type: 'geography' as const },
      { key: 'occupation', label: 'Occupation', persona_field: 'occupation' },
      { key: 'sex', label: 'Gender', persona_field: 'sex' },
    ],
    [uiConfig],
  );

  const tooltipFields: CountryUiTooltipField[] = useMemo(
    () => uiConfig?.tooltip_fields ?? [
      { field: 'occupation', label: 'Occupation', section: 'header' as const },
      { field: 'planning_area', label: 'Geography', section: 'grid' as const, type: 'geography' as const },
      { field: 'education_level', label: 'Education', section: 'grid' as const },
      { field: 'industry', label: 'Industry', section: 'grid' as const },
      { field: 'cultural_background', label: 'Culture', section: 'grid' as const },
      { field: 'income_bracket', label: 'Salary', section: 'grid' as const, fallback_fields: ['salary', 'household_income'] },
    ],
    [uiConfig],
  );

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
    const requestedAgentCount = Math.max(2, agentCount);
    try {
      setPopulationLoading(true);
      setPopulationError(null);
      const artifact = await previewPopulation(sessionId, {
        agent_count: requestedAgentCount,
        sample_mode: sampleMode,
        sampling_instructions: samplingInstructions.trim() || undefined,
        seed: requestedSeed,
      });
      setPopulationArtifact(artifact);
      setSampleSeed(artifact.sample_seed);
      setAgentsGenerated(true);
      setAgents(artifact.sampled_personas.map((row) => sampledPersonaToMockAgent(row)));
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
      if (!isLiveBootMode()) {
        try {
          const demo = await getBundledDemoOutput();
          const artifact = demo.population as any;
          if (artifact?.sampled_personas) {
            setPopulationArtifact(artifact);
            setSampleSeed(artifact.sample_seed);
            setAgentsGenerated(true);
            setAgents(artifact.sampled_personas.map((row: any) => sampledPersonaToMockAgent(row)));
            setSimulationComplete(false);
            setSimPosts([]);
            toast({
              title: 'Demo Population Loaded',
              description: 'Backend unavailable. Loaded cached demo agents.',
            });
            return;
          }
        } catch {
          // Demo fallback failed
        }
      }

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
  const occupationData = useMemo(() => buildOccupationDistribution(sampledPersonas), [sampledPersonas]);
  const geographyDistribution = useMemo(
    () => resolveGeographyDistribution(artifact, sampledPersonas, country),
    [artifact, country, sampledPersonas],
  );
  const topAreas = useMemo(() => buildTopAreas(geographyDistribution), [geographyDistribution]);

  const waffleGroups = useMemo(() => {
    if (!sampledPersonas.length) return [];
    
    // Find the active dimension config from YAML-driven cohort dimensions
    const activeDim = cohortDimensions.find(d => d.key === groupCategory);
    
    const resolveKey = (row: any, dim: string) => {
      // Special built-in types
      if (activeDim?.type === 'age_bucket' || dim === 'ageBucket') {
        const age = Number(row.persona.age ?? 0);
        return age <= 24 ? '18-24' : age <= 34 ? '25-34' : age <= 49 ? '35-49' : '50+';
      }
      if (activeDim?.type === 'geography' || dim === 'planningArea' || dim === 'geography') {
        return formatLabel(resolvePersonaGeographyValue(row.persona, country));
      }
      // Dynamic persona field from config
      const field = activeDim?.persona_field ?? dim;
      return formatLabel(String(row.persona[field] ?? 'Other'));
    };

    const grouped = new Map<string, any[]>();
    sampledPersonas.forEach((row) => {
      const key = resolveKey(row, groupCategory);
      const score = Math.max(0, Math.min(1, Number(row.selection_reason?.score ?? 0.4)));
      const agent = {
        id: row.agent_id,
        categoryName: key,
        score,
        persona: row.persona,
        selection_reason: row.selection_reason
      };
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key)!.push(agent);
    });

    const sortedGroups = Array.from(grouped.entries())
      .sort((a, b) => b[1].length - a[1].length);

    // Keep top 12, group rest into "Other"
    const finalGroups = sortedGroups.slice(0, 11);
    const rest = sortedGroups.slice(11);
    if (rest.length > 0) {
      const otherAgents = rest.flatMap(g => g[1]);
      const existingOther = finalGroups.find(g => g[0] === 'Other');
      if (existingOther) {
        existingOther[1].push(...otherAgents);
      } else {
        finalGroups.push(['Other', otherAgents]);
      }
    }

    return finalGroups.map(([name, agents]) => ({ name, agents }));
  }, [cohortDimensions, country, groupCategory, sampledPersonas]);

  const generationDisabled = populationLoading || !sessionId || !knowledgeArtifact;

  return (
    <div className="flex flex-col gap-8 h-full p-2 lg:p-6 overflow-y-auto scrollbar-thin bg-background">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-border">
        <div>
          <h2 className="text-page-title font-semibold text-foreground tracking-tight">Agent Configuration</h2>
          <p className="text-sm text-muted-foreground mt-1 font-light">Generate and refine an AI population cohort matching your parameters</p>
        </div>
        <div className="flex gap-3">
          <Button onClick={handleGenerate} disabled={generationDisabled} className="bg-primary text-primary-foreground font-medium px-5">
            {populationLoading ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Sampling...</> : <><Sparkles className="w-4 h-4 mr-2" /> Sample Population</>}
          </Button>
          {artifact && (
            <Button onClick={handleResample} disabled={populationLoading} variant="outline" className="border-border text-foreground hover:bg-muted">
              <Shuffle className="w-4 h-4 mr-2" /> Re-sample
            </Button>
          )}
          {artifact && (
            <Button
              onClick={handleProceed}
              variant="outline"
              className="h-10 border border-success/30 bg-success/20 px-6 font-mono text-xs uppercase tracking-wider text-success hover:bg-success/30"
            >
              Proceed <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          )}
        </div>
      </div>

      {populationError && (
        <div className="bg-destructive/10 border border-destructive/20 text-destructive text-sm p-3 rounded-md">
          {populationError}
        </div>
      )}

      {/* Row 1: Configuration */}
      <div className="grid grid-cols-1 xl:grid-cols-[0.8fr_1.2fr] gap-6">
        <div className="surface-card border border-border rounded-xl p-5 shadow-sm">
          <div className="flex flex-row items-start justify-between mb-4">
            <span className="text-sm font-medium text-foreground">Target Sample Size</span>
            <div className="flex flex-col items-end text-right">
              <span className="text-2xl font-mono text-primary/90 leading-none">{agentCount.toLocaleString()}</span>
              <span className="text-[10px] font-mono text-muted-foreground mt-1">
                {String(modelProvider).toLowerCase() === 'gemini' ? '~0.42¢ est. (cached)' : '~1.68¢ est.'}
              </span>
            </div>
          </div>
          <Slider
            value={[agentCount]}
            onValueChange={handleCountChange}
            min={10}
            max={500}
            step={10}
            className="w-full mb-2"
          />
          <div className="flex justify-between text-[11px] text-muted-foreground font-mono mb-1">
            <span>10</span><span>500</span>
          </div>
          <p className="text-[10px] font-mono mb-5" style={{
            color: agentCount <= 300
              ? 'hsl(142, 60%, 45%)'
              : agentCount <= 400
              ? 'hsl(38, 92%, 50%)'
              : 'hsl(0, 84%, 60%)',
          }}>
            {agentCount <= 300
              ? '✓ Optimal range — good quality/speed balance'
              : agentCount <= 400
              ? '⚠ Large simulation — may take longer'
              : '⚠ Very large — expect extended run time'}
          </p>

          <div className="text-xs text-muted-foreground font-medium uppercase tracking-wider mb-3">Sampling Strategy</div>
          <div className="flex flex-col sm:flex-row gap-2">
            <ModeButton
              active={sampleMode === 'affected_groups'}
              label="Affected Cohort"
              onClick={() => handleSampleModeChange('affected_groups')}
            />
            <ModeButton
              active={sampleMode === 'population_baseline'}
              label="Population Baseline"
              onClick={() => handleSampleModeChange('population_baseline')}
            />
          </div>


        </div>

        <div className="surface-card border border-border rounded-xl p-5 shadow-sm flex flex-col">
          <label htmlFor="sampling-instructions" className="text-sm font-medium text-foreground mb-3 flex items-center justify-between">
            <span>Strategic Parameters</span>
            {artifact && (
              <span className="text-xs font-normal text-muted-foreground border border-border px-2 py-0.5 rounded-sm bg-muted/50">
                Mode: {artifact.sample_mode === 'affected_groups' ? 'Targeted' : 'Baseline'}
              </span>
            )}
          </label>
          <Textarea
            id="sampling-instructions"
            value={samplingInstructions}
            onChange={(event) => handleInstructionsChange(event.target.value)}
            placeholder="E.g. Over-sample gig workers under 30. Exclude tourists..."
            className="bg-background border-border text-foreground flex-1 min-h-[100px] resize-none focus-visible:ring-1 focus-visible:ring-primary/50 text-sm leading-relaxed"
          />
          {artifact && artifact.parsed_sampling_instructions?.notes_for_ui?.length > 0 && (
            <div className="mt-4 pt-4 border-t border-border flex-1">
              <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-2">Parsed Strategy Notes</div>
              <ul className="text-xs text-muted-foreground/80 space-y-1.5 list-disc pl-3 marker:text-primary">
                {artifact.parsed_sampling_instructions.notes_for_ui.map((note: string) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      {artifact ? (
        <>
          {/* Analytical Header Stats */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-px bg-border border border-border rounded-xl overflow-hidden">
            <InlineStat label="Candidate Shortlist" value={artifact.candidate_count.toLocaleString()} tooltipText="Initial candidate pool passing hard demographic filters." />
            <InlineStat label="Semantic Rerank" value={artifact.selection_diagnostics?.semantic_rerank_count?.toLocaleString() ?? 0} tooltipText="Secondary retrieval phase that refines the candidate pool based on exact meaning and context." />
            <InlineStat label="Target Sample Size" value={artifact.sample_count.toLocaleString()} />
            <InlineStat label="Representativeness" value={artifact.representativeness.status} highlight={artifact.representativeness.status === 'Pass'} tooltipText="Statistical parity check against baseline distributions." />
          </div>

          {/* Row 2: Demographics & Geography */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="surface-card border border-border rounded-xl p-5">
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-widest mb-4">Age Stratification</h4>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={ageBuckets} margin={{ top: 0, right: 0, left: -25, bottom: 0 }}>
                  <XAxis dataKey="name" tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <RechartsTooltip cursor={{ fill: 'hsl(var(--foreground) / 0.04)' }} content={<CustomBarTooltip />} />
                  <Bar dataKey="count" fill="hsl(var(--data-blue))" radius={[2, 2, 0, 0]} maxBarSize={48} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="surface-card border border-border rounded-xl p-5">
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-widest mb-4">Occupation Distribution</h4>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={occupationData} layout="vertical" margin={{ top: 0, right: 10, left: 0, bottom: 0 }}>
                  <XAxis type="number" hide />
                  <YAxis
                    type="category"
                    dataKey="name"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                    width={110}
                  />
                  <RechartsTooltip cursor={{ fill: 'hsl(var(--foreground) / 0.04)' }} content={<CustomBarTooltip />} />
                  <Bar dataKey="value" radius={[0, 2, 2, 0]} maxBarSize={20}>
                    {occupationData.map((entry, index) => (
                      <Cell key={entry.name} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="surface-card border border-border rounded-xl p-5 flex flex-col">
              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-widest mb-4">Top Geography</h4>
              <div className="flex-1 -mx-2 -mb-2 rounded-lg overflow-hidden border border-border">
                <SingaporeMap areaData={topAreas} country={normalizedCountry === 'usa' ? 'usa' : 'singapore'} />
              </div>
            </div>
          </div>

          {/* Row 3: Cohort Explorer (Waffle Grid Pane) */}
          <div className="surface-card border border-border rounded-xl flex flex-col min-h-[800px] overflow-hidden">
            <div className="p-5 border-b border-border shrink-0 flex flex-col md:flex-row items-center justify-between bg-card">
              <div>
                <h3 className="text-base font-medium text-foreground">Cohort Explorer</h3>
                <p className="text-xs text-muted-foreground mt-1">
                  Individual personas visualized by categorical grid. Hover over any block to view exhaustive profile metadata.
                </p>
              </div>
              <div className="flex flex-col md:flex-row md:items-center mt-4 md:mt-0 gap-x-6 gap-y-3 bg-muted/40 p-2 md:px-4 md:py-2 rounded-md border border-border">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-muted-foreground/50 uppercase tracking-widest font-semibold mr-1">Sort By</span>
                  <div className="flex flex-wrap gap-1.5">
                    {cohortDimensions.map((dim) => (
                      <MetricToggle
                        key={dim.key}
                        active={groupCategory === dim.key}
                        onClick={() => setGroupCategory(dim.key)}
                        label={dim.label}
                      />
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="flex-1 p-6 md:p-8 overflow-y-auto scrollbar-thin">
              <div className="flex flex-wrap gap-x-8 gap-y-10">
                {waffleGroups.map((group, groupIndex) => (
                  <div key={group.name} className="flex flex-col shrink-0 min-w-[200px]">
                    <div className="flex items-baseline justify-between mb-3 border-b border-border pb-1 w-full max-w-[340px]">
                      <h4 className="text-sm font-semibold text-foreground truncate max-w-[280px]" title={group.name}>{group.name}</h4>
                      <span className="text-[11px] font-mono text-muted-foreground ml-3 bg-muted px-2 py-0.5 rounded">{group.agents.length}</span>
                    </div>
                    <div className="flex flex-wrap gap-1 max-w-[340px]">
                      {group.agents.map((agent: any) => (
                        <TooltipProvider key={agent.id} delayDuration={100}>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <div 
                                className="w-3.5 h-3.5 rounded-[2px] transition-transform hover:scale-125 hover:z-10 cursor-crosshair border border-black/20"
                                style={{ backgroundColor: CHART_COLORS[groupIndex % CHART_COLORS.length] }}
                                aria-label={`Persona ${agent.id}`}
                              />
                            </TooltipTrigger>
                            <TooltipContent 
                              className="max-w-[340px] w-[340px] text-xs bg-popover text-popover-foreground border border-border shadow-2xl p-0 overflow-hidden" 
                              side="top"
                              align="center"
                              sideOffset={6}
                            >
                               <WaffleTooltipContent data={agent} tooltipFields={tooltipFields} country={normalizedCountry} />
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="flex-1 flex items-center justify-center min-h-[400px] border border-border border-dashed rounded-xl bg-muted/20">
          {populationLoading ? (
            <div className="flex flex-col items-center gap-4 text-primary">
              <Loader2 className="w-8 h-8 animate-spin" />
              <span className="text-sm font-medium">Sampling population...</span>
            </div>
          ) : (
            <div className="text-center text-muted-foreground/60 max-w-sm">
              <Users className="w-10 h-10 mx-auto mb-4 opacity-50" />
              <p className="text-sm">Configure parameters and generate the initial cohort to populate the analytics dashboard.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Subcomponents

function InlineStat({ label, value, highlight = false, tooltipText }: { label: string; value: string | number; highlight?: boolean; tooltipText?: string }) {
  const inner = (
    <div className={`p-4 surface-card flex flex-col justify-center h-full transition-colors ${highlight ? 'text-primary' : ''} ${tooltipText ? 'hover:bg-white-[0.02]' : ''}`}>
      <div className="text-2xl font-mono font-medium tracking-tight mb-1" style={highlight ? { color: 'hsl(160, 84%, 45%)' } : {}}>{value}</div>
      <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest flex items-center gap-1.5">
        {label}
        {tooltipText && <Info className="w-3 h-3 text-muted-foreground/60" />}
      </div>
    </div>
  );

  if (tooltipText) {
    return (
      <TooltipProvider delayDuration={200}>
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="cursor-help">{inner}</div>
          </TooltipTrigger>
          <TooltipContent className="max-w-[220px] text-xs leading-relaxed bg-popover text-popover-foreground border-border" side="bottom">
            {tooltipText}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }
  return inner;
}

function ModeButton({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-4 py-2 text-xs font-medium uppercase tracking-wider rounded-md transition-colors ${
        active
          ? 'bg-foreground/10 text-foreground'
          : 'bg-transparent text-muted-foreground hover:bg-muted hover:text-foreground'
      }`}
    >
      {label}
    </button>
  );
}

function MetricToggle({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-3 py-1.5 text-[11px] font-medium transition-all rounded-sm ${
        active 
        ? 'bg-foreground/10 text-foreground shadow-sm' 
        : 'text-muted-foreground/80 hover:text-foreground hover:bg-muted'
      }`}
    >
      {label}
    </button>
  );
}

const CustomBarTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-popover border border-border px-3 py-2 rounded shadow-xl text-xs">
        <span className="text-muted-foreground mr-3">{payload[0].payload.name}:</span>
        <span className="font-mono text-foreground tracking-widest">{payload[0].value}</span>
      </div>
    );
  }
  return null;
};

function WaffleTooltipContent({ data, tooltipFields, country }: { data: any; tooltipFields: CountryUiTooltipField[]; country: string }) {
  const persona = data.persona;
  const displayName = resolvePersonaDisplayName(data);
  
  // Parse lists or unstructured text
  const rawSkills = String(persona.skills_and_expertise_list || persona.skills_and_expertise || '');
  const skills = rawSkills.split('\\n').filter(Boolean).map(s => s.replace(/^- /, ''));
  
  const rawHobbies = String(persona.hobbies_and_interests_list || persona.hobbies_and_interests || '');
  const hobbies = rawHobbies.split('\\n').filter(Boolean).map(s => s.replace(/^- /, ''));

  const headerField = tooltipFields.find(f => f.section === 'header');
  const gridFields = tooltipFields.filter(f => f.section === 'grid');

  const resolveFieldValue = (field: CountryUiTooltipField): string => {
    if (field.type === 'geography') {
      return formatLabel(resolvePersonaGeographyValue(persona, country));
    }
    let val = persona[field.field];
    if ((val === undefined || val === null || val === '') && field.fallback_fields) {
      for (const fb of field.fallback_fields) {
        val = persona[fb];
        if (val !== undefined && val !== null && val !== '') break;
      }
    }
    return formatLabel(String(val ?? 'Not specified'));
  };

  return (
    <div className="flex flex-col text-left">
      <div className="bg-card p-4 border-b border-border">
        <div className="flex justify-between items-start mb-1">
          <div className="font-semibold text-foreground text-[13px] tracking-tight leading-snug pr-2">
            {displayName}
          </div>
          <span className="bg-primary/20 text-primary px-1.5 py-0.5 rounded text-[10px] font-mono whitespace-nowrap">
            Match: {(data.score * 100).toFixed(0)}%
          </span>
        </div>
        <div className="text-[11px] text-muted-foreground">
          {headerField ? resolveFieldValue(headerField) : formatLabel(String(persona.occupation ?? 'Resident'))}
        </div>
        <div className="text-[11px] text-muted-foreground mt-1">
          {persona.age} yrs • {formatLabel(String(persona.sex ?? persona.gender ?? ''))} • {formatLabel(String(persona.marital_status ?? 'Single'))}
        </div>
      </div>
      
      <div className="p-4 space-y-3 surface-card">
        <div className="grid grid-cols-[80px_1fr] gap-x-2 gap-y-2 text-[11px]">
          {gridFields.map((field) => {
            const val = resolveFieldValue(field);
            if (val === 'Not specified' || val === '') return null;
            return (
              <React.Fragment key={field.field}>
                <span className="text-muted-foreground/60">{field.label}</span>
                <span className="text-foreground truncate">{val}</span>
              </React.Fragment>
            );
          })}
        </div>

        {skills.length > 0 && (
          <div className="border-t border-border pt-3">
            <div className="text-[9px] uppercase tracking-widest text-muted-foreground mb-1.5">Skills &amp; Expertise</div>
            <div className="flex flex-wrap gap-1">
              {skills.slice(0, 4).map((skill: string, i: number) => (
                <span key={i} className="text-[9px] bg-muted text-muted-foreground px-1.5 py-0.5 rounded border border-border">{skill}</span>
              ))}
            </div>
          </div>
        )}

        {hobbies.length > 0 && (
          <div className="border-t border-border pt-3">
            <div className="text-[9px] uppercase tracking-widest text-muted-foreground mb-1.5">Hobbies</div>
            <div className="flex flex-wrap gap-1">
              {hobbies.slice(0, 3).map((hobby: string, i: number) => (
                <span key={i} className="text-[9px] bg-muted text-muted-foreground px-1.5 py-0.5 rounded border border-border">{hobby}</span>
              ))}
            </div>
          </div>
        )}

        <div className="border-t border-border pt-3">
          <div className="text-[9px] uppercase tracking-widest text-muted-foreground mb-1">Career Goal</div>
          <div className="text-[10px] text-muted-foreground leading-relaxed italic line-clamp-2">
            "{String(persona.career_goals_and_ambitions ?? 'Not specified').trim()}"
          </div>
        </div>

        {data.selection_reason?.semantic_summary && (
          <div className="mt-1 pt-3 border-t border-border text-[10px] text-primary/80 leading-relaxed italic">
             Reason: {data.selection_reason.semantic_summary}
          </div>
        )}
      </div>
    </div>
  );
}

// Data Transformers

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

function buildOccupationDistribution(sampledPersonas: Array<{ persona: Record<string, unknown> }>) {
  const counts = sampledPersonas.reduce((acc, row) => {
    const occupation = formatLabel(String(row.persona.occupation ?? 'Other'));
    acc[occupation] = (acc[occupation] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1]) // highest first
    .slice(0, 6)
    .map(([name, value]) => ({ name: name.length > 20 ? name.slice(0, 20)+'…' : name, value }));
}

function buildTopAreas(distribution: Record<string, number>) {
  return Object.entries(distribution)
    .sort((left, right) => right[1] - left[1])
    .slice(0, 8)
    .map(([name, count]) => ({ name: name.length > 15 ? `${name.slice(0, 15)}…` : name, count }));
}

function formatLabel(raw: string) {
  return raw
    .replace(/_/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
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
    display_name?: string;
    persona: Record<string, unknown>;
    selection_reason: { score: number };
  },
): any {
  const approvalScore = Math.round(Number(row.selection_reason?.score ?? 0.5) * 100);
  const displayName = resolvePersonaDisplayName(row);
  return {
    id: row.agent_id,
    name: displayName,
    age: Number(row.persona.age ?? 0),
    gender: String(row.persona.sex ?? 'Unknown'),
    ethnicity: String(row.persona.ethnicity ?? row.persona.cultural_background ?? row.persona.country ?? 'Unknown'),
    occupation: formatLabel(String(row.persona.occupation ?? 'Resident')),
    planningArea: formatLabel(resolvePersonaGeographyValue(row.persona, String(row.persona.country ?? ''))),
    incomeBracket: 'Not specified',
    housingType: 'Not specified',
    sentiment: approvalScore >= 67 ? 'positive' : approvalScore >= 40 ? 'neutral' : 'negative',
    approvalScore,
  };
}

function resolvePersonaDisplayName(row: {
  display_name?: string;
  persona?: Record<string, unknown>;
  agent_id?: string;
}): string {
  const direct = String(row.display_name ?? '').trim();
  if (direct) return direct;

  const personaName = String(row.persona?.display_name ?? row.persona?.name ?? '').trim();
  if (personaName) return personaName;

  return formatLabel(String(row.persona?.occupation ?? row.agent_id ?? 'Resident'));
}

function resolvePersonaGeographyValue(persona: Record<string, unknown>, country: string): string {
  const normalizedCountry = String(country || '').trim().toLowerCase();
  const preferredKeys = normalizedCountry === 'usa'
    ? ['state', 'geography', 'planning_area', 'location', 'region', 'area']
    : ['planning_area', 'geography', 'state', 'location', 'region', 'area'];

  for (const key of preferredKeys) {
    const value = String(persona[key] ?? '').trim();
    if (value) {
      return value;
    }
  }

  return 'Unknown';
}

function resolveGeographyDistribution(
  artifact: {
    representativeness?: {
      geography_distribution?: Record<string, number>;
      state_distribution?: Record<string, number>;
      planning_area_distribution?: Record<string, number>;
    } | null;
  } | null,
  sampledPersonas: Array<{ persona: Record<string, unknown> }>,
  country: string,
) {
  const representativeness = artifact?.representativeness;
  const candidateDistribution =
    representativeness?.geography_distribution
    ?? representativeness?.state_distribution
    ?? representativeness?.planning_area_distribution;

  if (candidateDistribution && Object.keys(candidateDistribution).length > 0) {
    return candidateDistribution;
  }

  return sampledPersonas.reduce((acc, row) => {
    const geography = resolvePersonaGeographyValue(row.persona, country);
    if (geography !== 'Unknown') {
      acc[geography] = (acc[geography] || 0) + 1;
    }
    return acc;
  }, {} as Record<string, number>);
}
