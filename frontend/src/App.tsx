import { ChangeEvent, useEffect, useMemo, useState } from 'react';
import * as echarts from 'echarts';
import type { EChartsOption } from 'echarts';
import EChartPanel from './components/EChartPanel';
import StageSidebar from './components/StageSidebar';
import {
  agentChat,
  getAgentMemory,
  getDashboard,
  getPlanningAreaGeoJson,
  loadStaticDemoOutput,
  processKnowledge,
  reportChat,
  runSimulation,
  syncMemory,
} from './api';

const reportTabs = ['overview', 'friction-map', 'opinion-flow', 'timeline', 'influential', 'arguments', 'recommendations'] as const;
type ReportTab = (typeof reportTabs)[number];
type BootMode = 'auto' | 'demo' | 'live';

function resolveBootMode(): BootMode {
  const mode = String(import.meta.env.VITE_BOOT_MODE ?? 'auto').toLowerCase();
  if (mode === 'demo' || mode === 'live') return mode;
  return 'auto';
}

export default function App() {
  const bootMode = resolveBootMode();
  const [stage, setStage] = useState('stage1');
  const [simulationId, setSimulationId] = useState('demo-budget-2026');
  const [policySummary, setPolicySummary] = useState('FY2026 budget package focused on cost-of-living support, transport affordability, and senior support.');
  const [agentCount, setAgentCount] = useState(50);
  const [rounds, setRounds] = useState(10);
  const [dashboard, setDashboard] = useState<any>(null);
  const [reportReply, setReportReply] = useState('');
  const [query, setQuery] = useState('What is the highest-friction planning area?');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [memoryStatus, setMemoryStatus] = useState('Not synced');
  const [mapReady, setMapReady] = useState(false);
  const [reportTab, setReportTab] = useState<ReportTab>('overview');
  const [selectedArea, setSelectedArea] = useState<string | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<string>('');
  const [agentMessage, setAgentMessage] = useState('What drove your final stance after deliberation?');
  const [agentReply, setAgentReply] = useState('');
  const [agentMemoryRows, setAgentMemoryRows] = useState<any[]>([]);
  const [graphView, setGraphView] = useState<'knowledge' | 'persona'>('knowledge');
  const [knowledgeSnapshot, setKnowledgeSnapshot] = useState<any>(null);
  const [bootstrapStatus, setBootstrapStatus] = useState('');

  const scores = dashboard?.simulation;

  async function loadLiveDashboard() {
    const live = await getDashboard(simulationId);
    setDashboard(live);
    const top = live?.report?.influential_agents?.[0]?.agent_id;
    if (top) setSelectedAgent(top);
    setStage('stage4');
    setBootstrapStatus('Loaded live dashboard data.');
    return true;
  }

  async function loadDemoCache() {
    const cached = await loadStaticDemoOutput();
    if (!cached?.dashboard) {
      return false;
    }
    setDashboard(cached.dashboard);
    setKnowledgeSnapshot(cached.knowledge ?? null);
    setMemoryStatus(cached?.memory_sync?.zep_enabled ? 'Synced to Zep' : 'Sync fallback mode');
    const top = cached?.report?.influential_agents?.[0]?.agent_id;
    if (top) setSelectedAgent(top);
    setStage('stage4');
    setBootstrapStatus('Loaded cached demo dataset.');
    return true;
  }

  useEffect(() => {
    async function bootstrapDemo() {
      async function tryLoadLive() {
        try {
          return await loadLiveDashboard();
        } catch {
          return false;
        }
      }

      async function tryLoadCached() {
        try {
          return await loadDemoCache();
        } catch {
          return false;
        }
      }

      if (bootMode === 'demo') {
        const demoOk = await tryLoadCached();
        if (!demoOk) {
          await tryLoadLive();
        }
        return;
      }

      if (bootMode === 'live') {
        const liveOk = await tryLoadLive();
        if (!liveOk) {
          await tryLoadCached();
        }
        return;
      }

      const liveOk = await tryLoadLive();
      if (!liveOk) {
        await tryLoadCached();
      }
    }

    void bootstrapDemo();
  }, [simulationId, bootMode]);

  useEffect(() => {
    async function bootstrapGeoJson() {
      try {
        const geoJson = await getPlanningAreaGeoJson();
        echarts.registerMap('sg-planning-areas', geoJson as any);
        setMapReady(true);
      } catch {
        setMapReady(false);
      }
    }

    void bootstrapGeoJson();
  }, []);

  const approvalOption = useMemo<EChartsOption>(() => {
    const pre = (scores?.stage3a_scores ?? []).slice(0, 10);
    const post = (scores?.stage3b_scores ?? []).slice(0, 10);
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: { data: ['Stage 3a', 'Stage 3b'], textStyle: { color: '#ddd' } },
      xAxis: { type: 'category', data: pre.map((_: number, i: number) => `A${i + 1}`), axisLabel: { color: '#aaa' } },
      yAxis: { type: 'value', min: 1, max: 10, axisLabel: { color: '#aaa' } },
      series: [
        { name: 'Stage 3a', type: 'line', data: pre, smooth: true, lineStyle: { color: '#f97316' } },
        { name: 'Stage 3b', type: 'line', data: post, smooth: true, lineStyle: { color: '#8b5cf6' } },
      ],
    };
  }, [scores]);

  const frictionOption = useMemo<EChartsOption>(() => {
    const rows = dashboard?.friction_map ?? [];
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      xAxis: { type: 'category', data: rows.map((r: any) => r.planning_area), axisLabel: { color: '#aaa', rotate: 20 } },
      yAxis: { type: 'value', axisLabel: { color: '#aaa' } },
      series: [
        {
          type: 'bar',
          data: rows.map((r: any) => r.friction),
          itemStyle: {
            color: '#ef4444',
            borderRadius: [6, 6, 0, 0],
          },
        },
      ],
    };
  }, [dashboard]);

  const sankeyOption = useMemo<EChartsOption>(() => {
    const flow = dashboard?.opinion_flow;
    if (!flow) {
      return {
        title: { text: 'Opinion Flow', textStyle: { color: '#ddd' } },
      };
    }

    return {
      tooltip: { trigger: 'item' },
      series: [
        {
          type: 'sankey',
          emphasis: { focus: 'adjacency' },
          lineStyle: { color: 'gradient', curveness: 0.45 },
          data: flow.nodes,
          links: flow.links,
          label: { color: '#ddd' },
        },
      ],
    };
  }, [dashboard]);

  const heatmapOption = useMemo<EChartsOption>(() => {
    const rows = dashboard?.heatmap_matrix ?? [];
    const areas = rows.map((r: any) => r.planning_area);
    const values = rows.map((r: any, index: number) => [index, 0, r.friction]);

    return {
      tooltip: {
        position: 'top',
        formatter: (params: any) => {
          const row = rows[params.data?.[0]];
          if (!row) return '';
          return `${row.planning_area}<br/>Friction: ${row.friction}<br/>Avg Post Opinion: ${row.avg_post_opinion}`;
        },
      },
      grid: { height: '55%', top: '18%' },
      xAxis: {
        type: 'category',
        data: areas,
        splitArea: { show: false },
        axisLabel: { color: '#aaa', rotate: 30 },
      },
      yAxis: {
        type: 'category',
        data: ['Friction Index'],
        splitArea: { show: false },
        axisLabel: { color: '#aaa' },
      },
      visualMap: {
        min: 0,
        max: 1,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: 0,
        inRange: {
          color: ['#14532d', '#65a30d', '#eab308', '#f97316', '#b91c1c'],
        },
        textStyle: { color: '#ddd' },
      },
      series: [
        {
          name: 'Friction',
          type: 'heatmap',
          data: values,
          label: { show: false },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(0, 0, 0, 0.5)',
            },
          },
        },
      ],
    };
  }, [dashboard]);

  const mapOption = useMemo<EChartsOption>(() => {
    if (!mapReady) {
      return {
        title: { text: 'Singapore Planning Area Map', textStyle: { color: '#ddd' } },
      };
    }

    const rows = dashboard?.heatmap_matrix ?? [];
    const byArea = new Map<string, number>();
    for (const row of rows) {
      byArea.set(String(row.planning_area).toUpperCase(), Number(row.friction));
    }

    return {
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          const value = params?.value;
          const num = typeof value === 'number' ? value : Number(value ?? 0);
          return `${params?.name ?? 'Unknown'}<br/>Friction: ${num.toFixed(3)}`;
        },
      },
      visualMap: {
        min: 0,
        max: 1,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: 0,
        inRange: {
          color: ['#14532d', '#65a30d', '#eab308', '#f97316', '#b91c1c'],
        },
        textStyle: { color: '#ddd' },
      },
      series: [
        {
          type: 'map',
          map: 'sg-planning-areas',
          name: 'Planning Area Friction',
          roam: true,
          emphasis: { label: { color: '#fff' } },
          data: Array.from(byArea.entries()).map(([name, value]) => ({ name, value })),
        },
      ],
    };
  }, [dashboard, mapReady]);

  const areaDetails = useMemo(() => {
    const rows = dashboard?.heatmap_matrix ?? [];
    if (!selectedArea) return null;
    return rows.find((row: any) => String(row.planning_area).toUpperCase() === selectedArea.toUpperCase()) ?? null;
  }, [dashboard, selectedArea]);

  const knowledgeGraphOption = useMemo<EChartsOption>(() => {
    const summary = String(knowledgeSnapshot?.summary ?? '').trim();
    const focus = String(knowledgeSnapshot?.demographic_context ?? '').trim();
    const friction = (dashboard?.report?.friction_by_planning_area ?? []).slice(0, 6);
    const influential = (dashboard?.report?.influential_agents ?? []).slice(0, 8);

    const nodes: Array<{ name: string; value?: number; symbolSize?: number; itemStyle?: { color?: string } }> = [
      { name: 'Policy Document', symbolSize: 56, itemStyle: { color: '#f59e0b' } },
    ];
    const links: Array<{ source: string; target: string; value?: number }> = [];

    if (focus) {
      nodes.push({ name: 'Demographic Focus', symbolSize: 42, itemStyle: { color: '#06b6d4' } });
      links.push({ source: 'Policy Document', target: 'Demographic Focus', value: 1 });
    }

    for (const area of friction) {
      const areaName = String(area.planning_area || 'Unknown Area');
      nodes.push({ name: areaName, symbolSize: 28, itemStyle: { color: '#ef4444' } });
      links.push({ source: focus ? 'Demographic Focus' : 'Policy Document', target: areaName, value: Number(area.friction_index || 0) });
    }

    for (const agent of influential) {
      const agentName = String(agent.agent_id || 'agent');
      const areaName = String(agent.planning_area || 'Unknown Area');
      const score = Number(agent.influence_score || 0);
      nodes.push({ name: agentName, value: score, symbolSize: 18 + Math.min(30, score * 60), itemStyle: { color: '#8b5cf6' } });
      if (nodes.find((node) => node.name === areaName)) {
        links.push({ source: areaName, target: agentName, value: score });
      } else {
        links.push({ source: 'Policy Document', target: agentName, value: score });
      }
    }

    if (!summary && !focus && friction.length === 0 && influential.length === 0) {
      return {
        title: { text: 'Knowledge Graph (No data loaded)', textStyle: { color: '#ddd' } },
      };
    }

    return {
      tooltip: { trigger: 'item' },
      series: [
        {
          type: 'graph',
          layout: 'force',
          roam: true,
          data: nodes,
          links,
          force: {
            repulsion: 240,
            edgeLength: [50, 160],
          },
          label: { show: true, color: '#ddd' },
          lineStyle: { color: 'source', curveness: 0.18 },
        },
      ],
    };
  }, [dashboard, knowledgeSnapshot]);

  const personaGraphOption = useMemo<EChartsOption>(() => {
    const influential = (dashboard?.report?.influential_agents ?? []).slice(0, 18);
    if (influential.length === 0) {
      return {
        title: { text: 'Persona Graph (No influential agents yet)', textStyle: { color: '#ddd' } },
      };
    }

    const nodes: Array<{ name: string; category: number; symbolSize: number; value?: number; itemStyle?: { color?: string } }> = [];
    const links: Array<{ source: string; target: string; value?: number }> = [];
    const areaSeen = new Set<string>();

    for (const agent of influential) {
      const agentId = String(agent.agent_id || 'agent');
      const area = String(agent.planning_area || 'Unknown Area');
      const score = Number(agent.influence_score || 0);

      if (!areaSeen.has(area)) {
        nodes.push({ name: area, category: 0, symbolSize: 30, itemStyle: { color: '#06b6d4' } });
        areaSeen.add(area);
      }

      nodes.push({ name: agentId, category: 1, symbolSize: 16 + Math.min(28, score * 60), value: score, itemStyle: { color: '#22c55e' } });
      links.push({ source: area, target: agentId, value: score });
    }

    return {
      tooltip: { trigger: 'item' },
      legend: [{ data: ['Planning Areas', 'Influential Agents'], textStyle: { color: '#ddd' } }],
      series: [
        {
          type: 'graph',
          layout: 'force',
          roam: true,
          categories: [{ name: 'Planning Areas' }, { name: 'Influential Agents' }],
          data: nodes,
          links,
          force: { repulsion: 260, edgeLength: [45, 130] },
          label: { show: true, color: '#ddd' },
          lineStyle: { color: '#6b7280', opacity: 0.8 },
        },
      ],
    };
  }, [dashboard]);

  async function handleRun() {
    setLoading(true);
    setError('');
    try {
      const knowledge = await processKnowledge({
        simulation_id: simulationId,
        use_default_demo_document: true,
        demographic_focus: 'Singapore FY2026 budget policy reactions by planning area and income cohorts',
      });
      setKnowledgeSnapshot(knowledge);
      await runSimulation({
        simulation_id: simulationId,
        policy_summary: policySummary,
        agent_count: agentCount,
        rounds,
      });
      const sync = await syncMemory(simulationId);
      setMemoryStatus(sync?.zep_enabled ? `Synced ${sync.synced_events} events to Zep` : `Synced ${sync.synced_events} events (fallback)`);
      const data = await getDashboard(simulationId);
      setDashboard(data);
      const top = data?.report?.influential_agents?.[0]?.agent_id;
      if (top) setSelectedAgent(top);
      setStage('stage4');
      setReportTab('overview');
      setBootstrapStatus('Completed live run and loaded Stage 4 report.');
    } catch (err: any) {
      setError(String(err.message ?? err));
    } finally {
      setLoading(false);
    }
  }

  async function handleAskReport() {
    setLoading(true);
    setError('');
    try {
      const reply = await reportChat(simulationId, query);
      setReportReply(reply.response);
      setStage('stage5');
    } catch (err: any) {
      setError(String(err.message ?? err));
    } finally {
      setLoading(false);
    }
  }

  async function handleAskAgent() {
    if (!selectedAgent) return;
    setLoading(true);
    setError('');
    try {
      const memory = await getAgentMemory(simulationId, selectedAgent);
      setAgentMemoryRows(memory.episodes ?? []);
      const reply = await agentChat(simulationId, selectedAgent, agentMessage);
      setAgentReply(reply.response ?? 'No response returned.');
      setStage('stage5');
    } catch (err: any) {
      setError(String(err.message ?? err));
    } finally {
      setLoading(false);
    }
  }

  const onMapClick = (params: any) => {
    if (params?.name) {
      setSelectedArea(String(params.name));
      setReportTab('friction-map');
    }
  };

  const influentialAgents = dashboard?.report?.influential_agents ?? [];
  const recommendations = dashboard?.report?.recommendations ?? [];
  const argsFor = dashboard?.report?.key_arguments_for ?? [];
  const argsAgainst = dashboard?.report?.key_arguments_against ?? [];

  return (
    <div className="app-root">
      <header className="topbar glass-card">
        <div>
          <h1>McKAInsey</h1>
          <p>AI-Powered Population Simulation Console</p>
        </div>
        <div className="top-actions">
          <button className={graphView === 'knowledge' ? 'mode-btn active' : 'mode-btn'} onClick={() => setGraphView('knowledge')}>Knowledge Graph</button>
          <button className={graphView === 'persona' ? 'mode-btn active' : 'mode-btn'} onClick={() => setGraphView('persona')}>Persona Graph</button>
        </div>
        <div className="status-pill">{loading ? 'Running' : 'Idle'} | {stage.toUpperCase()}</div>
      </header>

      <main className="layout">
        <StageSidebar active={stage} onSelect={setStage} />

        <section className="main-panel">
          <section className="glass-card controls">
            <h2>Scenario Setup</h2>
            <div className="grid-2">
              <label>
                Simulation ID
                <input value={simulationId} onChange={(e: ChangeEvent<HTMLInputElement>) => setSimulationId(e.target.value)} />
              </label>
              <label>
                Agent Count
                <input type="number" min={10} max={500} value={agentCount} onChange={(e: ChangeEvent<HTMLInputElement>) => setAgentCount(Number(e.target.value))} />
              </label>
              <label>
                Deliberation Rounds
                <input type="number" min={1} max={20} value={rounds} onChange={(e: ChangeEvent<HTMLInputElement>) => setRounds(Number(e.target.value))} />
              </label>
              <label>
                Report Query
                <input value={query} onChange={(e: ChangeEvent<HTMLInputElement>) => setQuery(e.target.value)} />
              </label>
            </div>
            <label>
              Policy Summary
              <textarea rows={4} value={policySummary} onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setPolicySummary(e.target.value)} />
            </label>
            <div className="actions">
              <button onClick={handleRun} disabled={loading}>Run Stage 3 Simulation</button>
              <button
                onClick={async () => {
                  setLoading(true);
                  setError('');
                  try {
                    await loadLiveDashboard();
                  } catch (err: any) {
                    setError(String(err.message ?? err));
                  } finally {
                    setLoading(false);
                  }
                }}
                disabled={loading}
              >
                Load Live Dashboard
              </button>
              <button
                onClick={async () => {
                  setLoading(true);
                  setError('');
                  try {
                    const ok = await loadDemoCache();
                    if (!ok) {
                      setError('Demo cache missing dashboard payload.');
                    }
                  } catch (err: any) {
                    setError(String(err.message ?? err));
                  } finally {
                    setLoading(false);
                  }
                }}
                disabled={loading}
              >
                Load Demo Cache
              </button>
              <button onClick={handleAskReport} disabled={loading || !dashboard}>Ask ReportAgent</button>
              <button onClick={() => setStage('stage4')} disabled={!dashboard}>Open Report</button>
              <button onClick={() => setStage('stage5')} disabled={!dashboard}>Open Deep Dive</button>
            </div>
            {bootstrapStatus && <p>{bootstrapStatus}</p>}
            {error && <p className="error">{error}</p>}
          </section>

          <section className="glass-card report-zone">
            <h3>{graphView === 'knowledge' ? 'Knowledge Graph' : 'Persona Graph'}</h3>
            {graphView === 'knowledge' ? (
              <EChartPanel title="Policy & Cohort Knowledge Graph" option={knowledgeGraphOption} />
            ) : (
              <EChartPanel title="Influence Persona Graph" option={personaGraphOption} />
            )}
          </section>

          {stage !== 'stage5' && (
            <section className="glass-card report-zone">
              {!dashboard && (
                <section className="summary-box">
                  <h4>Stage 4 Report Data Not Loaded</h4>
                  <p>Use "Load Live Dashboard" or "Load Demo Cache" above to populate report tabs.</p>
                </section>
              )}

              {dashboard && (
                <>
                <div className="report-tabs">
                {reportTabs.map((tab) => (
                  <button key={tab} className={reportTab === tab ? 'pill active' : 'pill'} onClick={() => setReportTab(tab)}>
                    {tab.replace('-', ' ')}
                  </button>
                ))}
              </div>

              {reportTab === 'overview' && (
                <div className="overview-grid">
                  <div className="stat-card">
                    <span>Pre Approval</span>
                    <strong>{dashboard?.report?.approval_rates?.stage3a ?? '-'}</strong>
                  </div>
                  <div className="stat-card">
                    <span>Post Approval</span>
                    <strong>{dashboard?.report?.approval_rates?.stage3b ?? '-'}</strong>
                  </div>
                  <div className="stat-card">
                    <span>Approval Delta</span>
                    <strong>{dashboard?.report?.approval_rates?.delta ?? '-'}</strong>
                  </div>
                  <div className="stat-card">
                    <span>Most Friction</span>
                    <strong>{dashboard?.report?.friction_by_planning_area?.[0]?.planning_area ?? '-'}</strong>
                  </div>
                  <div className="summary-box">
                    <h4>Executive Summary</h4>
                    <p>{dashboard?.report?.executive_summary ?? 'No report summary yet.'}</p>
                  </div>
                </div>
              )}

              {reportTab === 'friction-map' && (
                <div className="charts-grid">
                  <EChartPanel title="Singapore Planning Area Friction Map" option={mapOption} onItemClick={onMapClick} />
                  <EChartPanel title="Friction Heatmap Matrix" option={heatmapOption} />
                  <EChartPanel title="Friction by Planning Area" option={frictionOption} />
                  <section className="glass-card report-list">
                    <h3>Area Drilldown</h3>
                    <p><strong>Selected:</strong> {selectedArea ?? 'Click a map area to inspect details.'}</p>
                    {areaDetails && (
                      <ul>
                        <li>Friction: {areaDetails.friction}</li>
                        <li>Avg post opinion: {areaDetails.avg_post_opinion}</li>
                        <li>Cohort size: {areaDetails.cohort_size}</li>
                      </ul>
                    )}
                  </section>
                </div>
              )}

              {reportTab === 'opinion-flow' && (
                <div className="charts-grid">
                  <EChartPanel title="Opinion Flow Sankey" option={sankeyOption} />
                </div>
              )}

              {reportTab === 'timeline' && (
                <div className="charts-grid">
                  <EChartPanel title="Opinion Shift Timeline" option={approvalOption} />
                </div>
              )}

              {reportTab === 'influential' && (
                <section className="glass-card report-list">
                  <h3>Top Influential Agents</h3>
                  {influentialAgents.length === 0 && <p>No influential agents found yet.</p>}
                  {influentialAgents.map((agent: any) => (
                    <article key={agent.agent_id} className="list-item">
                      <div>
                        <strong>{agent.agent_id}</strong>
                        <p>{agent.occupation} in {agent.planning_area} | {agent.income_bracket}</p>
                        <p>{agent.latest_argument}</p>
                      </div>
                      <span className="badge">Influence {agent.influence_score}</span>
                    </article>
                  ))}
                </section>
              )}

              {reportTab === 'arguments' && (
                <div className="argument-grid">
                  <section className="glass-card report-list">
                    <h3>Arguments For</h3>
                    {argsFor.slice(0, 10).map((item: any, idx: number) => (
                      <article key={`for-${idx}`} className="list-item">
                        <div>
                          <strong>{item.agent_id}</strong>
                          <p>{item.text}</p>
                        </div>
                        <span className="badge">+{item.strength}</span>
                      </article>
                    ))}
                  </section>
                  <section className="glass-card report-list">
                    <h3>Arguments Against</h3>
                    {argsAgainst.slice(0, 10).map((item: any, idx: number) => (
                      <article key={`against-${idx}`} className="list-item">
                        <div>
                          <strong>{item.agent_id}</strong>
                          <p>{item.text}</p>
                        </div>
                        <span className="badge">-{item.strength}</span>
                      </article>
                    ))}
                  </section>
                </div>
              )}

              {reportTab === 'recommendations' && (
                <section className="glass-card report-list">
                  <h3>Strategic Recommendations</h3>
                  {recommendations.length === 0 && <p>No recommendations generated yet.</p>}
                  {recommendations.map((rec: any, idx: number) => (
                    <article key={`rec-${idx}`} className="list-item">
                      <div>
                        <strong>{rec.title}</strong>
                        <p>{rec.rationale}</p>
                        <p><em>Target:</em> {rec.target_demographic}</p>
                        <ul>
                          {(rec.execution_plan ?? []).map((step: string, stepIdx: number) => (
                            <li key={`step-${idx}-${stepIdx}`}>{step}</li>
                          ))}
                        </ul>
                      </div>
                      <span className="badge">Conf {rec.confidence ?? '-'}</span>
                    </article>
                  ))}
                </section>
              )}
                </>
              )}
            </section>
          )}

          {stage === 'stage5' && (
            <section className="glass-card report-zone">
              <h3>Interactive Deep Dive</h3>
              <div className="deep-grid">
                <section className="glass-card deep-pane">
                  <h4>ReportAgent Chat</h4>
                  <label>
                    Ask ReportAgent
                    <input value={query} onChange={(e: ChangeEvent<HTMLInputElement>) => setQuery(e.target.value)} />
                  </label>
                  <button onClick={handleAskReport} disabled={loading || !dashboard}>Send</button>
                  <p className="chat-reply">{reportReply || 'No query yet.'}</p>
                </section>

                <section className="glass-card deep-pane">
                  <h4>Individual Agent Chat</h4>
                  <label>
                    Agent
                    <select value={selectedAgent} onChange={(e) => setSelectedAgent(e.target.value)}>
                      <option value="">Select agent</option>
                      {influentialAgents.map((agent: any) => (
                        <option key={agent.agent_id} value={agent.agent_id}>{agent.agent_id}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Ask Agent
                    <input value={agentMessage} onChange={(e: ChangeEvent<HTMLInputElement>) => setAgentMessage(e.target.value)} />
                  </label>
                  <button onClick={handleAskAgent} disabled={loading || !selectedAgent}>Send</button>
                  <p className="chat-reply">{agentReply || 'No agent query yet.'}</p>
                </section>

                <section className="glass-card deep-pane">
                  <h4>Agent Memory Trace</h4>
                  {agentMemoryRows.length === 0 && <p>No memory loaded.</p>}
                  <div className="memory-list">
                    {agentMemoryRows.slice(-15).map((row: any) => (
                      <article key={row.id} className="memory-item">
                        <strong>Round {row.round_no} • {row.action_type}</strong>
                        <p>{row.content || '-'}</p>
                      </article>
                    ))}
                  </div>
                </section>
              </div>
            </section>
          )}
        </section>

        <aside className="context-panel glass-card">
          <h3>Context Panel</h3>
          <p><strong>Graph View:</strong> {graphView === 'knowledge' ? 'Knowledge Graph' : 'Persona Graph'}</p>
          <p><strong>Simulation:</strong> {simulationId}</p>
          <p><strong>Agent Count:</strong> {dashboard?.simulation?.stats?.agent_count ?? '-'}</p>
          <p><strong>Interactions:</strong> {dashboard?.simulation?.stats?.interactions ?? '-'}</p>
          <p><strong>Approval Pre:</strong> {dashboard?.simulation?.stats?.approval_pre ?? '-'}</p>
          <p><strong>Approval Post:</strong> {dashboard?.simulation?.stats?.approval_post ?? '-'}</p>
          <p><strong>Memory Sync:</strong> {memoryStatus}</p>
          <p><strong>Runtime:</strong> {dashboard?.simulation?.runtime ?? dashboard?.simulation?.stats?.runtime ?? '-'}</p>
          <p><strong>Boot Mode:</strong> {bootMode}</p>
          <p><strong>Top Friction Area:</strong> {dashboard?.report?.friction_by_planning_area?.[0]?.planning_area ?? '-'}</p>

          <h4>ReportAgent Reply</h4>
          <p className="chat-reply">{reportReply || 'No query yet.'}</p>
        </aside>
      </main>
    </div>
  );
}
