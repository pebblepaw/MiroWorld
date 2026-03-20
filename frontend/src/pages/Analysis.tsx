import { useState } from 'react';
import { Map as MapIcon, FileText, TrendingUp, ThumbsUp, MessageSquare } from 'lucide-react';
import { useApp } from '@/contexts/AppContext';
import { GlassCard } from '@/components/GlassCard';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { mockReport, planningAreaApproval } from '@/data/mockData';
import { ArrowRight } from 'lucide-react';
import { MapContainer, TileLayer, CircleMarker, Tooltip } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

const planningAreaCoordinates: Record<string, [number, number]> = {
  'Ang Mo Kio': [1.3691, 103.8454],
  'Bedok': [1.3236, 103.9273],
  'Bishan': [1.3526, 103.8352],
  'Bukit Batok': [1.3590, 103.7637],
  'Bukit Merah': [1.2819, 103.8239],
  'Bukit Panjang': [1.3774, 103.7719],
  'Bukit Timah': [1.3294, 103.8021],
  'Clementi': [1.3162, 103.7649],
  'Geylang': [1.3201, 103.8918],
  'Hougang': [1.3713, 103.8925],
  'Jurong East': [1.3329, 103.7436],
  'Jurong West': [1.3404, 103.7090],
  'Kallang': [1.3115, 103.8750],
  'Marine Parade': [1.3020, 103.9046],
  'Pasir Ris': [1.3721, 103.9474],
  'Punggol': [1.3984, 103.9072],
  'Queenstown': [1.2942, 103.8060],
  'Sembawang': [1.4491, 103.8185],
  'Sengkang': [1.3868, 103.8914],
  'Serangoon': [1.3554, 103.8679],
  'Tampines': [1.3496, 103.9568],
  'Toa Payoh': [1.3343, 103.8563],
  'Woodlands': [1.4360, 103.7861],
  'Yishun': [1.4304, 103.8354],
  'Tengah': [1.3625, 103.7290],
  'Choa Chu Kang': [1.3840, 103.7470],
};

