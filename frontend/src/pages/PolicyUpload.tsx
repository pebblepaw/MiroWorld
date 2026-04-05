import { useState, useCallback, useRef, useEffect } from 'react';
import { Upload, FileText, Sparkles, Loader2, ArrowRight, Eye, EyeOff, X, Plus, Link, Type, ChevronDown, ChevronUp } from 'lucide-react';
import { forceCollide, forceManyBody } from 'd3-force-3d';
import ForceGraph2D from 'react-force-graph-2d';
import { useApp } from '@/contexts/AppContext';
import { GlassCard } from '@/components/GlassCard';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { createConsoleSession, uploadKnowledgeFile, KnowledgeArtifact } from '@/lib/console-api';
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

/* ─── Main Component ─── */

export default function PolicyUpload() {
  const {
    sessionId,
    modelProvider,
    modelName,
    embedModelName,
    modelApiKey,
    modelBaseUrl,
    uploadedFiles,
    guidingPrompts,
    knowledgeGraphReady,
    knowledgeArtifact,
    knowledgeLoading,
    knowledgeError,
    setSessionId,
    addUploadedFile,
    removeUploadedFile,
    setUploadedFiles,
    updateGuidingPrompt,
    addGuidingPrompt,
    removeGuidingPrompt,
    setKnowledgeGraphReady,
    setKnowledgeArtifact,
    setKnowledgeLoading,
    setKnowledgeError,
    completeStep,
    setCurrentStep,
  } = useApp();

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

  const graphReady = knowledgeGraphReady && knowledgeArtifact !== null;

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
    ? knowledgeArtifact.entity_nodes.filter(
        (node) => !node.ui_default_hidden && matchesFamilyFilter(node.facet_kind, familyFilter),
      )
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
    setKnowledgeGraphReady(false);
    setKnowledgeArtifact(null);
    setKnowledgeError(null);
  }, [setKnowledgeArtifact, setKnowledgeError, setKnowledgeGraphReady]);

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

  const handleExtract = useCallback(async () => {
    if (uploadedFiles.length === 0) return;

    try {
      setKnowledgeLoading(true);
      setKnowledgeError(null);

      const resolvedSessionId = sessionId ?? (
        await createConsoleSession(undefined, {
          model_provider: modelProvider,
          model_name: modelName,
          embed_model_name: embedModelName,
          api_key: modelApiKey.trim() || undefined,
          base_url: modelBaseUrl.trim() || undefined,
        })
      ).session_id;
      if (!sessionId) {
        setSessionId(resolvedSessionId);
      }

      // For now, process the first file. Multi-file merge would be handled by backend.
      const combinedPrompt = guidingPrompts.filter(p => p.trim()).join('\n\n');
      const artifact = await uploadKnowledgeFile(resolvedSessionId, uploadedFiles[0], combinedPrompt);
      setKnowledgeArtifact(artifact);
      setKnowledgeGraphReady(true);
    } catch (error) {
      // Fallback: try loading demo data from public/demo-output.json
      try {
        const demoRes = await fetch('/demo-output.json');
        if (demoRes.ok) {
          const demo = await demoRes.json();
          const knowledgeData = demo.knowledge;
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
            toast({ title: 'Demo mode', description: 'Loaded cached knowledge graph (backend unavailable)' });
            return;
          }
        }
      } catch { /* ignore demo fallback errors */ }

      const message = resolveKnowledgeExtractionError(error, {
        provider: modelProvider,
        model: modelName,
      });
      setKnowledgeGraphReady(false);
      setKnowledgeArtifact(null);
      setKnowledgeError(message);
      toast({
        title: 'Knowledge extraction failed',
        description: message,
        variant: 'destructive',
      });
    } finally {
      setKnowledgeLoading(false);
    }
  }, [
    uploadedFiles,
    sessionId,
    modelProvider,
    modelName,
    embedModelName,
    modelApiKey,
    modelBaseUrl,
    guidingPrompts,
    setKnowledgeLoading,
    setKnowledgeError,
    setSessionId,
    setKnowledgeArtifact,
    setKnowledgeGraphReady,
  ]);

  const handleProceed = () => {
    completeStep(1);
    setCurrentStep(2);
  };

  const handleUrlScrape = () => {
    if (!urlValue.trim()) return;
    // Mock: add a fake file entry for the scraped URL
    const mockFile = new File([''], urlValue.split('/').pop() || 'scraped-content.txt', { type: 'text/plain' });
    addUploadedFile(mockFile);
    setUrlValue('');
    setShowUrlInput(false);
    toast({ title: 'URL scraped', description: `Content fetched from ${urlValue}` });
  };

  const handlePasteSubmit = () => {
    if (!pasteValue.trim()) return;
    const blob = new Blob([pasteValue], { type: 'text/plain' });
    const mockFile = new File([blob], 'pasted-text.txt', { type: 'text/plain' });
    addUploadedFile(mockFile);
    setPasteValue('');
    setShowPasteArea(false);
    toast({ title: 'Text added', description: 'Pasted content added as document' });
  };

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
    ? [...knowledgeArtifact.entity_nodes]
      .filter((node) => !node.ui_default_hidden)
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
      <div className="flex flex-col border-r border-border overflow-y-auto scrollbar-thin bg-background">
        {/* Header */}
        <div className="p-5 pb-4 border-b border-border">
          <h2 className="text-lg font-bold text-foreground font-mono uppercase tracking-wider">NEW SIMULATION RUN</h2>
          <p className="text-xs text-muted-foreground mt-1">Upload unstructured documents to build the context graph</p>
          {/* Use-case badge */}
          <div className="mt-3">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-border bg-transparent text-[10px] font-mono uppercase tracking-[0.16em] text-muted-foreground">
              {modelProvider === 'gemini' ? 'Gemini 2.0' : modelProvider} · Document Processing
            </span>
          </div>
        </div>

        {/* Upload Zone */}
        <div className="p-5 border-b border-border">
          <label
            className={`flex flex-col items-center justify-center p-6 cursor-pointer transition-colors border border-dashed rounded-lg bg-transparent ${
              dragOver ? 'border-white/40 bg-white/[0.03]' : uploadedFiles.length > 0 ? 'border-border' : 'border-border hover:border-white/25'
            }`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
          >
            <input type="file" className="hidden" accept=".pdf,.docx,.doc,.txt,.md,.markdown,.html,.htm,.json,.csv,.yaml,.yml" multiple onChange={handleFileSelect} />
            <Upload className="w-6 h-6 text-muted-foreground mb-2" />
            <span className="text-sm text-foreground">Drop documents here</span>
            <span className="text-[10px] text-muted-foreground mt-1 font-mono uppercase tracking-wider">
              PDF · DOCX · TXT · MD · HTML · CSV · YAML
            </span>
          </label>

          {/* File list */}
          {uploadedFiles.length > 0 && (
            <div className="mt-3 space-y-1">
              {uploadedFiles.map((file, index) => (
                <div key={`${file.name}-${index}`} className="flex items-center justify-between px-3 py-2 rounded bg-card border border-border group">
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
              ))}
            </div>
          )}

          {/* Alt input methods */}
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={() => setShowUrlInput(!showUrlInput)}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-[10px] font-mono uppercase tracking-wider border transition-colors ${
                showUrlInput ? 'border-white/20 bg-white/5 text-foreground' : 'border-border text-muted-foreground hover:text-foreground hover:border-white/15'
              }`}
            >
              <Link className="w-3 h-3" /> URL
            </button>
            <button
              type="button"
              onClick={() => setShowPasteArea(!showPasteArea)}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-[10px] font-mono uppercase tracking-wider border transition-colors ${
                showPasteArea ? 'border-white/20 bg-white/5 text-foreground' : 'border-border text-muted-foreground hover:text-foreground hover:border-white/15'
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
              <Button onClick={handleUrlScrape} size="sm" variant="outline" className="shrink-0 border-border text-foreground">
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

        {/* Guiding Prompts */}
        <div className="p-5 border-b border-border">
          <div className="flex items-center justify-between mb-3">
            <span className="label-meta">Guiding Prompts</span>
            <div className="flex items-center gap-3">
              <select
                className="bg-transparent border border-border text-[10px] text-muted-foreground uppercase tracking-widest px-2 py-1 rounded cursor-pointer hover:text-foreground"
                onChange={(e) => {
                  const val = e.target.value;
                  if (val === 'policy') updateGuidingPrompt(0, "Identify all entities, locations, organizations, and the specific impact mechanisms described in this policy document. Focus strongly on sentiment and demographic effects.");
                  if (val === 'ad') updateGuidingPrompt(0, "Extract key product features, target demographics, and brand positioning statements. Highlight emotional triggers and pricing constraints.");
                  if (val === 'pmf') updateGuidingPrompt(0, "Analyze this product feedback for core pain points, requested features, and user satisfaction signals. Group by user persona.");
                }}
              >
                <option value="policy">Policy Review</option>
                <option value="ad">Ad Testing</option>
                <option value="pmf">PMF Discovery</option>
              </select>
              <button
                type="button"
                onClick={addGuidingPrompt}
                className="flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors"
              >
                <Plus className="w-3 h-3" /> Add Prompt
              </button>
            </div>
          </div>
          <div className="space-y-3">
            {guidingPrompts.map((prompt, index) => (
              <div key={index} className="relative group">
                <Textarea
                  value={prompt}
                  onChange={(e) => updateGuidingPrompt(index, e.target.value)}
                  placeholder={index === 0 ? 'What should the system extract from this document?' : 'Additional extraction guidance...'}
                  className={`text-sm bg-card border-border ${index === 0 ? 'min-h-[132px]' : 'min-h-[104px]'} resize-y pr-8`}
                />
                {guidingPrompts.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeGuidingPrompt(index)}
                    className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-foreground"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            ))}
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
            {graphReady && (
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

          {/* Fake Loading Log */}
          {knowledgeLoading && (
            <div className="mt-4 p-3 border border-border bg-black rounded font-mono text-[10px] text-muted-foreground w-full space-y-1">
              <div className="animate-pulse-subtle flex justify-between">
                <span>[{new Date().toLocaleTimeString('en-US', { hour12: false })}] Initializing graph builder...</span>
                <span className="text-success">OK</span>
              </div>
              <div className="animate-pulse-subtle flex justify-between" style={{ animationDelay: '0.4s' }}>
                <span>[{new Date().toLocaleTimeString('en-US', { hour12: false })}] Parsing uploaded documents...</span>
                <span className="text-success">OK</span>
              </div>
              <div className="animate-pulse-subtle flex justify-between" style={{ animationDelay: '0.8s' }}>
                <span>[{new Date().toLocaleTimeString('en-US', { hour12: false })}] Chunking & computing embeddings...</span>
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
          <div className="p-5">
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
                    ? 'border-white/20 bg-white/5 text-foreground'
                    : 'border-border text-muted-foreground hover:border-white/15 hover:text-foreground'
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
                const labelWidth = ctx.measureText(label).width;
                const backgroundX = labelX - 4;
                const backgroundY = labelY - fontSize / 2 - 3;
                const backgroundWidth = labelWidth + 8;
                const backgroundHeight = fontSize + 6;

                ctx.save();
                ctx.beginPath();
                ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
                ctx.fillStyle = nodeColor(node);
                ctx.fill();

                ctx.lineWidth = 1;
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
                ctx.stroke();

                ctx.fillStyle = 'rgba(10, 10, 10, 0.85)';
                ctx.fillRect(backgroundX, backgroundY, backgroundWidth, backgroundHeight);

                ctx.textAlign = 'left';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
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
                ctx.fillStyle = 'rgba(10, 10, 10, 0.88)';
                ctx.fillRect(
                  midX + normalX * offset - boxWidth / 2,
                  midY + normalY * offset - boxHeight / 2,
                  boxWidth,
                  boxHeight,
                );
                ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
                ctx.fillText(readableLabel, midX + normalX * offset, midY + normalY * offset);
                ctx.restore();
              }}
              linkColor={() => 'rgba(255, 255, 255, 0.08)'}
              linkWidth={1}
              linkDirectionalArrowLength={4}
              linkDirectionalArrowRelPos={1}
              backgroundColor="transparent"
              cooldownTicks={80}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              {knowledgeLoading ? (
                <div className="flex flex-col items-center gap-3">
                  <Loader2 className="w-6 h-6 animate-spin text-white/40" />
                  <span className="font-mono text-xs uppercase tracking-wider">Building graph...</span>
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
          ? 'border-white/20 bg-white/8 text-foreground'
          : 'border-border text-muted-foreground hover:border-white/15 hover:text-foreground'
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
