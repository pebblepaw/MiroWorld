import { Panel } from '../../components/layout/Panel';
import type { ReportOpinions } from '../../types/console';

type Props = {
  opinions: ReportOpinions | null;
};

export function Stage4OpinionsScreen({ opinions }: Props) {
  return (
    <div className="mk-screen-grid">
      <Panel eyebrow="Stage 4B" title="Agent Opinions Feed">
        <div className="mk-feed">
          {(opinions?.feed ?? []).slice(0, 16).map((item, index) => (
            <article key={index} className="mk-feed-card">
              <div className="mk-feed-card__meta">
                <span>{String(item.action_type ?? item.round_no ?? 'signal')}</span>
                <span>{String(item.actor_agent_id ?? item.agent_id ?? 'agent')}</span>
              </div>
              <p>{String(item.content ?? item.text ?? item.latest_argument ?? '')}</p>
            </article>
          ))}
        </div>
      </Panel>
      <Panel eyebrow="Influence" title="Most Influential Agents">
        <div className="mk-list">
          {(opinions?.influential_agents ?? []).map((agent, index) => (
            <article key={index} className="mk-list-card">
              <div className="mk-list-card__title">{String(agent.agent_id ?? 'agent')}</div>
              <div className="mk-list-card__meta">{String(agent.planning_area ?? 'Unknown')}</div>
              <p>{String(agent.latest_argument ?? '')}</p>
            </article>
          ))}
        </div>
      </Panel>
    </div>
  );
}
