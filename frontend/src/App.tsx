import { ChangeEvent, useMemo, useState } from 'react';
import type { EChartsOption } from 'echarts';
import EChartPanel from './components/EChartPanel';
import StageSidebar from './components/StageSidebar';
import { getDashboard, reportChat, runSimulation } from './api';

export default function App() {
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

  const scores = dashboard?.simulation;

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

  async function handleRun() {
    setLoading(true);
    setError('');
    try {
      await runSimulation({
        simulation_id: simulationId,
        policy_summary: policySummary,
        agent_count: agentCount,
        rounds,
      });
      const data = await getDashboard(simulationId);
      setDashboard(data);
      setStage('stage4');
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

  return (
    <div className="app-root">
      <header className="topbar glass-card">
        <div>
          <h1>McKAInsey</h1>
          <p>AI-Powered Population Simulation Console</p>
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
              <button onClick={handleAskReport} disabled={loading || !dashboard}>Ask ReportAgent</button>
            </div>
            {error && <p className="error">{error}</p>}
          </section>

          <div className="charts-grid">
            <EChartPanel title="Opinion Shift Timeline" option={approvalOption} />
            <EChartPanel title="Friction by Planning Area" option={frictionOption} />
          </div>
        </section>

        <aside className="context-panel glass-card">
          <h3>Context Panel</h3>
          <p><strong>Simulation:</strong> {simulationId}</p>
          <p><strong>Agent Count:</strong> {dashboard?.simulation?.stats?.agent_count ?? '-'}</p>
          <p><strong>Interactions:</strong> {dashboard?.simulation?.stats?.interactions ?? '-'}</p>
          <p><strong>Approval Pre:</strong> {dashboard?.simulation?.stats?.approval_pre ?? '-'}</p>
          <p><strong>Approval Post:</strong> {dashboard?.simulation?.stats?.approval_post ?? '-'}</p>

          <h4>ReportAgent Reply</h4>
          <p className="chat-reply">{reportReply || 'No query yet.'}</p>
        </aside>
      </main>
    </div>
  );
}
