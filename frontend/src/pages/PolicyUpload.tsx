import { useState, useCallback, useRef, useEffect } from 'react';
import { Upload, FileText, Sparkles, Loader2, ArrowRight, Eye, EyeOff, X, Plus, Link, Type, ChevronDown, ChevronUp } from 'lucide-react';
import { forceCollide, forceManyBody } from 'd3-force-3d';
import ForceGraph2D from 'react-force-graph-2d';
import { useApp, AnalysisQuestion } from '@/contexts/AppContext';
import { GlassCard } from '@/components/GlassCard';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import {
  createConsoleSession,
  generateQuestionMetadata,
  getAnalysisQuestions,
  getBundledDemoOutput,
  isLiveBootMode,
  isStaticDemoBootMode,
  processKnowledgeDocuments,
  subscribeKnowledgeStream,
  type KnowledgeArtifact,
  type KnowledgeEdge,
  type KnowledgeNode,
  type KnowledgeStreamEvent,
  updateV2SessionConfig,
  uploadKnowledgeFile,
  scrapeKnowledgeUrl,
} from '@/lib/console-api';
import { useTheme } from '@/contexts/ThemeContext';
import { toast } from '@/hooks/use-toast';

/* ─── Graph Display Constants ─── */

const DISPLAY_BUCKET_STYLES: Record<string, { label: string; color: string }> = {
  organization: { label: 'Organization', color: 'hsl(0, 0%, 62%)' },
  persons:      { label: 'Persons',      color: 'hsl(142, 50%, 50%)' },
  location:     { label: 'Location',     color: 'hsl(38, 72%, 54%)' },
  age_group:    { label: 'Age Group',    color: 'hsl(142, 48%, 50%)' },
  event:        { label: 'Event',        color: 'hsl(0, 58%, 55%)' },
  concept:      { label: 'Concept',      color: 'hsl(200, 50%, 56%)' },
  industry:     { label: 'Industry',     color: 'hsl(266, 40%, 60%)' },
  other:        { label: 'Other',        color: 'hsl(0, 0%, 47%)' },
};

const DISPLAY_BUCKET_ORDER = ['organization', 'persons', 'location', 'age_group', 'event', 'concept', 'industry', 'other'] as const;
const MIN_NODE_RADIUS = 4;
const MAX_NODE_RADIUS = 12;
const NODE_LABEL_GAP = 8;
const RELATIONSHIP_LABEL_STORAGE_KEY = 'screen1-relationship-labels';

type FamilyFilter = 'all' | 'nemotron' | 'other';
type DisplayBucket = typeof DISPLAY_BUCKET_ORDER[number];
type GraphNodeDatum = {
  id: string;
  name: string;
  type: string;
  displayBucket: string;
  facetKind?: string | null;
  families: string[];
  description?: string | null;
  summary?: string | null;
  val: number;
  renderRadius: number;
  x?: number;
  y?: number;
};
type GraphLinkDatum = {
  source: string | GraphNodeDatum;
  target: string | GraphNodeDatum;
  label: string;
  type: string;
  summary?: string | null;
};

type KnowledgeStreamProgress = {
  stage: string;
  message: string;
  percent?: number | null;
  chunkIndex?: number | null;
  chunkTotal?: number | null;
  documentLabel?: string | null;
};

type KnowledgeArtifactPatch = Partial<KnowledgeArtifact> & {
  entity_nodes?: KnowledgeNode[];
  relationship_edges?: KnowledgeEdge[];
  processing_logs?: string[];
};

function resolveKnowledgeExtractionError(
  error: unknown,
  context: { provider: string; model: string },
): string {
  if (error instanceof Error) {
    const message = error.message.trim();
    if (message && message.toLowerCase() !== 'failed to fetch') {
      return message;
    }
  }

  return (
    `Could not reach the backend during extraction while using ` +
    `${context.provider}/${context.model}. ` +
    `Check that the backend is running and that the selected provider runtime is reachable.`
  );
}

function buildSafeDocumentName(rawName: string, fallback: string) {
  const trimmed = rawName.trim();
  if (!trimmed) return fallback;
  return trimmed.replace(/[\\/:*?"<>|]+/g, "-").replace(/\s+/g, "-").toLowerCase();
}

function getProcessingProviderLabel(provider: string) {
  const normalized = String(provider || '').trim().toLowerCase();
  if (normalized === 'google' || normalized === 'gemini') {
    return 'Google Gemini';
  }
  if (normalized === 'openai') {
    return 'OpenAI';
  }
  if (normalized === 'ollama') {
    return 'Ollama';
  }
  return normalized || 'Model';
}

function normalizeAnalysisQuestion(question: Record<string, unknown>): AnalysisQuestion {
  return {
    question: String(question.question ?? ''),
    type: question.type === 'yes-no' || question.type === 'open-ended' ? question.type : 'scale',
    metric_name: String(question.metric_name ?? question.metricName ?? `custom_${Date.now()}`),
    metric_label: question.metric_label ? String(question.metric_label) : undefined,
    metric_unit: question.metric_unit ? String(question.metric_unit) : undefined,
    threshold: typeof question.threshold === 'number' ? question.threshold : undefined,
    threshold_direction: question.threshold_direction ? String(question.threshold_direction) : undefined,
    report_title: String(question.report_title ?? question.question ?? 'Question'),
    tooltip: question.tooltip ? String(question.tooltip) : undefined,
    source: 'preset',
    metadataStatus: 'ready',
  };
}

function stripQuestionMetadata(question: AnalysisQuestion): Record<string, unknown> {
  const { metadataStatus, ...rest } = question;
  return rest;
}

async function readFileText(file: File): Promise<string> {
  if (typeof file.text === "function") {
    return file.text();
  }

  if (typeof file.arrayBuffer === "function") {
    const bytes = await file.arrayBuffer();
    return new TextDecoder().decode(bytes);
  }

  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error("Unable to read file contents."));
    reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : "");
    reader.readAsText(file);
  });
}

function isServerParsedDocument(file: File): boolean {
  const name = file.name.toLowerCase();
  return (
    name.endsWith('.pdf') ||
    name.endsWith('.doc') ||
    name.endsWith('.docx') ||
    name.endsWith('.ppt') ||
    name.endsWith('.pptx') ||
    name.endsWith('.xls') ||
    name.endsWith('.xlsx') ||
    name.endsWith('.png') ||
    name.endsWith('.jpg') ||
    name.endsWith('.jpeg') ||
    name.endsWith('.gif') ||
    name.endsWith('.webp') ||
    name.endsWith('.bmp')
  );
}

function mergeKnowledgeArtifacts(
  sessionId: string,
  artifacts: KnowledgeArtifact[],
  guidingPrompt: string | null,
): KnowledgeArtifact {
  if (artifacts.length === 0) {
    throw new Error("No knowledge artifacts were returned from extraction.");
  }
  if (artifacts.length === 1) {
    return {
      ...artifacts[0],
      session_id: sessionId,
      guiding_prompt: guidingPrompt,
    };
  }

  const nodes: KnowledgeArtifact["entity_nodes"] = [];
  const edges: KnowledgeArtifact["relationship_edges"] = [];
  const logs: string[] = [];
  const summaries: string[] = [];
  const sourceDocuments = artifacts.map((artifact) => artifact.document);
  const seenNodes = new Set<string>();
  const seenEdges = new Set<string>();

  for (const artifact of artifacts) {
    const summary = String(artifact.summary || "").trim();
    if (summary) summaries.push(summary);

    for (const node of artifact.entity_nodes || []) {
      const key = String(node.id || node.label || "").trim().toLowerCase();
      if (!key || seenNodes.has(key)) continue;
      seenNodes.add(key);
      nodes.push(node);
    }

    for (const edge of artifact.relationship_edges || []) {
      const key = [
        String(edge.source || "").trim().toLowerCase(),
        String(edge.target || "").trim().toLowerCase(),
        String(edge.type || "").trim().toLowerCase(),
        String(edge.label || "").trim().toLowerCase(),
      ].join("|");
      if (!key || seenEdges.has(key)) continue;
      seenEdges.add(key);
      edges.push(edge);
    }

    for (const logLine of artifact.processing_logs || []) {
      const line = String(logLine || "").trim();
      if (line) logs.push(line);
    }
  }

  return {
    session_id: sessionId,
    document: {
      document_id: `merged-${artifacts.length}-documents`,
      source_path: "merged://knowledge-documents",
      file_name: "merged-documents",
      text_length: sourceDocuments.reduce((total, doc) => total + Number(doc?.text_length ?? 0), 0),
      paragraph_count: sourceDocuments.reduce((total, doc) => total + Number(doc?.paragraph_count ?? 0), 0),
    },
    summary: summaries.join("\n\n"),
    guiding_prompt: guidingPrompt,
    entity_nodes: nodes,
    relationship_edges: edges,
    entity_type_counts: nodes.reduce<Record<string, number>>((counts, node) => {
      const type = String(node.type || "unknown");
      counts[type] = (counts[type] || 0) + 1;
      return counts;
    }, {}),
    processing_logs: logs,
    demographic_focus_summary: artifacts[0]?.demographic_focus_summary ?? null,
  };
}

