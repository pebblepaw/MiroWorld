import { useState, useEffect, useRef } from 'react';
import { Play, Loader2, ArrowRight, MessageSquare, ThumbsUp, ThumbsDown, ChevronDown, ChevronUp } from 'lucide-react';
import { useApp } from '@/contexts/AppContext';
import { GlassCard } from '@/components/GlassCard';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { Progress } from '@/components/ui/progress';
import { generateSimPosts, SimPost } from '@/data/mockData';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';

export default function Simulation() {
  const { agents, simulationRounds, setSimulationRounds, setSimPosts, setSimulationComplete, completeStep, setCurrentStep } = useApp();
  const [running, setRunning] = useState(false);
  const [currentRound, setCurrentRound] = useState(0);
  const [posts, setPosts] = useState<SimPost[]>([]);
  const [done, setDone] = useState(false);
  const [expandedPost, setExpandedPost] = useState<string | null>(null);
  const feedRef = useRef<HTMLDivElement>(null);

  const startSimulation = () => {
    setRunning(true);
    setCurrentRound(0);
    setPosts([]);
    const allPosts = generateSimPosts(simulationRounds, agents.length > 0 ? agents : []);
    let round = 1;
    const interval = setInterval(() => {
      const roundPosts = allPosts.filter(p => p.round <= round);
      setPosts(roundPosts);
      setCurrentRound(round);
      if (round >= simulationRounds) {
        clearInterval(interval);
        setRunning(false);
        setDone(true);
        setSimPosts(allPosts);
        setSimulationComplete(true);
      }
      round++;
    }, 1500);
  };

  const handleProceed = () => { completeStep(3); setCurrentStep(4); };

  // Stats
  const totalComments = posts.reduce((s, p) => s + p.commentCount, 0);
  const sentimentData = [
    { name: 'Positive', value: posts.filter(p => p.upvotes > p.downvotes * 3).length || 1 },
    { name: 'Neutral', value: posts.filter(p => p.upvotes <= p.downvotes * 3 && p.upvotes >= p.downvotes).length || 1 },
    { name: 'Negative', value: posts.filter(p => p.upvotes < p.downvotes).length || 1 },
  ];

  return (
    <div className="flex h-full p-6 gap-6 overflow-hidden">
      {/* Main Feed */}
      <div className="flex-1 flex flex-col gap-4 min-w-0">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-foreground">Social Media Simulation</h2>
            <p className="text-sm text-muted-foreground">OASIS engine — simulated Reddit-style discourse</p>
          </div>
          <div className="flex gap-3">
            {!done && (
              <Button onClick={startSimulation} disabled={running} className="bg-primary text-primary-foreground">
                {running ? <><Loader2 className="w-4 h-4 animate-spin" /> Simulating...</> : <><Play className="w-4 h-4" /> Start Simulation</>}
              </Button>
            )}
            {done && (
              <Button onClick={handleProceed} variant="outline" className="border-success/30 text-success hover:bg-success/10">
                <ArrowRight className="w-4 h-4" /> Generate Report
              </Button>
            )}
          </div>
        </div>

        {/* Config */}
        {!running && !done && (
          <GlassCard className="p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-muted-foreground">Simulation Rounds</span>
              <span className="font-mono text-primary font-bold">{simulationRounds}</span>
            </div>
            <Slider value={[simulationRounds]} onValueChange={v => setSimulationRounds(v[0])} min={1} max={10} step={1} />
            <p className="text-[10px] text-muted-foreground mt-2 font-mono">Estimated time: ~{simulationRounds * 8}s</p>
          </GlassCard>
        )}

        {/* Progress */}
        {(running || done) && (
          <GlassCard className="p-3">
            <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
              <span>Round {currentRound}/{simulationRounds}</span>
              <span>{done ? 'Complete' : 'Running...'}</span>
            </div>
            <Progress value={(currentRound / simulationRounds) * 100} className="h-2" />
          </GlassCard>
        )}

        {/* Feed */}
        <div ref={feedRef} className="flex-1 overflow-y-auto space-y-3 scrollbar-thin pr-1">
          {posts.sort((a, b) => b.upvotes - a.upvotes).map(post => (
            <GlassCard key={post.id} className="p-4 animate-slide-up">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                  <span className="text-primary text-xs font-bold">{post.agentName.split(' ').map(n => n[0]).join('').slice(0, 2)}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium text-foreground">{post.agentName}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">{post.agentOccupation}</span>
                    <span className="text-[10px] text-muted-foreground ml-auto font-mono">{post.timestamp}</span>
                  </div>
                  <h4 className="text-sm font-semibold text-foreground mb-1">{post.title}</h4>
                  <p className="text-xs text-muted-foreground leading-relaxed">{post.content}</p>
                  <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1"><ThumbsUp className="w-3 h-3" /> {post.upvotes}</span>
                    <span className="flex items-center gap-1"><ThumbsDown className="w-3 h-3" /> {post.downvotes}</span>
                    <button
                      onClick={() => setExpandedPost(expandedPost === post.id ? null : post.id)}
                      className="flex items-center gap-1 hover:text-primary transition-colors"
                    >
                      <MessageSquare className="w-3 h-3" /> {post.commentCount} comments
                      {expandedPost === post.id ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                    </button>
                  </div>
                  {expandedPost === post.id && (
                    <div className="mt-3 pl-4 border-l border-border space-y-2">
                      {post.comments.map(c => (
                        <div key={c.id} className="text-xs">
                          <span className="font-medium text-foreground">{c.agentName}</span>
                          <span className="text-muted-foreground ml-2">{c.content}</span>
                          <span className="text-muted-foreground/50 ml-2">↑{c.upvotes}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </GlassCard>
          ))}
          {!running && posts.length === 0 && (
            <div className="flex items-center justify-center h-48 text-muted-foreground text-sm">
              Configure rounds and start the simulation
            </div>
          )}
        </div>
      </div>

      {/* Stats Sidebar */}
      <div className="w-64 flex-shrink-0 space-y-4 hidden lg:block">
        <GlassCard className="p-4">
          <h4 className="text-xs uppercase tracking-wider text-muted-foreground mb-3">Live Stats</h4>
          <div className="space-y-3">
            <StatItem label="Total Posts" value={posts.length} />
            <StatItem label="Total Comments" value={totalComments} />
            <StatItem label="Avg Upvotes" value={posts.length ? Math.round(posts.reduce((s, p) => s + p.upvotes, 0) / posts.length) : 0} />
          </div>
        </GlassCard>
        <GlassCard className="p-4">
          <h4 className="text-xs uppercase tracking-wider text-muted-foreground mb-3">Sentiment</h4>
          <ResponsiveContainer width="100%" height={120}>
            <PieChart>
              <Pie data={sentimentData} dataKey="value" innerRadius={30} outerRadius={50} paddingAngle={3}>
                <Cell fill="hsl(160,84%,39%)" />
                <Cell fill="hsl(38,92%,50%)" />
                <Cell fill="hsl(0,72%,51%)" />
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div className="flex justify-center gap-3 text-[10px] text-muted-foreground">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-success" />Positive</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-secondary" />Neutral</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-destructive" />Negative</span>
          </div>
        </GlassCard>
        <GlassCard className="p-4">
          <h4 className="text-xs uppercase tracking-wider text-muted-foreground mb-3">Trending Topics</h4>
          <div className="flex flex-wrap gap-1.5">
            {['BTO Pricing', 'Singles Policy', 'PLH Model', 'CPF Housing', 'Resale Market', 'Waiting Times'].map(t => (
              <span key={t} className="text-[10px] px-2 py-1 rounded-full bg-primary/10 text-primary border border-primary/20">{t}</span>
            ))}
          </div>
        </GlassCard>
      </div>
    </div>
  );
}

function StatItem({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="font-mono text-sm font-bold text-foreground">{value}</span>
    </div>
  );
}
