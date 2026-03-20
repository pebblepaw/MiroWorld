import { Panel } from '../../components/layout/Panel';
import type { ReportFull } from '../../types/console';

type Props = {
  report: ReportFull | null;
};

export function Stage4ReportScreen({ report }: Props) {
  const data = report?.report ?? {};
  const recommendations = (data.recommendations as Array<Record<string, unknown>> | undefined) ?? [];
  return (
    <div className="mk-screen-grid">
      <Panel eyebrow="Stage 4A" title="Full Report">
        <div className="mk-summary">{String(data.executive_summary ?? 'Run or load a session to populate the report.')}</div>
      </Panel>
      <Panel eyebrow="Actionable Insights" title="Recommendations">
        <div className="mk-list">
          {recommendations.map((row, index) => (
            <article key={`${row.title ?? 'rec'}-${index}`} className="mk-list-card">
              <div className="mk-list-card__title">{String(row.title ?? 'Recommendation')}</div>
              <p>{String(row.rationale ?? '')}</p>
            </article>
          ))}
        </div>
      </Panel>
    </div>
  );
}