function createEmptyKnowledgeArtifact(sessionId: string): KnowledgeArtifact {
  return {
    session_id: sessionId,
    document: {
      document_id: `stream-${sessionId}`,
      text_length: 0,
      paragraph_count: 0,
    },
    summary: '',
    guiding_prompt: null,
    entity_nodes: [],
    relationship_edges: [],
    entity_type_counts: {},
    processing_logs: [],
    demographic_focus_summary: null,
  };
}

function mergeUniqueRecords<T extends { id?: string | null }>(current: T[], incoming: T[]) {
  const result = [...current];
  const indexByKey = new Map(
    current
      .map((item, index) => [String(item.id ?? '').trim().toLowerCase(), index] as const)
      .filter(([key]) => Boolean(key)),
  );
  for (const item of incoming) {
    const key = String(item.id ?? '').trim().toLowerCase();
    if (!key) {
      continue;
    }
    const existingIndex = indexByKey.get(key);
    if (existingIndex === undefined) {
      indexByKey.set(key, result.length);
      result.push(item);
      continue;
    }
    result[existingIndex] = {
      ...result[existingIndex],
      ...item,
    };
  }
  return result;
}

function mergeUniqueEdges(current: KnowledgeEdge[], incoming: KnowledgeEdge[]) {
  const result = [...current];
  const indexByKey = new Map(
    current.map((edge, index) => [
      [
        String(edge.source || '').trim().toLowerCase(),
        String(edge.target || '').trim().toLowerCase(),
        String(edge.type || '').trim().toLowerCase(),
        String(edge.label || '').trim().toLowerCase(),
      ].join('|'),
      index,
    ] as const),
  );

  for (const edge of incoming) {
    const key = [
      String(edge.source || '').trim().toLowerCase(),
      String(edge.target || '').trim().toLowerCase(),
      String(edge.type || '').trim().toLowerCase(),
      String(edge.label || '').trim().toLowerCase(),
    ].join('|');
    if (!key) {
      continue;
    }
    const existingIndex = indexByKey.get(key);
    if (existingIndex === undefined) {
      indexByKey.set(key, result.length);
      result.push(edge);
      continue;
    }
    result[existingIndex] = {
      ...result[existingIndex],
      ...edge,
    };
  }

  return result;
}

function mergeKnowledgeArtifactSnapshot(
  currentArtifact: KnowledgeArtifact | null,
  patch: KnowledgeArtifactPatch,
  sessionId: string,
): KnowledgeArtifact {
  const base = currentArtifact ?? createEmptyKnowledgeArtifact(sessionId);
  const nextDocument = {
    ...base.document,
    ...(patch.document ?? {}),
  };
  const nextNodes = mergeUniqueRecords(base.entity_nodes, patch.entity_nodes ?? []);
  const nextEdges = mergeUniqueEdges(base.relationship_edges, patch.relationship_edges ?? []);
  const nextLogs = [...base.processing_logs];
  for (const logLine of patch.processing_logs ?? []) {
    const line = String(logLine || '').trim();
    if (line) {
      nextLogs.push(line);
    }
  }

  return {
    ...base,
    ...patch,
    session_id: patch.session_id || base.session_id || sessionId,
    document: nextDocument,
    entity_nodes: nextNodes,
    relationship_edges: nextEdges,
    entity_type_counts: {
      ...base.entity_type_counts,
      ...(patch.entity_type_counts ?? {}),
    },
    processing_logs: nextLogs,
    guiding_prompt: patch.guiding_prompt ?? base.guiding_prompt ?? null,
    demographic_focus_summary: patch.demographic_focus_summary ?? base.demographic_focus_summary ?? null,
  };
}

function isKnowledgeArtifactPatch(payload: Record<string, unknown>): payload is KnowledgeArtifactPatch {
  return (
    "entity_nodes" in payload
    || "relationship_edges" in payload
    || "processing_logs" in payload
    || "summary" in payload
    || "document" in payload
    || "entity_type_counts" in payload
    || "guiding_prompt" in payload
    || "demographic_focus_summary" in payload
    || "session_id" in payload
  );
}

function unwrapKnowledgeArtifactPatch(payload: Record<string, unknown>): KnowledgeArtifactPatch | null {
  const normalizePatch = (candidate: Record<string, unknown>): KnowledgeArtifactPatch => {
    const normalized: Record<string, unknown> = { ...candidate };
    if (!("entity_nodes" in normalized) && Array.isArray(normalized.nodes)) {
      normalized.entity_nodes = normalized.nodes;
    }
    if (!("relationship_edges" in normalized) && Array.isArray(normalized.edges)) {
      normalized.relationship_edges = normalized.edges;
    }
    if (!("processing_logs" in normalized) && Array.isArray(normalized.logs)) {
      normalized.processing_logs = normalized.logs;
    }
    return normalized as KnowledgeArtifactPatch;
  };

  const nestedKeys = ["artifact", "knowledge", "knowledge_artifact", "partial", "data"];
  for (const key of nestedKeys) {
    const value = payload[key];
    if (value && typeof value === "object" && !Array.isArray(value)) {
      const nested = value as Record<string, unknown>;
      if (isKnowledgeArtifactPatch(nested)) {
        return normalizePatch(nested);
      }
      if ("nodes" in nested || "edges" in nested || "logs" in nested) {
        return normalizePatch(nested);
      }
    }
  }

  if (isKnowledgeArtifactPatch(payload)) {
    return normalizePatch(payload);
  }

  if ("nodes" in payload || "edges" in payload || "logs" in payload) {
    return normalizePatch(payload);
  }

  return null;
}

