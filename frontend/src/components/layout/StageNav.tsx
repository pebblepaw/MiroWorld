import { screens } from '../../app/screen-state';
import type { ScreenKey } from '../../types/console';

type Props = {
  active: ScreenKey;
  onSelect: (screen: ScreenKey) => void;
};

export function StageNav({ active, onSelect }: Props) {
  return (
    <aside className="mk-sidebar">
      <div className="mk-brand-block">
        <div className="mk-brand-mark">MK</div>
        <div>
          <div className="mk-brand-title">McKAInsey</div>
          <div className="mk-brand-subtitle">Population Simulation Console</div>
        </div>
      </div>

      <nav className="mk-stage-list">
        {screens.map((screen) => (
          <button
            key={screen.key}
            className={screen.key === active ? 'mk-stage mk-stage--active' : 'mk-stage'}
            onClick={() => onSelect(screen.key)}
          >
            <span className="mk-stage__code">{screen.stage}</span>
            <span className="mk-stage__label">{screen.label}</span>
          </button>
        ))}
      </nav>

      <div className="mk-sidebar__footer">
        <div>System Health</div>
        <div>Documentation</div>
      </div>
    </aside>
  );
}
