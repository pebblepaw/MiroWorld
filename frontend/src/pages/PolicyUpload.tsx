import { useState, useCallback, useRef, useEffect } from 'react';
import { Upload, FileText, Sparkles, Loader2, ArrowRight, Eye, EyeOff } from 'lucide-react';
import { forceCollide, forceManyBody } from 'd3-force-3d';
import ForceGraph2D from 'react-force-graph-2d';
import { useApp } from '@/contexts/AppContext';
import { GlassCard } from '@/components/GlassCard';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { createConsoleSession, uploadKnowledgeFile } from '@/lib/console-api';
import { toast } from '@/hooks/use-toast';

const DISPLAY_BUCKET_STYLES: Record<string, { label: string; color: string }> = {
  organization: { label: 'Organization', color: 'hsl(215, 20%, 62%)' },
  persons: { label: 'Persons', color: 'hsl(160, 84%, 42%)' },
  location: { label: 'Location', color: 'hsl(38, 92%, 54%)' },
  age_group: { label: 'Age Group', color: 'hsl(142, 68%, 50%)' },
  event: { label: 'Event', color: 'hsl(0, 78%, 58%)' },
  concept: { label: 'Concept', color: 'hsl(196, 92%, 56%)' },
  industry: { label: 'Industry', color: 'hsl(266, 70%, 64%)' },
  other: { label: 'Other', color: 'hsl(215, 18%, 47%)' },
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
    `Could not reach the backend during Screen 1 extraction while using ` +
    `${context.provider}/${context.model}. ` +
    `Check that the backend is running and that the selected provider runtime is reachable.`
  );
}

