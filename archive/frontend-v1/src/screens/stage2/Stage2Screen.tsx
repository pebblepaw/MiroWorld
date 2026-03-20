import { PersonaGraph } from '../../components/graphs/PersonaGraph';
import { Panel } from '../../components/layout/Panel';
import type { PopulationArtifact } from '../../types/console';

type Props = {
  population: PopulationArtifact | null;
  agentCount: number;
  planningAreas: string;
  onAgentCountChange: (value: number) => void;
  onPlanningAreasChange: (value: string) => void;
  onSample: () => void;
  isBusy: boolean;
};

export function Stage2Screen({ population, agentCount, planningAreas, onAgentCountChange, onPlanningAreasChange, onSample, isBusy }: Props) {
  return (
    <div className="mk-screen-grid">
      <Panel eyebrow="Stage 2" title="Document-Aware Sampling">
        <div className="mk-form-grid">
          <label className="mk-field">
            <span>Agent Count</span>
            <input type="number" min={10} max={500} value={agentCount} onChange={(event) => onAgentCountChange(Number(event.target.value))} />
          </label>
          <label className="mk-field">
            <span>Planning Areas</span>
            <input value={planningAreas} onChange={(event) => onPlanningAreasChange(event.target.value)} placeholder="Woodlands,Yishun,Tampines" />
          </label>
          <button className="mk-button mk-button--primary" onClick={onSample} disabled={isBusy}>
            {isBusy ? 'Sampling…' : 'Sample Relevant Cohort'}
          </button>
        </div>
        <div className="mk-metric-grid">
          <div className="mk-metric">
            <span>Candidate Pool</span>
            <strong>{population?.candidate_count ?? 0}</strong>
          </div>
          <div className="mk-metric">
            <span>Selected Sample</span>
            <strong>{population?.sample_count ?? 0}</strong>
          </div>
          <div className="mk-metric">
            <span>Representativeness</span>
            <strong>{String(population?.representativeness?.status ?? 'pending')}</strong>
          </div>
        </div>
      </Panel>

      <Panel eyebrow="Agent Graph" title="Sampled Persona Network">
        <PersonaGraph population={population} />
      </Panel>

      <Panel eyebrow="Selection Rationale" title="Why These Personas">
        <div className="mk-list">
          {(population?.sampled_personas ?? []).slice(0, 10).map((row) => (
            <article key={row.agent_id} className="mk-list-card">
              <div className="mk-list-card__title">{row.agent_id}</div>
              <div className="mk-list-card__meta">{String(row.persona.planning_area ?? 'Unknown')} · {String(row.persona.income_bracket ?? 'Unknown')}</div>
              <p>Relevance score: {Number(row.selection_reason.score ?? 0).toFixed(2)}</p>
            </article>
          ))}
        </div>
      </Panel>
    </div>
  );
}
