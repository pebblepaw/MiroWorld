import { useState } from "react";
import Markdown from "react-markdown";

interface MarkdownContentProps {
  children: string | null | undefined;
  className?: string;
  /** When set, content is clamped to this many lines with a "Read more" toggle. */
  clampLines?: number;
}

/**
 * Pre-process AI-generated text so Markdown syntax is correctly interpreted.
 * Handles cases where `### ` headings appear inline after other text.
 */
function preprocessMarkdown(raw: string): string {
  let text = raw;
  // Ensure markdown headings start on their own line
  text = text.replace(/([^\n])(#{1,6}\s)/g, "$1\n\n$2");
  // Ensure `**bold**` markers aren't stuck to preceding text
  text = text.replace(/([^\n*])\*\*([^*]+)\*\*/g, "$1 **$2**");
  return text;
}

/**
 * Renders AI-generated markdown content with prose styling.
 * Works in both light and dark mode via Tailwind's dark-class strategy.
 */
export function MarkdownContent({ children, className = "", clampLines }: MarkdownContentProps) {
  const text = preprocessMarkdown(String(children ?? "").trim());
  if (!text) return null;

  const [expanded, setExpanded] = useState(false);
  const clamp = clampLines && !expanded;

  return (
    <div className={clamp ? "relative" : undefined}>
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
        style={clamp ? { overflow: "hidden", display: "-webkit-box", WebkitLineClamp: clampLines, WebkitBoxOrient: "vertical" } as React.CSSProperties : undefined}
      >
        <Markdown>{text}</Markdown>
      </div>
      {clampLines && (
        <button
          type="button"
          onClick={() => setExpanded((prev) => !prev)}
          className="text-[11px] font-medium text-primary hover:text-primary/80 mt-1 transition-colors"
        >
          {expanded ? "Show less" : "Read more"}
        </button>
      )}
    </div>
  );
}
