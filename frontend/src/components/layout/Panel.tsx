import { PropsWithChildren } from 'react';

type Props = PropsWithChildren<{
  title?: string;
  eyebrow?: string;
  className?: string;
}>;

export function Panel({ title, eyebrow, className, children }: Props) {
  return (
    <section className={`mk-panel ${className ?? ''}`.trim()}>
      {(eyebrow || title) && (
        <header className="mk-panel__header">
          {eyebrow ? <div className="mk-eyebrow">{eyebrow}</div> : null}
          {title ? <h3 className="mk-panel__title">{title}</h3> : null}
        </header>
      )}
      {children}
    </section>
  );
}
