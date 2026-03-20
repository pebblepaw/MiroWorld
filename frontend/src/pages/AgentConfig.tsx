import { useState, useCallback, useRef, useEffect } from 'react';
import { Users, Loader2, ArrowRight, Shuffle } from 'lucide-react';
import ForceGraph2D from 'react-force-graph-2d';
import { useApp } from '@/contexts/AppContext';
import { GlassCard } from '@/components/GlassCard';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { generateAgents } from '@/data/mockData';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

const CHART_COLORS = ['hsl(193,100%,50%)', 'hsl(38,92%,50%)', 'hsl(160,84%,39%)', 'hsl(280,70%,60%)', 'hsl(0,72%,51%)', 'hsl(215,20%,55%)'];

export default function AgentConfig() {
  const { agentCount, setAgentCount, setAgents, setAgentsGenerated, completeStep, setCurrentStep } = useApp();
  const [generating, setGenerating] = useState(false);
  const [agents, setLocalAgents] = useState(generateAgents(agentCount));
  const [generated, setGenerated] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState({ width: 500, height: 300 });

  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver(([e]) => setDims({ width: e.contentRect.width, height: e.contentRect.height }));
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  const handleCountChange = (val: number[]) => {
    setAgentCount(val[0]);
    setLocalAgents(generateAgents(val[0]));
    setGenerated(false);
  };

  const handleGenerate = () => {
    setGenerating(true);
    setTimeout(() => {
      const a = generateAgents(agentCount);
      setLocalAgents(a);
      setAgents(a);
      setAgentsGenerated(true);
      setGenerated(true);
      setGenerating(false);
    }, 2000);
  };

  const handleProceed = () => { completeStep(2); setCurrentStep(3); };

  // Demographics
  const ageBuckets = [
    { name: '21-30', count: agents.filter(a => a.age >= 21 && a.age <= 30).length },
    { name: '31-40', count: agents.filter(a => a.age >= 31 && a.age <= 40).length },
    { name: '41-55', count: agents.filter(a => a.age >= 41 && a.age <= 55).length },
    { name: '55+', count: agents.filter(a => a.age > 55).length },
  ];

  const ethnicityData = Object.entries(
    agents.reduce((acc, a) => { acc[a.ethnicity] = (acc[a.ethnicity] || 0) + 1; return acc; }, {} as Record<string, number>)
  ).map(([name, value]) => ({ name, value }));

  const topAreas = Object.entries(
    agents.reduce((acc, a) => { acc[a.planningArea] = (acc[a.planningArea] || 0) + 1; return acc; }, {} as Record<string, number>)
  ).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([name, count]) => ({ name: name.length > 10 ? name.slice(0, 10) + '…' : name, count }));

  // Agent graph clusters
  const clusterData = Object.entries(
    agents.reduce((acc, a) => { acc[a.planningArea] = (acc[a.planningArea] || 0) + 1; return acc; }, {} as Record<string, number>)
  );
  const graphData = {
    nodes: [
      { id: 'center', name: 'Population', val: 20 },
      ...clusterData.map(([area, count]) => ({ id: area, name: area, val: Math.max(3, count / 5) })),
    ],
    links: clusterData.map(([area]) => ({ source: 'center', target: area })),
  };

  return (
    <div className="flex flex-col gap-6 h-full p-6 overflow-y-auto scrollbar-thin">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-foreground">Agent Configuration</h2>
          <p className="text-sm text-muted-foreground">Configure synthetic population based on Nemotron Singaporean demographics</p>
        </div>
        <div className="flex gap-3">
          <Button onClick={handleGenerate} disabled={generating} className="bg-primary text-primary-foreground">
            {generating ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</> : <><Shuffle className="w-4 h-4" /> Generate Agents</>}
          </Button>
          {generated && (
            <Button onClick={handleProceed} variant="outline" className="border-success/30 text-success hover:bg-success/10">
              <ArrowRight className="w-4 h-4" /> Proceed
            </Button>
          )}
        </div>
      </div>

      {/* Slider */}
      <GlassCard className="p-5">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm text-muted-foreground">Number of Agents</span>
          <span className="text-2xl font-mono font-bold text-primary">{agentCount.toLocaleString()}</span>
        </div>
        <Slider
          value={[agentCount]}
          onValueChange={handleCountChange}
          min={100}
          max={5000}
          step={100}
          className="w-full"
        />
        <div className="flex justify-between mt-1 text-[10px] text-muted-foreground font-mono">
          <span>100</span><span>5,000</span>
        </div>
      </GlassCard>

      {/* Demographics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <GlassCard className="p-4">
          <h4 className="text-xs text-muted-foreground uppercase tracking-wider mb-3">Age Distribution</h4>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={ageBuckets}>
              <XAxis dataKey="name" tick={{ fill: 'hsl(215,20%,55%)', fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis hide />
              <Tooltip contentStyle={{ background: 'hsl(225,40%,8%)', border: '1px solid hsl(225,20%,18%)', borderRadius: 8, color: 'hsl(210,40%,93%)' }} />
              <Bar dataKey="count" fill="hsl(193,100%,50%)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </GlassCard>

        <GlassCard className="p-4">
          <h4 className="text-xs text-muted-foreground uppercase tracking-wider mb-3">Ethnicity</h4>
          <ResponsiveContainer width="100%" height={160}>
            <PieChart>
              <Pie data={ethnicityData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={35} outerRadius={60} paddingAngle={2}>
                {ethnicityData.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: 'hsl(225,40%,8%)', border: '1px solid hsl(225,20%,18%)', borderRadius: 8, color: 'hsl(210,40%,93%)' }} />
            </PieChart>
          </ResponsiveContainer>
        </GlassCard>

        <GlassCard className="p-4">
          <h4 className="text-xs text-muted-foreground uppercase tracking-wider mb-3">Top Planning Areas</h4>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={topAreas} layout="vertical">
              <XAxis type="number" hide />
              <YAxis type="category" dataKey="name" tick={{ fill: 'hsl(215,20%,55%)', fontSize: 9 }} axisLine={false} tickLine={false} width={70} />
              <Tooltip contentStyle={{ background: 'hsl(225,40%,8%)', border: '1px solid hsl(225,20%,18%)', borderRadius: 8, color: 'hsl(210,40%,93%)' }} />
              <Bar dataKey="count" fill="hsl(38,92%,50%)" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </GlassCard>
      </div>

      {/* Agent Graph */}
      <GlassCard glow="primary" className="p-4 flex-1 min-h-[300px]">
        <h3 className="text-sm font-semibold text-foreground mb-2">Agent Graph — Clustered by Planning Area</h3>
        <div ref={containerRef} className="w-full h-[280px] rounded-lg overflow-hidden bg-background/30">
          <ForceGraph2D
            graphData={graphData}
            width={dims.width}
            height={dims.height}
            nodeColor={(node: { id?: string }) => node.id === 'center' ? 'hsl(193,100%,50%)' : 'hsl(38,92%,50%)'}
            nodeRelSize={5}
            nodeCanvasObjectMode={() => 'after'}
            nodeCanvasObject={(node: { id?: string; name?: string; val?: number; x?: number; y?: number }, ctx, globalScale) => {
              if (node.id === 'center') return;
              const fontSize = 10 / globalScale;
              ctx.font = `${fontSize}px Inter`;
              ctx.textAlign = 'center';
              ctx.fillStyle = 'hsl(215,20%,55%)';
              ctx.fillText(node.name, node.x!, node.y! + (node.val || 3) + fontSize + 2);
            }}
            linkColor={() => 'hsl(225,20%,20%)'}
            linkWidth={1}
            backgroundColor="transparent"
            cooldownTicks={80}
          />
        </div>
      </GlassCard>
    </div>
  );
}
