type Stage = {
  key: string;
  label: string;
  color: string;
};

type Props = {
  active: string;
  onSelect: (stage: string) => void;
};

const stages: Stage[] = [
  { key: 'stage1', label: 'Stage 1 Setup', color: '#f59e0b' },
  { key: 'stage2', label: 'Stage 2 Sampling', color: '#06b6d4' },
  { key: 'stage3a', label: 'Stage 3a Reactions', color: '#f97316' },
  { key: 'stage3b', label: 'Stage 3b Deliberation', color: '#8b5cf6' },
  { key: 'stage4', label: 'Stage 4 Report', color: '#10b981' },
  { key: 'stage5', label: 'Stage 5 Deep Dive', color: '#f43f5e' },
];

export default function StageSidebar({ active, onSelect }: Props) {
  return (
    <aside className="sidebar glass-card">
      <h3>Workflow</h3>
      <ul>
        {stages.map((stage) => (
          <li key={stage.key}>
            <button
              className={active === stage.key ? 'stage active' : 'stage'}
              style={{ borderColor: active === stage.key ? stage.color : 'transparent' }}
              onClick={() => onSelect(stage.key)}
            >
              <span className="dot" style={{ background: stage.color }} />
              {stage.label}
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