function numberValue(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function stringValue(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

function resolveStreamProgress(eventName: string, payload: Record<string, unknown>): KnowledgeStreamProgress {
  const percent =
    numberValue(payload.progress)
    ?? numberValue(payload.percent)
    ?? numberValue(payload.completion_pct)
    ?? numberValue(payload.completionPercent)
    ?? null;
  const chunkIndex =
    numberValue(payload.chunk_index)
    ?? numberValue(payload.chunkIndex)
    ?? numberValue(payload.current_chunk)
    ?? numberValue(payload.currentChunk)
    ?? null;
  const chunkTotal =
    numberValue(payload.chunk_total)
    ?? numberValue(payload.chunk_count)
    ?? numberValue(payload.chunkTotal)
    ?? numberValue(payload.total_chunks)
    ?? numberValue(payload.totalChunks)
    ?? null;
  const documentLabel =
    stringValue(payload.document_name)
    ?? stringValue(payload.file_name)
    ?? stringValue(payload.source_path)
    ?? stringValue((payload.document as Record<string, unknown> | undefined)?.file_name)
    ?? stringValue((payload.document as Record<string, unknown> | undefined)?.source_path)
    ?? null;

  const rawMessage =
    stringValue(payload.message)
    ?? stringValue(payload.detail)
    ?? stringValue(payload.status)
    ?? stringValue(payload.note)
    ?? '';
  const fallbackMessage = (() => {
    switch (eventName) {
      case 'knowledge_started':
        return 'Initializing LightRAG engine...';
      case 'knowledge_document_started':
        return 'Loading document into pipeline...';
      case 'knowledge_chunk_started':
        return `Extracting entities from chunk${chunkIndex !== null ? ` ${chunkIndex}` : ''}${chunkTotal !== null ? ` of ${chunkTotal}` : ''}...`;
      case 'knowledge_chunk_completed':
        return `Chunk${chunkIndex !== null ? ` ${chunkIndex}` : ''}${chunkTotal !== null ? ` of ${chunkTotal}` : ''} extracted`;
      case 'knowledge_partial':
        return 'Building knowledge graph...';
      case 'knowledge_completed':
        return 'Knowledge extraction complete';
      case 'knowledge_failed':
        return 'Knowledge extraction failed';
      default:
        return 'Processing...';
    }
  })();

  const chunkMessage =
    chunkIndex !== null && chunkTotal !== null
      ? `Chunk ${chunkIndex} of ${chunkTotal} — extracting entities & relations`
      : chunkIndex !== null
        ? `Chunk ${chunkIndex} — extracting...`
        : documentLabel
          ? `Document ${documentLabel}`
          : fallbackMessage;

  return {
    stage: eventName,
    message: rawMessage || chunkMessage || fallbackMessage,
    percent,
    chunkIndex,
    chunkTotal,
    documentLabel,
  };
}

/* ─── Main Component ─── */

export default function PolicyUpload() {
  const {
    sessionId,
    modelProvider,
    modelName,
    embedModelName,
    modelApiKey,
    modelBaseUrl,
    useCase,
    uploadedFiles,
    analysisQuestions,
    knowledgeGraphReady,
    knowledgeArtifact,
    knowledgeLoading,
    knowledgeError,
    setSessionId,
    addUploadedFile,
    removeUploadedFile,
    setAnalysisQuestions,
    setKnowledgeGraphReady,
    setKnowledgeArtifact,
    setKnowledgeLoading,
    setKnowledgeError,
    completeStep,
    setCurrentStep,
  } = useApp();

  const { theme } = useTheme();
  const [dragOver, setDragOver] = useState(false);
  const graphRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 500, height: 400 });
  const [familyFilter, setFamilyFilter] = useState<FamilyFilter>('all');
  const [activeBuckets, setActiveBuckets] = useState<DisplayBucket[]>([]);
  const [showRelationshipLabels, setShowRelationshipLabels] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return window.sessionStorage.getItem(RELATIONSHIP_LABEL_STORAGE_KEY) === 'on';
  });
  const [showUrlInput, setShowUrlInput] = useState(false);
  const [urlValue, setUrlValue] = useState('');
  const [showPasteArea, setShowPasteArea] = useState(false);
  const [pasteValue, setPasteValue] = useState('');
  const [showTopEntities, setShowTopEntities] = useState(true);
  const [analysisQuestionsState, setAnalysisQuestionsState] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [analysisQuestionsError, setAnalysisQuestionsError] = useState<string | null>(null);
  const [knowledgeStreamProgress, setKnowledgeStreamProgress] = useState<KnowledgeStreamProgress | null>(null);
  const hydratedSessionRef = useRef<string | null>(null);
  const analysisQuestionsRef = useRef<AnalysisQuestion[]>(analysisQuestions);
  const knowledgeLoadingRef = useRef<boolean>(knowledgeLoading);
  const lastPersistedQuestionsSnapshotRef = useRef<string>('');
  const knowledgeArtifactRef = useRef<KnowledgeArtifact | null>(knowledgeArtifact);
  const knowledgeStreamRef = useRef<ReturnType<typeof subscribeKnowledgeStream> | null>(null);

  const graphReady = knowledgeGraphReady && knowledgeArtifact !== null;

  // Pre-load source URL in demo-static mode so Screen 1 shows the URL input filled
  useEffect(() => {
    if (!isStaticDemoBootMode()) return;
    getBundledDemoOutput().then((demo: Record<string, unknown>) => {
      const sourceUrl = (demo.source_run as Record<string, unknown> | undefined)?.source_url;
      if (typeof sourceUrl === 'string' && sourceUrl) {
        setUrlValue(sourceUrl);
        setShowUrlInput(true);
      }
    }).catch(() => { /* ignore */ });
  }, []);

  useEffect(() => {
    analysisQuestionsRef.current = analysisQuestions;
  }, [analysisQuestions]);

  useEffect(() => {
    knowledgeLoadingRef.current = knowledgeLoading;
  }, [knowledgeLoading]);

  useEffect(() => {
    knowledgeArtifactRef.current = knowledgeArtifact;
  }, [knowledgeArtifact]);

  const closeKnowledgeStream = useCallback(() => {
    knowledgeStreamRef.current?.close();
    knowledgeStreamRef.current = null;
  }, []);

  useEffect(() => () => closeKnowledgeStream(), [closeKnowledgeStream]);

  const commitKnowledgeArtifact = useCallback((nextArtifact: KnowledgeArtifact | null) => {
    knowledgeArtifactRef.current = nextArtifact;
    setKnowledgeArtifact(nextArtifact);
    setKnowledgeGraphReady(Boolean(nextArtifact));
  }, [setKnowledgeArtifact, setKnowledgeGraphReady]);

  const persistAnalysisQuestionsNow = useCallback((cleanQuestions: Record<string, unknown>[]) => {
    if (!sessionId) {
      return;
    }

    if (
      cleanQuestions.length === 0
      && hydratedSessionRef.current !== sessionId
      && analysisQuestionsState !== 'ready'
    ) {
      return;
    }

    const snapshot = JSON.stringify(cleanQuestions);

    if (snapshot === lastPersistedQuestionsSnapshotRef.current) {
      return;
    }

    lastPersistedQuestionsSnapshotRef.current = snapshot;
    void updateV2SessionConfig(sessionId, {
      country: undefined,
      use_case: useCase,
      provider: modelProvider,
      model: modelName,
      api_key: modelApiKey || undefined,
      analysis_questions: cleanQuestions,
    }).catch(() => {
      // Persisting analysis questions is best-effort so extraction can continue.
    });
  }, [analysisQuestionsState, modelApiKey, modelName, modelProvider, sessionId, useCase]);

  const persistAnalysisQuestions = useCallback((nextQuestions: AnalysisQuestion[]) => {
    const cleanQuestions = nextQuestions.map(stripQuestionMetadata);
    if (knowledgeLoadingRef.current) {
      return;
    }
    persistAnalysisQuestionsNow(cleanQuestions);
  }, [persistAnalysisQuestionsNow]);

  useEffect(() => {
    if (knowledgeLoading) {
      return;
    }
    persistAnalysisQuestionsNow(analysisQuestionsRef.current.map(stripQuestionMetadata));
  }, [knowledgeLoading, persistAnalysisQuestionsNow]);

  useEffect(() => {
    if (!sessionId || hydratedSessionRef.current === sessionId) {
      return;
    }

    let cancelled = false;

    const loadAnalysisQuestions = async () => {
      setAnalysisQuestionsState('loading');
      setAnalysisQuestionsError(null);
      try {
        const payload = await getAnalysisQuestions(sessionId);
        const next = Array.isArray(payload.questions) ? payload.questions.map((question) => normalizeAnalysisQuestion(question)) : [];
        if (cancelled) {
          return;
        }
        analysisQuestionsRef.current = next;
        setAnalysisQuestions(next);
        lastPersistedQuestionsSnapshotRef.current = JSON.stringify(next.map(stripQuestionMetadata));
        persistAnalysisQuestions(next);
        setAnalysisQuestionsState('ready');
        hydratedSessionRef.current = sessionId;
      } catch (error) {
        if (cancelled) {
          return;
        }
        const message = error instanceof Error ? error.message : 'Failed to load analysis questions.';
        setAnalysisQuestionsState('error');
        setAnalysisQuestionsError(message);
      }
    };

    void loadAnalysisQuestions();

    return () => {
      cancelled = true;
    };
  }, [sessionId, setAnalysisQuestions]);

  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver(([entry]) => {
      setDimensions({ width: entry.contentRect.width, height: entry.contentRect.height });
    });
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.sessionStorage.setItem(RELATIONSHIP_LABEL_STORAGE_KEY, showRelationshipLabels ? 'on' : 'off');
    }
  }, [showRelationshipLabels]);

  const familyScopedNodes = graphReady
    ? (() => {
        const visibleNodes = knowledgeArtifact.entity_nodes.filter(
          (node) => !node.ui_default_hidden && matchesFamilyFilter(node.facet_kind, familyFilter),
        );
        if (visibleNodes.length > 0) {
          return visibleNodes;
        }
        // Short uploads can legitimately yield a single low-value orphan. Show it when it is all we have.
        return knowledgeArtifact.entity_nodes.filter((node) => matchesFamilyFilter(node.facet_kind, familyFilter));
      })()
    : [];

  const availableBuckets: DisplayBucket[] = graphReady
    ? DISPLAY_BUCKET_ORDER.filter((bucket) => familyScopedNodes.some((node) => resolveDisplayBucket(node.type, node.facet_kind, node.display_bucket) === bucket))
    : [];

  useEffect(() => {
    if (!graphReady) {
      setFamilyFilter((current) => (current === 'all' ? current : 'all'));
      setActiveBuckets((current) => (current.length === 0 ? current : []));
      return;
    }

    setActiveBuckets((current) => {
      const next = current.filter((bucket) => availableBuckets.includes(bucket));
      const resolved = next.length > 0 ? next : availableBuckets;
      return sameStringArray(current, resolved) ? current : resolved;
    });
  }, [availableBuckets, graphReady]);

  const resetKnowledgeState = useCallback(() => {
    closeKnowledgeStream();
    setKnowledgeStreamProgress(null);
    knowledgeArtifactRef.current = null;
    setFamilyFilter('all');
    setActiveBuckets([]);
    setKnowledgeGraphReady(false);
    setKnowledgeArtifact(null);
    setKnowledgeError(null);
  }, [closeKnowledgeStream, setActiveBuckets, setFamilyFilter, setKnowledgeArtifact, setKnowledgeError, setKnowledgeGraphReady]);

  const replaceAnalysisQuestionAtIndex = useCallback((index: number, updater: (question: AnalysisQuestion) => AnalysisQuestion) => {
    const next = analysisQuestionsRef.current.map((question, currentIndex) => (
      currentIndex === index ? updater(question) : question
    ));
    analysisQuestionsRef.current = next;
    setAnalysisQuestions(next);
    persistAnalysisQuestions(next);
  }, [persistAnalysisQuestions, setAnalysisQuestions]);

  const addNewAnalysisQuestion = useCallback(() => {
    const next: AnalysisQuestion = {
      question: '',
      type: 'open-ended',
      metric_name: `custom_${Date.now()}`,
      report_title: 'Custom Question',
      source: 'custom',
      metadataStatus: 'pending',
    };
    const updated = [...analysisQuestionsRef.current, next];
    analysisQuestionsRef.current = updated;
    setAnalysisQuestions(updated);
    persistAnalysisQuestions(updated);
  }, [persistAnalysisQuestions, setAnalysisQuestions]);

  const removeQuestionAtIndex = useCallback((index: number) => {
    const updated = analysisQuestionsRef.current.filter((_, currentIndex) => currentIndex !== index);
    analysisQuestionsRef.current = updated;
    setAnalysisQuestions(updated);
    persistAnalysisQuestions(updated);
  }, [persistAnalysisQuestions, setAnalysisQuestions]);

  const updateQuestionText = useCallback((index: number, value: string) => {
    replaceAnalysisQuestionAtIndex(index, (question) => ({
      ...question,
      question: value,
      source: 'custom',
      metadataStatus: 'pending',
    }));
  }, [replaceAnalysisQuestionAtIndex]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    files.forEach((f) => addUploadedFile(f));
    resetKnowledgeState();
  }, [resetKnowledgeState, addUploadedFile]);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    files.forEach((f) => addUploadedFile(f));
    resetKnowledgeState();
  }, [resetKnowledgeState, addUploadedFile]);

  const ensureSession = useCallback(async () => {
    if (sessionId) {
      return sessionId;
    }

    const created = await createConsoleSession(undefined, {
      model_provider: modelProvider,
      model_name: modelName,
      embed_model_name: embedModelName,
      api_key: modelApiKey.trim() || undefined,
      base_url: modelBaseUrl.trim() || undefined,
    });
    setSessionId(created.session_id);
    return created.session_id;
  }, [
    embedModelName,
    modelApiKey,
    modelBaseUrl,
    modelName,
    modelProvider,
    sessionId,
    setSessionId,
  ]);

  const handleExtract = useCallback(async () => {
    if (uploadedFiles.length === 0) return;

    try {
      setKnowledgeLoading(true);
      setKnowledgeError(null);
      setKnowledgeStreamProgress(null);

      let resolvedSessionId = await ensureSession();
      resetKnowledgeState();
      setKnowledgeLoading(true);
      const currentQuestions = analysisQuestionsRef.current;
      persistAnalysisQuestions(currentQuestions);
      const serverParsedFiles = uploadedFiles.filter(isServerParsedDocument);
      const textFiles = uploadedFiles.filter((file) => !isServerParsedDocument(file));
      const metadataTargets = currentQuestions
        .map((question, index) => ({ question, index }))
        .filter(({ question }) => question.metadataStatus !== 'ready');

      const metadataGeneration = metadataTargets.map(async ({ question, index }) => {
        if (!question.question.trim()) {
          replaceAnalysisQuestionAtIndex(index, (current) => ({
            ...current,
            metadataStatus: 'error',
          }));
          return;
        }

        replaceAnalysisQuestionAtIndex(index, (current) => ({
          ...current,
          metadataStatus: 'loading',
        }));

        try {
          const metadata = await generateQuestionMetadata(question.question, useCase);
          replaceAnalysisQuestionAtIndex(index, (current) => ({
            ...current,
            ...metadata,
            source: current.source === 'preset' ? 'preset' : 'custom',
            metadataStatus: 'ready',
          }));
        } catch (error) {
          replaceAnalysisQuestionAtIndex(index, (current) => ({
            ...current,
            metadataStatus: 'error',
          }));
          throw error;
        }
      });

      let streamFailureMessage: string | null = null;
      const canStreamKnowledge = isLiveBootMode();
      const streamSubscription = canStreamKnowledge
        ? subscribeKnowledgeStream(resolvedSessionId, {
            onEvent: ({ name, payload }: KnowledgeStreamEvent) => {
              const nextProgress = resolveStreamProgress(name, payload);
              setKnowledgeStreamProgress((current) => ({
                stage: nextProgress.stage,
                message: nextProgress.message,
                percent: nextProgress.percent ?? current?.percent ?? null,
                chunkIndex: nextProgress.chunkIndex ?? current?.chunkIndex ?? null,
                chunkTotal: nextProgress.chunkTotal ?? current?.chunkTotal ?? null,
                documentLabel: nextProgress.documentLabel ?? current?.documentLabel ?? null,
              }));

              const patch = unwrapKnowledgeArtifactPatch(payload);
              if (name === 'knowledge_partial' && patch) {
                commitKnowledgeArtifact(
                  mergeKnowledgeArtifactSnapshot(knowledgeArtifactRef.current, patch, resolvedSessionId),
                );
                return;
              }

              if (name === 'knowledge_completed') {
                const nextArtifact = patch
                  ? mergeKnowledgeArtifactSnapshot(null, patch, resolvedSessionId)
                  : knowledgeArtifactRef.current;
                if (nextArtifact) {
                  commitKnowledgeArtifact(nextArtifact);
                }
                setFamilyFilter('all');
                setActiveBuckets([]);
                setKnowledgeStreamProgress((current) => ({
                  stage: 'knowledge_completed',
                  message: 'Knowledge extraction completed.',
                  percent: 100,
                  chunkIndex: current?.chunkIndex ?? null,
                  chunkTotal: current?.chunkTotal ?? null,
                  documentLabel: current?.documentLabel ?? null,
                }));
                return;
              }

              if (name === 'knowledge_failed') {
                streamFailureMessage =
                  stringValue(payload.message)
                  ?? stringValue(payload.detail)
                  ?? nextProgress.message
                  ?? 'Knowledge extraction failed.';
                setKnowledgeError(streamFailureMessage);
              }
            },
            onError: () => {
              if (!streamFailureMessage) {
                setKnowledgeStreamProgress((current) => ({
                  stage: 'heartbeat',
                  message: current?.message || 'Knowledge stream disconnected.',
                  percent: current?.percent ?? null,
                  chunkIndex: current?.chunkIndex ?? null,
                  chunkTotal: current?.chunkTotal ?? null,
                  documentLabel: current?.documentLabel ?? null,
                }));
              }
            },
          })
        : null;

      if (streamSubscription) {
        knowledgeStreamRef.current = streamSubscription;
      }

      const knowledgePromise = (async () => {
        const artifacts: KnowledgeArtifact[] = [];
        let backendSessionId: string | null = null;
        const assertStreamHealthy = () => {
          if (streamFailureMessage) {
            throw new Error(streamFailureMessage);
          }
        };

        if (textFiles.length > 0) {
          setKnowledgeStreamProgress({
            stage: 'knowledge_started',
            message: `Submitting ${textFiles.length} text document${textFiles.length === 1 ? '' : 's'}`,
            percent: 5,
          });
          const documents = await Promise.all(
            textFiles.map(async (file) => ({
              document_text: await readFileText(file),
              source_path: file.name,
            })),
          );
          const artifact = await processKnowledgeDocuments(resolvedSessionId, {
            documents,
            guiding_prompt: undefined,
          });
          const artifactSessionId = String(artifact.session_id ?? '').trim();
          if (artifactSessionId && artifactSessionId !== resolvedSessionId) {
            backendSessionId = artifactSessionId;
          }
          artifacts.push(artifact);
          commitKnowledgeArtifact(
            mergeKnowledgeArtifactSnapshot(knowledgeArtifactRef.current, artifact, resolvedSessionId),
          );
          assertStreamHealthy();
        }

        for (let index = 0; index < serverParsedFiles.length; index += 1) {
          const file = serverParsedFiles[index];
          setKnowledgeStreamProgress({
            stage: 'knowledge_document_started',
            message: `Submitting ${file.name}`,
            percent: textFiles.length > 0 || serverParsedFiles.length > 1 ? Math.max(10, Math.round(((index + 1) / serverParsedFiles.length) * 85)) : 25,
            documentLabel: file.name,
          });
          const artifact = await uploadKnowledgeFile(
            resolvedSessionId,
            file,
            undefined,
          );
          const artifactSessionId = String(artifact.session_id ?? '').trim();
          if (artifactSessionId && artifactSessionId !== resolvedSessionId) {
            backendSessionId = artifactSessionId;
          }
          artifacts.push(artifact);
          commitKnowledgeArtifact(
            mergeKnowledgeArtifactSnapshot(knowledgeArtifactRef.current, artifact, resolvedSessionId),
          );
          assertStreamHealthy();
        }

        assertStreamHealthy();
        const mergedArtifact = mergeKnowledgeArtifacts(resolvedSessionId, artifacts, null);
        if (backendSessionId) {
          mergedArtifact.session_id = backendSessionId;
        }
        return mergedArtifact;
      })();

      const [artifact] = await Promise.all([
        knowledgePromise,
        Promise.allSettled(metadataGeneration),
      ]);

      if (streamFailureMessage) {
        throw new Error(streamFailureMessage);
      }

      const returnedSessionId = String(artifact.session_id ?? '').trim();
      if (returnedSessionId && returnedSessionId !== resolvedSessionId) {
        setSessionId(returnedSessionId);
        resolvedSessionId = returnedSessionId;
      }

      commitKnowledgeArtifact(
        mergeKnowledgeArtifactSnapshot(null, artifact, resolvedSessionId),
      );
      setFamilyFilter('all');
      setActiveBuckets([]);
      setKnowledgeStreamProgress({
        stage: 'knowledge_completed',
        message: 'Knowledge extraction completed.',
        percent: 100,
        chunkIndex: null,
        chunkTotal: null,
        documentLabel: null,
      });
    } catch (error) {
      closeKnowledgeStream();
      if (!isLiveBootMode()) {
        try {
          // Demo mode can still hydrate from the bundled demo artifact.
          const demo = await getBundledDemoOutput();
          const knowledgeData = demo.knowledge as Record<string, any> | undefined;
          if (knowledgeData?.entity_nodes) {
            const artifact = {
              session_id: knowledgeData.simulation_id || 'demo-session',
              document: knowledgeData.document || { document_id: 'demo', paragraph_count: 0 },
              summary: knowledgeData.summary || '',
              guiding_prompt: knowledgeData.guiding_prompt || null,
              entity_nodes: knowledgeData.entity_nodes,
              relationship_edges: knowledgeData.relationship_edges || [],
              entity_type_counts: knowledgeData.entity_type_counts || {},
              processing_logs: [],
              demographic_focus_summary: knowledgeData.demographic_focus_summary || null,
            } as KnowledgeArtifact;
            setKnowledgeArtifact(artifact);
            setKnowledgeGraphReady(true);
            setSessionId(artifact.session_id);
            setKnowledgeStreamProgress({
              stage: 'knowledge_completed',
              message: 'Loaded cached demo knowledge graph.',
              percent: 100,
            });
            toast({ title: 'Demo mode', description: 'Loaded cached knowledge graph (backend unavailable)' });
            return;
          }
        } catch { /* ignore demo fallback errors */ }
      }

      const message = resolveKnowledgeExtractionError(error, {
        provider: modelProvider,
        model: modelName,
      });
      setKnowledgeGraphReady(false);
      setKnowledgeArtifact(null);
      setKnowledgeStreamProgress(null);
      setKnowledgeError(message);
      toast({
        title: 'Knowledge extraction failed',
        description: message,
        variant: 'destructive',
      });
    } finally {
      closeKnowledgeStream();
      setKnowledgeLoading(false);
    }
  }, [
    closeKnowledgeStream,
    uploadedFiles,
    sessionId,
    modelProvider,
    modelName,
    embedModelName,
    modelApiKey,
    modelBaseUrl,
    setKnowledgeLoading,
    setKnowledgeError,
    setSessionId,
    setKnowledgeArtifact,
    setKnowledgeGraphReady,
    ensureSession,
    commitKnowledgeArtifact,
    replaceAnalysisQuestionAtIndex,
    resetKnowledgeState,
    useCase,
  ]);

  const handleProceed = () => {
    completeStep(1);
    setCurrentStep(2);
  };

  const handleUrlScrape = useCallback(async () => {
    const url = urlValue.trim();
    if (!url) return;

    try {
      const resolvedSessionId = await ensureSession();
      const scraped = await scrapeKnowledgeUrl(resolvedSessionId, url);
      const fileName = `${buildSafeDocumentName(scraped.title || 'scraped-document', 'scraped-document')}.txt`;
      const scrapedFile = new File([scraped.text || url], fileName, { type: 'text/plain' });
      addUploadedFile(scrapedFile);
      resetKnowledgeState();
      toast({ title: 'URL scraped', description: scraped.title ? scraped.title : `Fetched content from ${url}` });
    } catch (error) {
      resetKnowledgeState();
      const message = error instanceof Error ? error.message : 'Backend scrape failed.';
      if (!isLiveBootMode()) {
        const fallbackName = `${buildSafeDocumentName(url, 'scraped-document')}.txt`;
        const fallbackFile = new File([url], fallbackName, { type: 'text/plain' });
        addUploadedFile(fallbackFile);
        toast({
          title: 'URL scrape fallback',
          description: `${message} Queued URL as text.`,
        });
        return;
      }

      setKnowledgeError(message);
      toast({
        title: 'URL scrape failed',
        description: message,
        variant: 'destructive',
      });
    } finally {
      setUrlValue('');
      setShowUrlInput(false);
    }
  }, [addUploadedFile, ensureSession, resetKnowledgeState, setKnowledgeError, setShowUrlInput, setUrlValue, urlValue]);

  const handlePasteSubmit = useCallback(() => {
    const text = pasteValue.trim();
    if (!text) return;

    const blob = new Blob([text], { type: 'text/plain' });
    const mockFile = new File([blob], 'pasted-text.txt', { type: 'text/plain' });
    addUploadedFile(mockFile);
    resetKnowledgeState();
    setPasteValue('');
    setShowPasteArea(false);
    toast({ title: 'Text added', description: 'Pasted content queued for backend extraction' });
  }, [addUploadedFile, pasteValue, resetKnowledgeState, setPasteValue, setShowPasteArea]);

  /* ─── Graph Data ─── */

  const filteredSourceNodes = graphReady
    ? familyScopedNodes.filter((node) => {
        const bucket = resolveDisplayBucket(node.type, node.facet_kind, node.display_bucket);
        return activeBuckets.length === 0 ? true : activeBuckets.includes(bucket);
      })
    : [];

  const filteredNodeIds = new Set(filteredSourceNodes.map((node) => node.id));

  const graphData = graphReady ? {
    nodes: filteredSourceNodes.map((node) => ({
      id: node.id,
      name: node.label,
      type: normalizeNodeType(node.type),
      displayBucket: resolveDisplayBucket(node.type, node.facet_kind, node.display_bucket),
      facetKind: node.facet_kind,
      families: node.families ?? ['document'],
      description: node.summary || node.description,
      summary: node.summary || node.description,
      val: normalizeImportance(node.importance_score, node.weight),
      renderRadius: radiusFromImportance(node.importance_score, node.weight),
    })),
    links: knowledgeArtifact.relationship_edges
      .filter((edge) => filteredNodeIds.has(edge.source) && filteredNodeIds.has(edge.target))
      .map((edge) => ({
        ...edge,
        label: edge.label || edge.raw_relation_text || edge.type,
        summary: edge.summary || edge.raw_relation_text || edge.label || edge.type,
      })),
  } : { nodes: [], links: [] };

  useEffect(() => {
    if (!graphReady || graphData.nodes.length === 0 || !graphRef.current?.d3Force) return;

    const maxRadius = Math.max(...graphData.nodes.map((node) => node.renderRadius), MIN_NODE_RADIUS);
    graphRef.current.d3Force('charge', forceManyBody().strength(-(150 + maxRadius * 18)));
    graphRef.current.d3Force('collide', forceCollide((node: GraphNodeDatum) => node.renderRadius + 30).iterations(2));

    const linkForce = graphRef.current.d3Force('link');
    if (linkForce && typeof linkForce.distance === 'function') {
      linkForce.distance((link: { source: GraphNodeDatum; target: GraphNodeDatum }) => {
        const sourceRadius = link.source?.renderRadius ?? MIN_NODE_RADIUS;
        const targetRadius = link.target?.renderRadius ?? MIN_NODE_RADIUS;
        return Math.max(110, (sourceRadius + targetRadius) * 8);
      });
    }
    graphRef.current.d3ReheatSimulation?.();
  }, [graphData.links, graphData.nodes, graphReady]);

  const legendEntries = graphReady
    ? Array.from(
        new Map(
          graphData.nodes.map((node: GraphNodeDatum) => {
            const style = DISPLAY_BUCKET_STYLES[node.displayBucket] ?? DISPLAY_BUCKET_STYLES.other;
            return [`${style.label}:${style.color}`, style] as const;
          }),
        ).values(),
      )
    : [];

  const topEntities = graphReady
    ? [...(
        knowledgeArtifact.entity_nodes.some((node) => !node.ui_default_hidden)
          ? knowledgeArtifact.entity_nodes.filter((node) => !node.ui_default_hidden)
          : knowledgeArtifact.entity_nodes
      )]
      .sort((left, right) => {
        const rightImportance = normalizeImportance(right.importance_score, right.weight);
        const leftImportance = normalizeImportance(left.importance_score, left.weight);
        if (rightImportance !== leftImportance) return rightImportance - leftImportance;
        return (right.support_count ?? 0) - (left.support_count ?? 0);
      })
      .slice(0, 3)
    : [];

  const nodeColor = (node: { type?: string; displayBucket?: string; facetKind?: string }) => {
    return (DISPLAY_BUCKET_STYLES[node.displayBucket || resolveDisplayBucket(node.type, node.facetKind)] ?? DISPLAY_BUCKET_STYLES.other).color;
  };

  /* ─── Render ─── */

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[420px_1fr] gap-0 h-full">
      {/* ───── LEFT PANEL ───── */}
      <div className="flex flex-col border-r border-border overflow-y-auto scrollbar-thin bg-background min-h-0">
        {/* Header */}
        <div className="p-5 pb-4 border-b border-border">
          <h2 className="text-page-title font-semibold text-foreground">New Simulation Run</h2>
          <p className="text-xs text-muted-foreground mt-1">Upload unstructured documents to build the context graph</p>
          {/* Use-case badge */}
          <div className="mt-3">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-border bg-transparent text-[10px] font-mono uppercase tracking-[0.16em] text-muted-foreground">
              {getProcessingProviderLabel(modelProvider)} · Document Processing
            </span>
          </div>
        </div>

        {/* Upload Zone */}
        <div className="p-5 border-b border-border">
          <label
            className={`flex flex-col items-center justify-center p-6 cursor-pointer transition-colors border border-dashed rounded-lg bg-transparent ${
              dragOver ? 'border-[hsl(var(--data-blue))] bg-muted/30' : uploadedFiles.length > 0 ? 'border-border' : 'border-border hover:border-muted-foreground/40'
            }`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
          >
            <input type="file" className="hidden" accept=".pdf,.docx,.doc,.ppt,.pptx,.xls,.xlsx,.txt,.md,.markdown,.html,.htm,.csv,.png,.jpg,.jpeg,.gif,.webp,.bmp" multiple onChange={handleFileSelect} />
            <Upload className="w-6 h-6 text-muted-foreground mb-2" />
            <span className="text-sm text-foreground">Drop documents here</span>
            <span className="text-[10px] text-muted-foreground mt-1 font-mono uppercase tracking-wider">
              PDF · PPT · DOCX · XLSX · JPG · CSV · MD
            </span>
          </label>

          {/* File list */}
          {uploadedFiles.length > 0 && (
            <div className="mt-3 space-y-1">
              {uploadedFiles.map((file, index) => (
                <div key={`${file.name}-${index}`} className="rounded bg-card border border-border group px-3 py-2">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 min-w-0">
                      <FileText className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                      <span className="text-sm text-foreground truncate">{file.name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono text-muted-foreground">{formatFileSize(file.size)}</span>
                      <button
                        type="button"
                        onClick={() => { removeUploadedFile(index); resetKnowledgeState(); }}
                        className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-foreground"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                  {knowledgeLoading && (
                    <div className="mt-2">
                      <Progress
                        value={resolveKnowledgeProgressValue(knowledgeStreamProgress)}
                        pulse
                        aria-label={`${file.name} extraction progress`}
                        className="h-1.5 bg-muted"
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Alt input methods */}
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={() => setShowUrlInput(!showUrlInput)}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-[10px] font-mono uppercase tracking-wider border transition-colors ${
                showUrlInput ? 'border-border bg-muted/50 text-foreground' : 'border-border text-muted-foreground hover:text-foreground hover:border-muted-foreground/40'
              }`}
            >
              <Link className="w-3 h-3" /> URL
            </button>
            <button
              type="button"
              onClick={() => setShowPasteArea(!showPasteArea)}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-[10px] font-mono uppercase tracking-wider border transition-colors ${
                showPasteArea ? 'border-border bg-muted/50 text-foreground' : 'border-border text-muted-foreground hover:text-foreground hover:border-muted-foreground/40'
              }`}
            >
              <Type className="w-3 h-3" /> Paste
            </button>
          </div>

          {/* URL scraper */}
          {showUrlInput && (
            <div className="mt-2 flex gap-2 animate-slide-up">
              <Input
                value={urlValue}
                onChange={(e) => setUrlValue(e.target.value)}
                placeholder="https://example.com/policy-doc"
                className="text-sm bg-card border-border"
              />
              <Button
                onClick={handleUrlScrape}
                size="sm"
                variant={urlValue.trim() ? "destructive" : "outline"}
                className={urlValue.trim() ? "shrink-0" : "shrink-0 border-border text-foreground"}
              >
                Scrape
              </Button>
            </div>
          )}

          {/* Paste text */}
          {showPasteArea && (
            <div className="mt-2 space-y-2 animate-slide-up">
              <Textarea
                value={pasteValue}
                onChange={(e) => setPasteValue(e.target.value)}
                placeholder="Paste document text here..."
                className="text-sm bg-card border-border min-h-[80px] resize-none"
              />
              <Button onClick={handlePasteSubmit} size="sm" variant="outline" className="border-border text-foreground">
                Add as Document
              </Button>
            </div>
          )}
        </div>

        {/* Analysis Questions */}
        <div className="p-5 border-b border-border">
          <div className="flex items-center justify-between gap-3 mb-3">
            <div>
              <span className="label-section">Analysis Questions</span>
              <p className="text-[10px] text-muted-foreground mt-0.5">
                These questions drive the simulation checkpoints, report sections, and metric generation.
              </p>
            </div>
            <button
              type="button"
              onClick={addNewAnalysisQuestion}
              className="inline-flex items-center gap-1.5 rounded border border-border px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider text-muted-foreground transition-colors hover:border-muted-foreground/40 hover:bg-muted/30 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              <Plus className="w-3 h-3" /> Add Question
            </button>
          </div>
          <div className="space-y-2">
            {analysisQuestionsState === 'loading' && (
              <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Loading analysis questions...</p>
            )}
            {analysisQuestionsError && (
              <p className="text-xs text-destructive">{analysisQuestionsError}</p>
            )}
            {analysisQuestions.length === 0 && analysisQuestionsState !== 'loading' && (
              <p className="text-xs text-muted-foreground italic py-3 text-center">
                No analysis questions loaded yet.
              </p>
            )}
            {analysisQuestions.map((q, index) => {
              const statusLabel = q.metadataStatus === 'loading'
                ? 'Loading metadata...'
                : q.metadataStatus === 'ready'
                  ? 'Ready'
                  : q.metadataStatus === 'error'
                    ? 'Metadata error'
                    : 'Pending regeneration';
              const statusClass = q.metadataStatus === 'loading'
                ? 'bg-amber-500/10 text-amber-300'
                : q.metadataStatus === 'ready'
                  ? 'bg-emerald-500/10 text-emerald-400'
                  : q.metadataStatus === 'error'
                    ? 'bg-red-500/10 text-red-400'
                    : 'bg-muted text-muted-foreground';

              return (
                <div key={`${q.metric_name}-${index}`} className="group relative rounded-lg border border-border bg-card p-3 transition-colors hover:border-muted-foreground/30">
                  <div className="flex items-start gap-3">
                    <div className="flex-1 min-w-0">
                      <Textarea
                        value={q.question}
                        onChange={(e) => updateQuestionText(index, e.target.value)}
                        placeholder="Type your analysis question..."
                        className="min-h-[58px] resize-none border-0 bg-transparent p-0 text-sm text-foreground focus-visible:ring-0 focus-visible:ring-offset-0"
                      />
                      <div className="mt-1.5 flex flex-wrap items-center gap-2">
                        <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-mono uppercase tracking-wider ${
                          q.type === 'scale' ? 'bg-blue-500/10 text-blue-400' :
                          q.type === 'yes-no' ? 'bg-emerald-500/10 text-emerald-400' :
                          'bg-muted text-muted-foreground'
                        }`}>
                          {q.type}
                        </span>
                        {q.source === 'preset' && (
                          <span className="text-[9px] font-mono uppercase tracking-wider text-muted-foreground/70">PRESET</span>
                        )}
                        <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-mono uppercase tracking-wider ${statusClass}`}>
                          {statusLabel}
                        </span>
                        {q.metric_label && <span className="text-[9px] text-muted-foreground">{q.metric_label}</span>}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeQuestionAtIndex(index)}
                      className="opacity-0 transition-opacity text-muted-foreground hover:text-foreground group-hover:opacity-100 mt-1"
                      title="Delete question"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Actions */}
        <div className="p-5 border-b border-border">
          <div className="flex gap-2">
            <Button
              onClick={handleExtract}
              disabled={uploadedFiles.length === 0 || knowledgeLoading}
              className="flex-1 bg-[hsl(var(--data-blue))] hover:bg-[hsl(210,100%,50%)] text-white border-0 font-medium font-mono uppercase tracking-wider text-xs h-10"
            >
              {knowledgeLoading ? (
                "Processing..."
              ) : (
                <><Sparkles className="w-3.5 h-3.5 mr-2" /> Start Extraction</>
              )}
            </Button>
            {graphReady && !knowledgeLoading && (
              <Button
                onClick={handleProceed}
                variant="outline"
                className="h-10 border border-success/30 bg-success/20 px-4 font-mono text-xs uppercase tracking-wider text-success hover:bg-success/30"
              >
                Proceed <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            )}
          </div>
          {knowledgeError && (
            <p className="text-xs text-destructive mt-2 font-mono uppercase">{knowledgeError}</p>
          )}

          {/* Knowledge extraction progress */}
          {knowledgeLoading && (
            <div className="mt-4 p-3 border border-border bg-card rounded font-mono text-[10px] text-muted-foreground w-full space-y-1 overflow-hidden">
              <div className="flex justify-between gap-3 min-w-0">
                <span className="truncate min-w-0">
                  [{new Date().toLocaleTimeString('en-US', { hour12: false })}] {knowledgeStreamProgress?.message || 'Loading LightRAG engine...'}
                </span>
                <span className="text-success uppercase shrink-0 animate-pulse">{formatKnowledgeStageLabel(knowledgeStreamProgress?.stage)}</span>
              </div>
              <Progress
                value={resolveKnowledgeProgressValue(knowledgeStreamProgress)}
                pulse
                aria-label="Knowledge extraction progress"
                className="h-1.5 bg-muted"
              />
              <div className="flex justify-between gap-3 text-[9px] uppercase tracking-wider text-muted-foreground/80 min-w-0">
                <span className="truncate min-w-0">
                  {knowledgeStreamProgress?.documentLabel
                    ? `Document ${knowledgeStreamProgress.documentLabel}`
                    : knowledgeStreamProgress?.chunkIndex
                      ? 'Extracting entities & relations'
                      : 'Preparing document for analysis'}
                </span>
                <span className="shrink-0">
                  {knowledgeStreamProgress?.chunkIndex && knowledgeStreamProgress?.chunkTotal
                    ? `Chunk ${knowledgeStreamProgress.chunkIndex} of ${knowledgeStreamProgress.chunkTotal} extracted`
                    : knowledgeStreamProgress?.chunkIndex
                      ? `Chunk ${knowledgeStreamProgress.chunkIndex} extracting...`
                      : 'Waiting for chunks'}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Stats */}
        {graphReady && (
          <div className="p-5 border-b border-border">
            <div className="grid grid-cols-3 gap-4">
              <Stat label="Entities" value={knowledgeArtifact.entity_nodes.length} />
              <Stat label="Relations" value={knowledgeArtifact.relationship_edges.length} />
              <Stat label="Paragraphs" value={knowledgeArtifact.document.paragraph_count ?? 0} />
            </div>
          </div>
        )}

        {/* Top Entities — collapsible */}
        {graphReady && (
          <div className="p-5 pb-8">
            <button
              type="button"
              onClick={() => setShowTopEntities(!showTopEntities)}
              className="flex items-center justify-between w-full mb-3"
            >
              <span className="label-meta">Top Entities</span>
              {showTopEntities ? <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" /> : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />}
            </button>
            {showTopEntities && (
              <div className="space-y-3 animate-slide-up">
                {topEntities.map((node) => {
                  const bucket = resolveDisplayBucket(node.type, node.facet_kind, node.display_bucket);
                  const style = DISPLAY_BUCKET_STYLES[bucket] ?? DISPLAY_BUCKET_STYLES.other;
                  return (
                    <div key={node.id} className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: style.color }} />
                          <span className="truncate text-sm text-foreground">{node.label}</span>
                        </div>
                        <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground ml-4">{style.label}</div>
                      </div>
                      <div className="text-right shrink-0">
                        <div className="text-sm font-mono text-foreground">{normalizeImportance(node.importance_score, node.weight).toFixed(2)}</div>
                        <div className="text-[10px] font-mono text-muted-foreground">×{node.support_count ?? 0}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ───── RIGHT PANEL — KNOWLEDGE GRAPH ───── */}
      <div className="flex flex-col bg-background">
        <div className="flex items-center justify-between px-5 py-3 border-b border-border">
          <h3 className="text-sm font-medium text-foreground">Knowledge Graph</h3>
        </div>

        {graphReady && (
          <div className="px-5 py-2.5 border-b border-border space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <SegmentedControl
                value={familyFilter}
                options={[
                  { value: 'all', label: 'All' },
                  { value: 'nemotron', label: 'Nemotron' },
                  { value: 'other', label: 'Other' },
                ]}
                onChange={(nextValue) => setFamilyFilter(nextValue as FamilyFilter)}
              />
              <button
                type="button"
                onClick={() => setShowRelationshipLabels((current) => !current)}
                className={`inline-flex items-center gap-1.5 rounded border px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider transition-colors ${
                  showRelationshipLabels
                    ? 'border-border bg-muted/50 text-foreground'
                    : 'border-border text-muted-foreground hover:border-muted-foreground/40 hover:text-foreground'
                }`}
              >
                {showRelationshipLabels ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
                Labels
              </button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {availableBuckets.map((bucket) => {
                const style = DISPLAY_BUCKET_STYLES[bucket] ?? DISPLAY_BUCKET_STYLES.other;
                const isActive = activeBuckets.includes(bucket);
                return (
                  <FilterChip
                    key={bucket}
                    active={isActive}
                    label={style.label}
                    accent={style.color}
                    onClick={() => {
                      setActiveBuckets((current) => (
                        current.length === availableBuckets.length
                          ? [bucket]
                          : current.includes(bucket)
                            ? (current.filter((value) => value !== bucket).length > 0
                              ? current.filter((value) => value !== bucket)
                              : availableBuckets)
                            : [...current, bucket]
                      ));
                    }}
                  />
                );
              })}
            </div>
          </div>
        )}

        <div ref={containerRef} className="flex-1 min-h-[300px] overflow-hidden">
          {graphReady && graphData.nodes.length > 0 ? (
            <ForceGraph2D
              ref={graphRef}
              graphData={graphData}
              width={dimensions.width}
              height={dimensions.height}
              enableNodeDrag
              nodeLabel={(node: GraphNodeDatum) => `${node.name || ''}${node.summary ? `: ${node.summary}` : ''}`}
              linkLabel={(link: GraphLinkDatum) => {
                const summary = link.summary?.trim();
                if (!summary) return link.label || '';
                return `${link.label}: ${summary}`;
              }}
              nodeColor={nodeColor}
              nodeRelSize={1}
              nodeCanvasObjectMode={() => 'replace'}
              nodeCanvasObject={(node: GraphNodeDatum, ctx, globalScale) => {
                if (typeof node.x !== 'number' || typeof node.y !== 'number') return;

                const radius = node.renderRadius || radiusFromNormalizedValue(node.val);
                const label = node.name || '';
                const fontSize = Math.max(8, 11 / globalScale);
                ctx.font = `${fontSize}px "Space Grotesk", sans-serif`;
                const labelX = node.x + radius + NODE_LABEL_GAP;
                const labelY = node.y;

                ctx.save();
                ctx.beginPath();
                ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
                ctx.fillStyle = nodeColor(node);
                ctx.fill();

                ctx.lineWidth = 1;
                ctx.strokeStyle = theme === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.12)';
                ctx.stroke();

                ctx.textAlign = 'left';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = theme === 'dark' ? 'rgba(255, 255, 255, 0.85)' : 'rgba(0, 0, 0, 0.8)';
                ctx.fillText(label, labelX, labelY);
                ctx.restore();
              }}
              linkCanvasObjectMode={() => 'after'}
              linkCanvasObject={(link: GraphLinkDatum, ctx, globalScale) => {
                if (!showRelationshipLabels) return;
                const label = (link.label || link.type || '').trim();
                const source = typeof link.source === 'string' ? undefined : link.source;
                const target = typeof link.target === 'string' ? undefined : link.target;
                if (!label || typeof source?.x !== 'number' || typeof source?.y !== 'number' || typeof target?.x !== 'number' || typeof target?.y !== 'number') return;

                const midX = (source.x + target.x) / 2;
                const midY = (source.y + target.y) / 2;
                const dx = target.x - source.x;
                const dy = target.y - source.y;
                const length = Math.hypot(dx, dy) || 1;
                const normalX = -dy / length;
                const normalY = dx / length;
                const readableLabel = shortenLabel(label, Math.max(12, Math.floor(length / 8)));
                const fontSize = Math.max(8.5, 10.5 / globalScale);
                ctx.font = `${fontSize}px "Space Mono", monospace`;
                const textWidth = ctx.measureText(readableLabel).width;
                const boxWidth = textWidth + 12;
                const boxHeight = fontSize + 8;
                const offset = Math.min(22, Math.max(10, length * 0.08));

                ctx.save();
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = theme === 'dark' ? 'rgba(255, 255, 255, 0.55)' : 'rgba(0, 0, 0, 0.5)';
                ctx.fillText(readableLabel, midX + normalX * offset, midY + normalY * offset);
                ctx.restore();
              }}
              linkColor={() => theme === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.12)'}
              linkWidth={1}
              linkDirectionalArrowLength={4}
              linkDirectionalArrowRelPos={1}
              backgroundColor="transparent"
              cooldownTicks={120}
              warmupTicks={50}
              nodePointerAreaPaint={(node: GraphNodeDatum, color, ctx) => {
                const radius = (node as GraphNodeDatum).renderRadius || 5;
                ctx.fillStyle = color;
                ctx.beginPath();
                ctx.arc((node as GraphNodeDatum).x ?? 0, (node as GraphNodeDatum).y ?? 0, radius + 4, 0, 2 * Math.PI);
                ctx.fill();
              }}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              {knowledgeLoading ? (
                <div className="flex flex-col items-center gap-3">
                  <Loader2 className="w-6 h-6 animate-spin text-white/40" />
                  <span className="animate-pulse font-mono text-xs uppercase tracking-wider">Building graph...</span>
                </div>
              ) : graphReady ? (
                'No nodes match the current filters'
              ) : (
                <div className="text-center max-w-xs">
                  <div className="text-muted-foreground/40 mb-2">
                    <Upload className="w-8 h-8 mx-auto" />
                  </div>
                  <p className="text-sm text-muted-foreground">Upload a document to generate the knowledge graph</p>
                  <p className="text-[10px] font-mono text-muted-foreground/50 mt-1 uppercase tracking-wider">Interactive Force Graph · Drag nodes to explore</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── Sub-components ─── */

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="text-2xl font-mono font-medium text-foreground tracking-tight">{value}</div>
      <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-[0.18em]">{label}</div>
    </div>
  );
}

function FilterChip({ active, label, onClick, accent }: { active: boolean; label: string; onClick: () => void; accent?: string; }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded border px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider transition-colors ${
        active
          ? 'border-border bg-foreground/[0.08] text-foreground'
          : 'border-border text-muted-foreground hover:border-muted-foreground/40 hover:text-foreground'
      }`}
    >
      <span className="flex items-center gap-1.5">
        {accent && <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: accent, opacity: active ? 1 : 0.5 }} />}
        {label}
      </span>
    </button>
  );
}

function SegmentedControl({ value, options, onChange }: { value: string; options: Array<{ value: string; label: string }>; onChange: (value: string) => void; }) {
  return (
    <div className="inline-flex items-center gap-0.5 rounded border border-border bg-card p-0.5">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={`rounded px-3 py-1 text-[10px] font-mono uppercase tracking-wider transition-colors ${
            option.value === value
              ? 'bg-white/10 text-foreground'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

/* ─── Utilities ─── */

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function normalizeNodeType(type?: string) {
  const normalized = (type || 'other').trim().toLowerCase();
  if (normalized === 'institution' || normalized === 'org') return 'organization';
  if (normalized === 'demographic') return 'population';
  if (normalized === 'planning_area') return 'location';
  return normalized || 'other';
}

function normalizeImportance(importanceScore?: number | null, weight?: number | null) {
  const base = importanceScore ?? weight ?? 0.35;
  return Math.max(0, Math.min(1, Number.isFinite(base) ? Number(base) : 0.35));
}

function radiusFromImportance(importanceScore?: number | null, weight?: number | null) {
  const importance = normalizeImportance(importanceScore, weight);
  return Math.ceil(MIN_NODE_RADIUS + ((MAX_NODE_RADIUS - MIN_NODE_RADIUS) * importance));
}

function resolveKnowledgeProgressValue(progress: KnowledgeStreamProgress | null): number {
  if (!progress) {
    return 0;
  }

  if (typeof progress.percent === 'number' && Number.isFinite(progress.percent)) {
    return Math.max(0, Math.min(100, progress.percent));
  }

  if (typeof progress.chunkIndex === 'number' && typeof progress.chunkTotal === 'number' && progress.chunkTotal > 0) {
    return Math.max(0, Math.min(100, Math.round((progress.chunkIndex / progress.chunkTotal) * 100)));
  }

  if (progress.stage === 'knowledge_completed') {
    return 100;
  }

  return 50;
}

function formatKnowledgeStageLabel(stage: string | null | undefined): string {
  const normalized = String(stage || '').trim().toLowerCase();
  if (!normalized) {
    return 'Initializing';
  }
  if (normalized === 'heartbeat') {
    return 'In Progress';
  }
  return normalized
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function radiusFromNormalizedValue(value?: number | null) {
  const importance = Math.max(0, Math.min(1, Number.isFinite(value) ? Number(value) : 0));
  return Math.ceil(MIN_NODE_RADIUS + ((MAX_NODE_RADIUS - MIN_NODE_RADIUS) * importance));
}

function matchesFamilyFilter(facetKind?: string | null, familyFilter: FamilyFilter = 'all') {
  if (familyFilter === 'all') return true;
  const isNemotronEntity = Boolean((facetKind || '').trim());
  return familyFilter === 'nemotron' ? isNemotronEntity : !isNemotronEntity;
}

function resolveDisplayBucket(type?: string, facetKind?: string | null, explicitBucket?: string | null): DisplayBucket {
  const normalizedExplicit = (explicitBucket || '').trim().toLowerCase();
  if (normalizedExplicit && normalizedExplicit in DISPLAY_BUCKET_STYLES) return normalizedExplicit as DisplayBucket;

  const normalizedFacet = (facetKind || '').trim().toLowerCase();
  if (normalizedFacet === 'age_cohort') return 'age_group';
  if (normalizedFacet === 'industry') return 'industry';

  const normalizedType = normalizeNodeType(type);
  if (['organization', 'institution'].includes(normalizedType)) return 'organization';
  if (['person', 'population', 'stakeholder', 'demographic', 'group'].includes(normalizedType)) return 'persons';
  if (['location', 'planning_area'].includes(normalizedType)) return 'location';
  if (normalizedType === 'event') return 'event';
  if (['concept', 'policy', 'program', 'topic', 'law', 'service', 'funding'].includes(normalizedType)) return 'concept';
  if (normalizedType === 'industry') return 'industry';
  return 'other';
}

function shortenLabel(label: string, maxLength: number) {
  if (label.length <= maxLength) return label;
  return `${label.slice(0, Math.max(6, maxLength - 1))}…`;
}

function sameStringArray(left: string[], right: string[]) {
  if (left.length !== right.length) return false;
  return left.every((value, index) => value === right[index]);
}