export default function Analysis() {
  const { completeStep, setCurrentStep, simPosts } = useApp();

  const handleProceed = () => { completeStep(4); setCurrentStep(5); };

  return (
    <div className="flex flex-col h-full p-6 gap-4 overflow-hidden">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-foreground">Analysis Dashboard</h2>
          <p className="text-sm text-muted-foreground">Comprehensive analysis of simulation results</p>
        </div>
        <Button onClick={handleProceed} variant="outline" className="border-success/30 text-success hover:bg-success/10">
          <ArrowRight className="w-4 h-4" /> Chat with Agents
        </Button>
      </div>

      <Tabs defaultValue="map" className="flex-1 flex flex-col overflow-hidden">
        <TabsList className="bg-muted/30 border border-border self-start">
          <TabsTrigger value="map" className="data-[state=active]:bg-primary/10 data-[state=active]:text-primary gap-1.5"><MapIcon className="w-3.5 h-3.5" /> Planning Area Map</TabsTrigger>
          <TabsTrigger value="report" className="data-[state=active]:bg-primary/10 data-[state=active]:text-primary gap-1.5"><FileText className="w-3.5 h-3.5" /> Report & Insights</TabsTrigger>
          <TabsTrigger value="posts" className="data-[state=active]:bg-primary/10 data-[state=active]:text-primary gap-1.5"><TrendingUp className="w-3.5 h-3.5" /> Influential Posts</TabsTrigger>
        </TabsList>

        <TabsContent value="map" className="flex-1 overflow-y-auto scrollbar-thin mt-4">
          <PlanningAreaMap />
        </TabsContent>
        <TabsContent value="report" className="flex-1 overflow-y-auto scrollbar-thin mt-4">
          <ReportView />
        </TabsContent>
        <TabsContent value="posts" className="flex-1 overflow-y-auto scrollbar-thin mt-4">
          <InfluentialPosts posts={simPosts} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function PlanningAreaMap() {
  const [selected, setSelected] = useState<string | null>(null);
  const areas = Object.entries(planningAreaApproval);
  const overall = Math.round(areas.reduce((s, [, v]) => s + v.approval, 0) / areas.length);

  const getMarkerColor = (approval: number) => {
    if (approval >= 60) return '#10b981'; // success
    if (approval >= 45) return '#f59e0b'; // secondary/warning
    return '#ef4444'; // destructive
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[600px]">
      <div className="lg:col-span-2 h-full">
        <GlassCard glow="primary" className="p-6 h-full flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-foreground">Singapore Planning Areas — Sentiment Heatmap</h3>
            <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
              <span className="flex items-center gap-1"><span className="w-3 h-2 rounded-sm bg-destructive" />Low</span>
              <span className="flex items-center gap-1"><span className="w-3 h-2 rounded-sm bg-secondary" />Mid</span>
              <span className="flex items-center gap-1"><span className="w-3 h-2 rounded-sm bg-success" />High</span>
            </div>
          </div>
          <div className="flex-1 rounded-xl overflow-hidden border border-border relative z-0">
            <MapContainer center={[1.3521, 103.8198]} zoom={11} className="w-full h-full" zoomControl={false}>
              <TileLayer
                attribution='<img src="https://www.onemap.gov.sg/web-assets/images/logo/om_logo.png" style="height:20px;width:20px;"/>&nbsp;<a href="https://www.sla.gov.sg/" target="_blank" rel="noopener noreferrer">Singapore Land Authority</a>'
                url="https://maps-{s}.onemap.sg/v3/Night/{z}/{x}/{y}.png"
              />
              {areas.map(([name, data]) => {
                const coords = planningAreaCoordinates[name];
                if (!coords) return null;
                const isSelected = selected === name;
                return (
                  <CircleMarker
                    key={name}
                    center={coords}
                    radius={isSelected ? 12 : 8}
                    pathOptions={{
                      color: isSelected ? '#ffffff' : getMarkerColor(data.approval),
                      fillColor: getMarkerColor(data.approval),
                      fillOpacity: 0.8,
                      weight: isSelected ? 3 : 1
                    }}
                    eventHandlers={{
                      click: () => setSelected(selected === name ? null : name)
                    }}
                  >
                    <Tooltip direction="top" offset={[0, -10]} opacity={1}>
                      <div className="text-center font-sans">
                        <div className="font-bold text-xs">{name}</div>
                        <div className="text-sm">{data.approval}%</div>
                      </div>
                    </Tooltip>
                  </CircleMarker>
                );
              })}
            </MapContainer>
          </div>
        </GlassCard>
      </div>
      <div className="space-y-4">
        <GlassCard className="p-5 text-center">
          <div className="text-3xl font-mono font-bold text-primary glow-text">{overall}%</div>
          <div className="text-xs text-muted-foreground mt-1">Overall Approval</div>
        </GlassCard>
        {selected && (
          <GlassCard glow="secondary" className="p-4 animate-slide-up">
            <h4 className="text-sm font-semibold text-foreground mb-2">{selected}</h4>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between"><span className="text-muted-foreground">Approval</span><span className="text-foreground font-mono">{planningAreaApproval[selected].approval}%</span></div>
              <Progress value={planningAreaApproval[selected].approval} className="h-2" />
              <div className="flex justify-between"><span className="text-muted-foreground">Agents</span><span className="text-foreground font-mono">{planningAreaApproval[selected].agentCount}</span></div>
            </div>
          </GlassCard>
        )}
      </div>
    </div>
  );
}

function ReportView() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2">
        <GlassCard className="p-6">
          <h3 className="text-lg font-bold text-foreground mb-1">{mockReport.title}</h3>
          <p className="text-xs text-muted-foreground mb-6">{mockReport.date}</p>
          <div className="space-y-6">
            {mockReport.sections.map((s, i) => (
              <div key={i}>
                <h4 className="text-sm font-bold text-primary mb-2">{s.heading}</h4>
                <div className="text-xs text-muted-foreground leading-relaxed whitespace-pre-line">{s.content}</div>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>
      <div className="space-y-3">
        <h4 className="text-xs uppercase tracking-wider text-muted-foreground">Key Insights</h4>
        {mockReport.keyInsights.map((insight, i) => (
          <GlassCard key={i} glow={i === 0 ? 'primary' : 'none'} className="p-4">
            <div className="flex items-start gap-3">
              <span className="text-2xl">{insight.icon}</span>
              <div>
                <h5 className="text-sm font-semibold text-foreground">{insight.headline}</h5>
                <p className="text-xs text-muted-foreground mt-1">{insight.description}</p>
              </div>
            </div>
          </GlassCard>
        ))}
      </div>
    </div>
  );
}

function InfluentialPosts({ posts }: { posts: { id: string; title: string; content: string; agentName: string; agentOccupation: string; upvotes: number; commentCount: number }[] }) {
  const sorted = [...posts].sort((a, b) => b.upvotes - a.upvotes).slice(0, 10);

  if (sorted.length === 0) {
    return <div className="text-center text-muted-foreground py-12">Run the simulation first to see influential posts</div>;
  }

  return (
    <div className="space-y-3">
      {sorted.map((post, i) => (
        <GlassCard key={post.id} className="p-4">
          <div className="flex items-start gap-4">
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 font-mono font-bold text-sm ${i < 3 ? 'bg-primary/20 text-primary' : 'bg-muted text-muted-foreground'}`}>
              #{i + 1}
            </div>
            <div className="flex-1 min-w-0">
              <h4 className="text-sm font-semibold text-foreground">{post.title}</h4>
              <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{post.content}</p>
              <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                <span>{post.agentName} · {post.agentOccupation}</span>
                <span className="flex items-center gap-1"><ThumbsUp className="w-3 h-3" />{post.upvotes}</span>
                <span className="flex items-center gap-1"><MessageSquare className="w-3 h-3" />{post.commentCount}</span>
              </div>
              <div className="mt-2">
                <Progress value={Math.min(100, (post.upvotes / 500) * 100)} className="h-1.5" />
              </div>
            </div>
          </div>
        </GlassCard>
      ))}
    </div>
  );
}
