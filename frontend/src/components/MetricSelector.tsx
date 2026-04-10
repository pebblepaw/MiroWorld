import { useEffect, useState } from "react";
import { getAnalysisQuestions } from "@/lib/console-api";

interface AnalysisQuestion {
  question: string;
  type: string;
  metric_name: string;
  metric_label: string;
  metric_unit?: string;
}

interface MetricSelectorProps {
  sessionId: string | null;
  value: string | null;
  onChange: (metricName: string | null) => void;
  className?: string;
}

export function MetricSelector({ sessionId, value, onChange, className }: MetricSelectorProps) {
  const [questions, setQuestions] = useState<AnalysisQuestion[]>([]);

  useEffect(() => {
    if (!sessionId) return;
    getAnalysisQuestions(sessionId)
      .then((data) => {
        const qs = ((data.questions || []) as AnalysisQuestion[]).filter(
          (q) => (q.type === "scale" || q.type === "yes-no") && q.metric_name
        );
        setQuestions(qs);
      })
      .catch(() => setQuestions([]));
  }, [sessionId]);

  if (questions.length <= 1) return null;

  return (
    <div className={className}>
      <label className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mr-2">
        Metric
      </label>
      <select
        value={value ?? "__all__"}
        onChange={(e) => onChange(e.target.value === "__all__" ? null : e.target.value)}
        className="rounded border border-white/10 bg-white/5 px-2.5 py-1.5 text-xs text-foreground"
      >
        <option value="__all__">All (Aggregate)</option>
        {questions.map((q) => (
          <option key={q.metric_name} value={q.metric_name}>
            {q.metric_label} ({q.type === "yes-no" ? "%" : q.metric_unit || "/10"})
          </option>
        ))}
      </select>
    </div>
  );
}