export default function PolicyUpload() {
  const {
    sessionId,
    modelProvider,
    modelName,
    embedModelName,
    modelApiKey,
    modelBaseUrl,
    uploadedFile,
    guidingPrompt,
    knowledgeGraphReady,
    knowledgeArtifact,
    knowledgeLoading,
    knowledgeError,
    setSessionId,
    setUploadedFile,
    setGuidingPrompt,
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
    const f = e.dataTransfer.files[0];
    if (f) {
      setUploadedFile(f);
      resetKnowledgeState();
    }
  }, [resetKnowledgeState, setUploadedFile]);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) {
      setUploadedFile(f);
      resetKnowledgeState();
    }
  }, [resetKnowledgeState, setUploadedFile]);

  const handleExtract = useCallback(async () => {
    if (!uploadedFile) {
      return;
    }

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

      const artifact = await uploadKnowledgeFile(resolvedSessionId, uploadedFile, guidingPrompt);
      setKnowledgeArtifact(artifact);
      setKnowledgeGraphReady(true);
    } catch (error) {
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
    uploadedFile,
    sessionId,
    modelProvider,
    modelName,
    embedModelName,
    modelApiKey,
    modelBaseUrl,
    guidingPrompt,
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

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[0.88fr_1.12fr] gap-6 h-full p-6">
      <div className="flex flex-col gap-4">
        <div>
          <h2 className="text-xl font-bold text-foreground mb-1">Policy Document Upload</h2>
          <p className="text-sm text-muted-foreground">Upload policy documents to build a knowledge graph using LightRAG</p>
        </div>

        <GlassCard glow={dragOver ? 'primary' : 'none'} className="p-0">
          <label
            className={`flex flex-col items-center justify-center p-8 cursor-pointer transition-all border-2 border-dashed rounded-xl ${
              dragOver ? 'border-primary bg-primary/5' : uploadedFile ? 'border-success/30 bg-success/5' : 'border-border hover:border-primary/40'
            }`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
          >
            <input type="file" className="hidden" accept=".pdf,.docx,.doc,.txt,.md,.markdown,.html,.htm,.json,.csv,.yaml,.yml" onChange={handleFileSelect} />
            {uploadedFile ? (
              <>
                <FileText className="w-10 h-10 text-success mb-3" />
                <span className="text-foreground font-medium">{uploadedFile.name}</span>
                <span className="text-muted-foreground text-xs mt-1">File ready for extraction</span>
              </>
            ) : (
              <>
                <Upload className="w-10 h-10 text-muted-foreground mb-3" />
                <span className="text-foreground font-medium">Drop your policy document here</span>
                <span className="text-muted-foreground text-xs mt-1">PDF, DOCX, TXT, MD, HTML, JSON, CSV, YAML supported</span>
              </>
            )}
          </label>
        </GlassCard>

        <GlassCard className="p-4">
          <label htmlFor="guiding-prompt" className="text-sm font-medium text-foreground mb-2 block">Guiding Prompt</label>
          <Textarea
            id="guiding-prompt"
            value={guidingPrompt}
            onChange={(e) => setGuidingPrompt(e.target.value)}
            placeholder="What should the system extract from this document?"
            className="bg-background/50 border-border text-foreground min-h-[100px] resize-none"
          />
        </GlassCard>

        <div className="flex gap-3">
          <Button
            onClick={handleExtract}
            disabled={!uploadedFile || knowledgeLoading}
            className="flex-1 bg-primary text-primary-foreground hover:bg-primary/90"
          >
            {knowledgeLoading ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Extracting...</>
            ) : (
              <><Sparkles className="w-4 h-4" /> Extract Knowledge Graph</>
            )}
          </Button>
          {graphReady && (
            <Button onClick={handleProceed} variant="outline" className="border-success/30 text-success hover:bg-success/10">
              <ArrowRight className="w-4 h-4" /> Proceed
            </Button>
          )}
        </div>
        {knowledgeError && (
          <p className="text-xs text-destructive">{knowledgeError}</p>
        )}

        {graphReady && (
          <>
            <GlassCard className="p-4 flex gap-6">
              <Stat label="Entity Count" value={knowledgeArtifact.entity_nodes.length} />
              <Stat label="Relationship Count" value={knowledgeArtifact.relationship_edges.length} />
              <Stat label="Paragraph Count" value={knowledgeArtifact.document.paragraph_count ?? 0} />
            </GlassCard>
            <GlassCard className="p-4">
              <div className="text-[10px] text-muted-foreground uppercase tracking-[0.24em]">Top 3 Entities</div>
              <div className="mt-3 space-y-3">
                {topEntities.map((node) => {
                  const bucket = resolveDisplayBucket(node.type, node.facet_kind, node.display_bucket);
                  const style = DISPLAY_BUCKET_STYLES[bucket] ?? DISPLAY_BUCKET_STYLES.other;
                  return (
                    <div key={node.id} className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-sm text-foreground">{node.label}</div>
                        <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">{style.label}</div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-mono text-primary">{normalizeImportance(node.importance_score, node.weight).toFixed(2)}</div>
                        <div className="text-[10px] text-muted-foreground">support {node.support_count ?? 0}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </GlassCard>
          </>
        )}
      </div>

      <GlassCard glow={graphReady ? 'primary' : 'none'} className="p-4 flex flex-col">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-foreground">Knowledge Graph</h3>
          {graphReady && legendEntries.length > 0 && (
            <div className="flex flex-wrap justify-end gap-3">
              {legendEntries.map((entry) => (
                <span key={entry.label} className="flex items-center gap-1 text-[10px] text-muted-foreground">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
                  {entry.label}
                </span>
              ))}
            </div>
          )}
        </div>
        {graphReady && (
          <div className="mb-3 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <SegmentedControl
                value={familyFilter}
                options={[
                  { value: 'all', label: 'All' },
                  { value: 'nemotron', label: 'Nemotron Entities' },
                  { value: 'other', label: 'Other Entities' },
                ]}
                onChange={(nextValue) => setFamilyFilter(nextValue as FamilyFilter)}
              />
              <button
                type="button"
                onClick={() => setShowRelationshipLabels((current) => !current)}
                className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[10px] uppercase tracking-[0.18em] transition-colors ${
                  showRelationshipLabels
                    ? 'border-primary/60 bg-primary/10 text-foreground'
                    : 'border-white/8 bg-white/4 text-muted-foreground hover:border-white/15 hover:text-foreground'
                }`}
              >
                {showRelationshipLabels ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
                {showRelationshipLabels ? 'Relationship Labels On' : 'Relationship Labels Off'}
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
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
        <div ref={containerRef} className="flex-1 min-h-[300px] rounded-lg overflow-hidden bg-background/30">
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
                ctx.font = `${fontSize}px Inter, sans-serif`;
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
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.18)';
                ctx.stroke();

                ctx.fillStyle = 'rgba(8, 10, 16, 0.78)';
                ctx.fillRect(backgroundX, backgroundY, backgroundWidth, backgroundHeight);

                ctx.textAlign = 'left';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = 'hsl(210, 40%, 93%)';
                ctx.fillText(label, labelX, labelY);
                ctx.restore();
              }}
              linkCanvasObjectMode={() => 'after'}
              linkCanvasObject={(link: GraphLinkDatum, ctx, globalScale) => {
                if (!showRelationshipLabels) {
                  return;
                }
                const label = (link.label || link.type || '').trim();
                const source = typeof link.source === 'string' ? undefined : link.source;
                const target = typeof link.target === 'string' ? undefined : link.target;
                if (!label || typeof source?.x !== 'number' || typeof source?.y !== 'number' || typeof target?.x !== 'number' || typeof target?.y !== 'number') {
                  return;
                }

                const midX = (source.x + target.x) / 2;
                const midY = (source.y + target.y) / 2;
                const dx = target.x - source.x;
                const dy = target.y - source.y;
                const length = Math.hypot(dx, dy) || 1;
                const normalX = -dy / length;
                const normalY = dx / length;
                const readableLabel = shortenLabel(label, Math.max(12, Math.floor(length / 8)));
                const fontSize = Math.max(8.5, 10.5 / globalScale);
                ctx.font = `${fontSize}px Inter, sans-serif`;
                const textWidth = ctx.measureText(readableLabel).width;
                const boxWidth = textWidth + 12;
                const boxHeight = fontSize + 8;
                const offset = Math.min(22, Math.max(10, length * 0.08));

                ctx.save();
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = 'rgba(8, 10, 16, 0.84)';
                ctx.fillRect(
                  midX + normalX * offset - boxWidth / 2,
                  midY + normalY * offset - boxHeight / 2,
                  boxWidth,
                  boxHeight,
                );
                ctx.fillStyle = 'hsl(210, 28%, 96%)';
                ctx.fillText(readableLabel, midX + normalX * offset, midY + normalY * offset);
                ctx.restore();
              }}
              linkColor={() => 'hsl(225, 20%, 25%)'}
              linkWidth={1.25}
              linkDirectionalArrowLength={4}
              linkDirectionalArrowRelPos={1}
              backgroundColor="transparent"
              cooldownTicks={80}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              {knowledgeLoading ? (
                <div className="flex flex-col items-center gap-3">
                  <Loader2 className="w-8 h-8 animate-spin text-primary" />
                  <span>Building knowledge graph...</span>
                </div>
              ) : graphReady ? (
                'No nodes match the current graph filters'
              ) : (
                'Upload a document to generate the knowledge graph'
              )}
            </div>
          )}
        </div>
      </GlassCard>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="text-xl font-bold font-mono text-primary">{value}</div>
      <div className="text-[10px] text-muted-foreground uppercase tracking-wider">{label}</div>
    </div>
  );
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

function FilterChip({
  active,
  label,
  onClick,
  accent,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
  accent?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-3 py-1 text-[10px] tracking-[0.16em] uppercase transition-colors ${
        active
          ? 'border-primary/70 bg-primary/12 text-foreground'
          : 'border-white/8 bg-white/4 text-muted-foreground hover:border-white/15 hover:text-foreground'
      }`}
      style={active && accent ? { borderColor: accent, boxShadow: `inset 0 0 0 1px ${accent}` } : undefined}
    >
      {label}
    </button>
  );
}

function SegmentedControl({
  value,
  options,
  onChange,
}: {
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <div className="inline-flex items-center gap-1 rounded-full border border-white/8 bg-white/4 p-1">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={`rounded-full px-3 py-1.5 text-[10px] uppercase tracking-[0.18em] transition-colors ${
            option.value === value
              ? 'bg-primary/18 text-foreground shadow-[inset_0_0_0_1px_rgba(91,143,255,0.35)]'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function shortenLabel(label: string, maxLength: number) {
  if (label.length <= maxLength) return label;
  return `${label.slice(0, Math.max(6, maxLength - 1))}…`;
}

function sameStringArray(left: string[], right: string[]) {
  if (left.length !== right.length) return false;
  return left.every((value, index) => value === right[index]);
}
