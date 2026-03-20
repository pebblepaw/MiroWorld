import { KnowledgeGraph } from '../../components/graphs/KnowledgeGraph';
import { Panel } from '../../components/layout/Panel';
import type { KnowledgeArtifact } from '../../types/console';

type Props = {
  knowledge: KnowledgeArtifact | null;
  documentText: string;
  demographicFocus: string;
  uploadedFile: File | null;
  isBusy: boolean;
  onDocumentTextChange: (value: string) => void;
  onDemographicFocusChange: (value: string) => void;
  onUploadedFileChange: (file: File | null) => void;
  onUseDemoDocument: () => void;
  onProcess: () => void;
};

export function Stage1Screen(props: Props) {
  const { knowledge } = props;
  return (
    <div className="mk-screen-grid">
      <Panel eyebrow="Stage 1" title="Scenario Setup">
        <div className="mk-form-grid">
          <label className="mk-field">
            <span>Upload Source File</span>
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md,.markdown,.html,.htm,.json,.csv,.yaml,.yml"
              onChange={(event) => props.onUploadedFileChange(event.target.files?.[0] ?? null)}
            />
            <small className="mk-field__hint">Supported uploads: PDF, DOCX, TXT, Markdown, HTML, JSON, CSV, and YAML. Uploaded files take precedence over pasted text.</small>
          </label>
          <label className="mk-field">
            <span>Document Text</span>
            <textarea
              value={props.documentText}
              onChange={(event) => props.onDocumentTextChange(event.target.value)}
              rows={12}
              placeholder="Paste the policy, proposal, or campaign brief here."
            />
          </label>
          <label className="mk-field">
            <span>Demographic Focus</span>
            <input
              value={props.demographicFocus}
              onChange={(event) => props.onDemographicFocusChange(event.target.value)}
              placeholder="e.g. seniors in Woodlands exposed to transport cost changes"
            />
          </label>
          <div className="mk-file-pill">
            {props.uploadedFile ? (
              <>
                <span className="mk-file-pill__label">Selected file</span>
                <span className="mk-file-pill__name">{props.uploadedFile.name}</span>
                <button className="mk-pill" type="button" onClick={() => props.onUploadedFileChange(null)}>
                  Clear
                </button>
              </>
            ) : (
              <span className="mk-file-pill__empty">No file selected. Text input will be used.</span>
            )}
          </div>
          <div className="mk-row">
            <button className="mk-button" onClick={props.onUseDemoDocument}>
              Load Demo Document
            </button>
            <button className="mk-button mk-button--primary" onClick={props.onProcess} disabled={props.isBusy}>
              {props.isBusy ? 'Processing…' : 'Build Knowledge Graph'}
            </button>
          </div>
        </div>
      </Panel>

      <Panel eyebrow="Extracted Graph" title="Document Intelligence">
        <KnowledgeGraph artifact={knowledge} />
      </Panel>

      <Panel eyebrow="Summary" title="Structured Output">
        <div className="mk-summary">{knowledge?.summary ?? 'Run document processing to populate the graph and summary.'}</div>
        <div className="mk-chip-row">
          {Object.entries(knowledge?.entity_type_counts ?? {}).map(([key, value]) => (
            <span key={key} className="mk-chip">
              {key}: {value}
            </span>
          ))}
        </div>
        <ul className="mk-log-list">
          {(knowledge?.processing_logs ?? ['Awaiting processing']).map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}
