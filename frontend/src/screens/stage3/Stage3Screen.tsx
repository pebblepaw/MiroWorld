import { useMemo } from 'react';
import { GraphCanvas } from '../../components/graphs/GraphCanvas';
import { Panel } from '../../components/layout/Panel';
import { SimulationFeed } from '../../components/feed/SimulationFeed';
import type { ConsoleMode, SimulationEvent, SimulationState } from '../../types/console';

type Props = {
  mode: ConsoleMode;
  state: SimulationState | null;
  events: SimulationEvent[];
  policySummary: string;
  rounds: number;
  onPolicySummaryChange: (value: string) => void;
  onRoundsChange: (value: number) => void;
  onStart: () => void;
  isBusy: boolean;
};

export function Stage3Screen({ mode, state, events, policySummary, rounds, onPolicySummaryChange, onRoundsChange, onStart, isBusy }: Props) {
  const option = useMemo(() => {
    const metricsEvents = events.filter((event) => event.event_type === 'metrics_updated');
    return {
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: metricsEvents.map((event) => `R${event.round_no ?? 0}`), axisLabel: { color: '#dfe7ff' } },
      yAxis: { type: 'value', axisLabel: { color: '#dfe7ff' } },
      series: [
        {
          type: 'line',
          smooth: true,
          data: metricsEvents.map((event) => Number(event.metrics?.approval ?? 0)),
          lineStyle: { color: '#b9c8ff' },
          areaStyle: { color: 'rgba(185,200,255,0.18)' },
        },
      ],
    };
  }, [events]);

  return (
    <div className="mk-screen-grid mk-screen-grid--stage3">
      <Panel eyebrow="Stage 3" title="Live Simulation Control">
        <div className="mk-form-grid">
          <label className="mk-field">
            <span>Policy Summary</span>
            <textarea value={policySummary} onChange={(event) => onPolicySummaryChange(event.target.value)} rows={6} />
          </label>
          <label className="mk-field">
            <span>Rounds</span>
            <input type="number" min={1} max={30} value={rounds} onChange={(event) => onRoundsChange(Number(event.target.value))} />
          </label>
          <button className="mk-button mk-button--primary" onClick={onStart} disabled={isBusy}>
            {isBusy ? 'Starting…' : `Start ${mode === 'live' ? 'Live OASIS' : 'Demo'} Run`}
          </button>
        </div>
        <div className="mk-metric-grid">
          <div className="mk-metric">
            <span>Status</span>
            <strong>{state?.status ?? 'idle'}</strong>
          </div>
          <div className="mk-metric">
            <span>Events</span>
            <strong>{state?.event_count ?? 0}</strong>
          </div>
          <div className="mk-metric">
            <span>Round</span>
            <strong>{state?.last_round ?? 0}</strong>
          </div>
        </div>
      </Panel>

      <Panel eyebrow="Simulation Feed" title="Agent Discourse Stream">
        <SimulationFeed events={events} />
      </Panel>

      <Panel eyebrow="Opinion Motion" title="Approval Curve">
        <GraphCanvas option={option} />
      </Panel>
    </div>
  );
}
