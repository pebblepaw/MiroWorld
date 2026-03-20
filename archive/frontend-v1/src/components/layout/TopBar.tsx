import type { ConsoleMode, GraphView, ScreenKey } from '../../types/console';

type Props = {
  screen: ScreenKey;
  mode: ConsoleMode;
  graphView: GraphView;
  sessionId: string;
  status: string;
  onGraphViewChange: (view: GraphView) => void;
  onModeChange: (mode: ConsoleMode) => void;
};

export function TopBar({ screen, mode, graphView, sessionId, status, onGraphViewChange, onModeChange }: Props) {
  return (
    <header className="mk-topbar">
      <div>
        <div className="mk-topbar__title">McKAInsey</div>
        <div className="mk-topbar__subtitle">
          Session `{sessionId}` · Screen `{screen}` · Status `{status}`
        </div>
      </div>

      <div className="mk-topbar__actions">
        <div className="mk-pill-group">
          <button className={graphView === 'knowledge' ? 'mk-pill mk-pill--active' : 'mk-pill'} onClick={() => onGraphViewChange('knowledge')}>
            Knowledge Graph
          </button>
          <button className={graphView === 'agent' ? 'mk-pill mk-pill--active' : 'mk-pill'} onClick={() => onGraphViewChange('agent')}>
            Agent Graph
          </button>
        </div>
        <div className="mk-pill-group">
          <button className={mode === 'demo' ? 'mk-pill mk-pill--active' : 'mk-pill'} onClick={() => onModeChange('demo')}>
            Demo
          </button>
          <button className={mode === 'live' ? 'mk-pill mk-pill--active' : 'mk-pill'} onClick={() => onModeChange('live')}>
            Live
          </button>
        </div>
      </div>
    </header>
  );
}
