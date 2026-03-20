import type { SimulationEvent } from '../../types/console';

type Props = {
  events: SimulationEvent[];
};

export function SimulationFeed({ events }: Props) {
  return (
    <div className="mk-feed">
      {events.length === 0 ? (
        <div className="mk-empty">No live events yet.</div>
      ) : (
        events.slice(-16).reverse().map((event, index) => (
          <article key={`${event.event_type}-${index}-${event.timestamp ?? ''}`} className="mk-feed-card">
            <div className="mk-feed-card__meta">
              <span>{event.event_type.replace(/_/g, ' ')}</span>
              <span>Round {event.round_no ?? 0}</span>
            </div>
            <div className="mk-list-card__title">{event.actor_agent_id ?? 'System Event'}</div>
            <p>{event.content ?? event.reaction ?? JSON.stringify(event.metrics ?? {})}</p>
          </article>
        ))
      )}
    </div>
  );
}
