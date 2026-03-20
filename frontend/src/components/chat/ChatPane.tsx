import { FormEvent } from 'react';
import type { ChatTranscriptEntry } from '../../types/console';

type Props = {
  title: string;
  promptLabel: string;
  value: string;
  transcript: ChatTranscriptEntry[];
  context?: string | null;
  sendLabel?: string;
  isBusy?: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
};

export function ChatPane({
  title,
  promptLabel,
  value,
  transcript,
  context,
  sendLabel = 'Send',
  isBusy = false,
  onChange,
  onSubmit,
}: Props) {
  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <section className="mk-chat">
      <div className="mk-chat__title-row">
        <div className="mk-chat__title">{title}</div>
        {isBusy ? <div className="mk-status">Sending…</div> : null}
      </div>
      {context ? <div className="mk-chat__context">{context}</div> : null}
      <div className="mk-chat__thread">
        {transcript.length > 0 ? (
          transcript.map((entry, index) => (
            <article
              key={`${entry.created_at ?? index}-${index}`}
              className={entry.role === 'user' ? 'mk-chat__bubble mk-chat__bubble--user' : 'mk-chat__bubble mk-chat__bubble--assistant'}
            >
              <div className="mk-chat__bubble-meta">
                <span>{entry.role === 'user' ? 'You' : 'McKAInsey'}</span>
                {entry.created_at ? <span>{entry.created_at}</span> : null}
              </div>
              <p>{entry.content}</p>
            </article>
          ))
        ) : (
          <div className="mk-empty">No transcript yet. Send the first message to start the conversation.</div>
        )}
      </div>
      <form className="mk-chat__form" onSubmit={handleSubmit}>
        <label className="mk-field">
          <span>{promptLabel}</span>
          <textarea value={value} onChange={(event) => onChange(event.target.value)} rows={4} />
        </label>
        <button className="mk-button mk-button--primary" type="submit" disabled={isBusy}>
          {isBusy ? 'Sending…' : sendLabel}
        </button>
      </form>
    </section>
  );
}
