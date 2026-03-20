import { Panel } from '../../components/layout/Panel';
import { FrictionMap } from '../../components/map/FrictionMap';
import type { ReportFrictionMap } from '../../types/console';

type Props = {
  friction: ReportFrictionMap | null;
  mapReady: boolean;
};

export function Stage4FrictionScreen({ friction, mapReady }: Props) {
  return (
    <div className="mk-screen-grid mk-screen-grid--map">
      <Panel eyebrow="Stage 4C" title="Singapore Friction Map">
        <FrictionMap friction={friction} mapReady={mapReady} />
      </Panel>
      <Panel eyebrow="Anomaly" title="Conflict Analysis">
        <div className="mk-summary">{friction?.anomaly_summary ?? 'No anomaly summary available yet.'}</div>
        <div className="mk-list">
          {(friction?.map_metrics ?? []).slice(0, 8).map((row: any, index) => (
            <article key={index} className="mk-list-card">
              <div className="mk-list-card__title">{String(row.planning_area ?? 'Area')}</div>
              <p>Friction: {Number(row.friction_index ?? row.friction ?? 0).toFixed(3)}</p>
            </article>
          ))}
        </div>
      </Panel>
    </div>
  );
}
