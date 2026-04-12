import { useRef, useState, useEffect, useCallback } from "react";
import Markdown from "react-markdown";

interface MarkdownContentProps {
  children: string | null | undefined;
  className?: string;
  /** When set, content is clamped to this many lines with a "Read more" toggle. */
  clampLines?: number;
}

/**
 * Pre-process AI-generated text so Markdown syntax is correctly interpreted.
 *
 * Handles common LLM output quirks:
 * - `### ` headings appearing inline after other text
 * - `**Bold Label:** rest of text` that should be a heading on its own line
 * - Single `*` used as bullet markers inline within a paragraph
 */
function preprocessMarkdown(raw: string): string {
  let text = raw;

  // 1. Ensure markdown headings (e.g. ### Heading) start on their own line
  text = text.replace(/([^\n])(#{1,6}\s)/g, "$1\n\n$2");

  // 2. Convert inline `* Item:` or `* Item` patterns into proper list items.
  //    Matches " * " or ". * " mid-sentence (not already at line start).
  text = text.replace(/([.;,])\s*\*\s+/g, "$1\n\n- ");
  // Also handle `* ` at the very start of a line already (standardize to `- `)
  text = text.replace(/^\*\s+/gm, "- ");

  // 3. Ensure bold labels like "**Thematic Consensus:**" get their own paragraph
  //    when they appear right after a period/newline (i.e. start of a new thought).
  text = text.replace(/([.!?\n])\s*\*\*([^*]+?):?\*\*\s*/g, "$1\n\n**$2:** ");

  return text;
}

/**
 * Renders AI-generated markdown content with prose styling.
 * Works in both light and dark mode via Tailwind's dark-class strategy.
 */
export function MarkdownContent({ children, className = "", clampLines }: MarkdownContentProps) {
  const [expanded, setExpanded] = useState(false);
  const [clamped, setClamped] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  const text = preprocessMarkdown(String(children ?? "").trim());

  // Robust overflow detection: check after render, after fonts load, and on resize
  const checkOverflow = useCallback(() => {
    if (!clampLines || !contentRef.current) return;
    const el = contentRef.current;
    setClamped(el.scrollHeight > el.clientHeight + 2);
  }, [clampLines]);

  useEffect(() => {
    checkOverflow();
    // Re-check after fonts settle (async font loading can change line heights)
    const raf = requestAnimationFrame(checkOverflow);
    return () => cancelAnimationFrame(raf);
  }, [text, clampLines, checkOverflow]);

  useEffect(() => {
    if (!clampLines || !contentRef.current) return;
    const observer = new ResizeObserver(checkOverflow);
    observer.observe(contentRef.current);
    return () => observer.disconnect();
  }, [clampLines, checkOverflow]);

  if (!text) return null;

  const clamp = clampLines && !expanded;

  return (
    <div>
      <div
        ref={contentRef}
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
      {clampLines && (clamped || expanded) && (
        <button
          type="button"
          onClick={() => setExpanded((prev) => !prev)}
          className="text-xs font-medium text-primary hover:text-primary/80 mt-1.5 transition-colors flex items-center gap-1"
        >
          {expanded ? "↑ Show less" : "↓ Show more"}
        </button>
      )}
    </div>
  );
}
