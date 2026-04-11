import Markdown from "react-markdown";

interface MarkdownContentProps {
  children: string | null | undefined;
  className?: string;
}

/**
 * Renders AI-generated markdown content with prose styling.
 * Works in both light and dark mode via Tailwind's dark-class strategy.
 */
export function MarkdownContent({ children, className = "" }: MarkdownContentProps) {
  const text = String(children ?? "").trim();
  if (!text) return null;

  return (
    <div
      className={`prose prose-sm dark:prose-invert max-w-none
        prose-p:my-1.5 prose-p:leading-relaxed
        prose-headings:font-semibold prose-headings:tracking-tight
        prose-h1:text-base prose-h2:text-sm prose-h3:text-sm
        prose-ul:my-1.5 prose-ol:my-1.5
        prose-li:my-0.5
        prose-code:rounded prose-code:bg-muted prose-code:px-1 prose-code:py-0.5
        prose-code:text-foreground prose-code:before:content-none prose-code:after:content-none
        prose-blockquote:border-border prose-blockquote:text-muted-foreground
        prose-strong:text-foreground
        ${className}`}
    >
      <Markdown>{text}</Markdown>
    </div>
  );
}
