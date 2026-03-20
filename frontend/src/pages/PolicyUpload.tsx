import { useState, useCallback, useRef, useEffect } from 'react';
import { Upload, FileText, Sparkles, Loader2, ArrowRight } from 'lucide-react';
import ForceGraph2D from 'react-force-graph-2d';
import { useApp } from '@/contexts/AppContext';
import { GlassCard } from '@/components/GlassCard';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { createConsoleSession, uploadKnowledgeFile } from '@/lib/console-api';
import { toast } from '@/hooks/use-toast';

const NODE_TYPE_STYLES: Record<string, { label: string; color: string }> = {
  policy: { label: 'Policy', color: 'hsl(193, 100%, 50%)' },
  organization: { label: 'Organization', color: 'hsl(215, 20%, 55%)' },
  institution: { label: 'Organization', color: 'hsl(215, 20%, 55%)' },
  person: { label: 'Person', color: 'hsl(160, 84%, 39%)' },
  stakeholder: { label: 'Person', color: 'hsl(160, 84%, 39%)' },
  demographic: { label: 'Population', color: 'hsl(160, 84%, 39%)' },
  population: { label: 'Population', color: 'hsl(160, 84%, 39%)' },
  location: { label: 'Location', color: 'hsl(38, 92%, 50%)' },
  planning_area: { label: 'Planning Area', color: 'hsl(38, 92%, 50%)' },
  age_cohort: { label: 'Age Cohort', color: 'hsl(146, 64%, 46%)' },
  sex: { label: 'Sex', color: 'hsl(331, 72%, 62%)' },
  education_level: { label: 'Education', color: 'hsl(47, 90%, 58%)' },
  marital_status: { label: 'Marital Status', color: 'hsl(6, 86%, 64%)' },
  occupation: { label: 'Occupation', color: 'hsl(226, 78%, 66%)' },
  industry: { label: 'Industry', color: 'hsl(264, 70%, 63%)' },
  hobby: { label: 'Interest', color: 'hsl(96, 62%, 52%)' },
  skill: { label: 'Skill', color: 'hsl(189, 82%, 63%)' },
  topic: { label: 'Topic', color: 'hsl(280, 70%, 60%)' },
  concept: { label: 'Concept', color: 'hsl(280, 70%, 60%)' },
  event: { label: 'Event', color: 'hsl(0, 72%, 51%)' },
  program: { label: 'Program', color: 'hsl(193, 100%, 50%)' },
  law: { label: 'Law', color: 'hsl(215, 20%, 68%)' },
  metric: { label: 'Metric', color: 'hsl(280, 70%, 60%)' },
  funding: { label: 'Funding', color: 'hsl(38, 92%, 50%)' },
  entity: { label: 'Other', color: 'hsl(215, 20%, 55%)' },
  other: { label: 'Other', color: 'hsl(215, 20%, 55%)' },
};

const NODE_DOT_RADIUS = 4;
const NODE_LABEL_GAP = 8;
type FamilyFilter = 'all' | 'document' | 'facet';

export default function PolicyUpload() {
  const {
    sessionId,
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
  const graphRef = useRef<unknown>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 500, height: 400 });
  const [familyFilter, setFamilyFilter] = useState<FamilyFilter>('all');
  const [activeTypeKeys, setActiveTypeKeys] = useState<string[]>([]);
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
    if (!graphReady || !knowledgeArtifact) {
      setFamilyFilter('all');
      setActiveTypeKeys([]);
      return;
    }

    const nextTypeKeys = Array.from(
      new Set(
        knowledgeArtifact.entity_nodes.map((node) => resolveNodeStyleKey(node.type, node.facet_kind)),
      ),
    );
    setActiveTypeKeys(nextTypeKeys);
  }, [graphReady, knowledgeArtifact]);

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

      const resolvedSessionId = sessionId ?? (await createConsoleSession()).session_id;
      if (!sessionId) {
        setSessionId(resolvedSessionId);
      }

      const artifact = await uploadKnowledgeFile(resolvedSessionId, uploadedFile, guidingPrompt);
      setKnowledgeArtifact(artifact);
      setKnowledgeGraphReady(true);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Knowledge extraction failed.';
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

  const availableTypeKeys = graphReady
    ? Array.from(
        new Set(
          knowledgeArtifact.entity_nodes.map((node) => resolveNodeStyleKey(node.type, node.facet_kind)),
        ),
      )
    : [];

  const filteredSourceNodes = graphReady
    ? knowledgeArtifact.entity_nodes.filter((node) => {
        const styleKey = resolveNodeStyleKey(node.type, node.facet_kind);
        const families = node.families ?? ['document'];
        const familyMatch = familyFilter === 'all' ? true : families.includes(familyFilter);
        const typeMatch = activeTypeKeys.length === 0 ? true : activeTypeKeys.includes(styleKey);
        return familyMatch && typeMatch;
      })
    : [];

  const filteredNodeIds = new Set(filteredSourceNodes.map((node) => node.id));

  const graphData = graphReady ? {
    nodes: filteredSourceNodes.map((node) => ({
      id: node.id,
      name: node.label,
      type: normalizeNodeType(node.type),
      styleKey: resolveNodeStyleKey(node.type, node.facet_kind),
      facetKind: node.facet_kind,
      families: node.families ?? ['document'],
      description: node.description,
      val: 1,
    })),
    links: knowledgeArtifact.relationship_edges
      .filter((edge) => filteredNodeIds.has(edge.source) && filteredNodeIds.has(edge.target))
      .map((edge) => ({
        ...edge,
        label: edge.label || edge.raw_relation_text || edge.type,
      })),
  } : { nodes: [], links: [] };

  const legendEntries = graphReady
    ? Array.from(
        new Map(
          graphData.nodes.map((node: { styleKey?: string }) => {
            const styleKey = node.styleKey || 'other';
            const style = NODE_TYPE_STYLES[styleKey] ?? NODE_TYPE_STYLES.other;
            return [`${style.label}:${style.color}`, style] as const;
          }),
        ).values(),
      )
    : [];

  const nodeColor = (node: { type?: string; styleKey?: string; facetKind?: string }) => {
    return (NODE_TYPE_STYLES[node.styleKey || resolveNodeStyleKey(node.type, node.facetKind)] ?? NODE_TYPE_STYLES.other).color;
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[0.92fr_1.08fr] gap-6 h-full p-6">
      {/* Left Panel */}
      <div className="flex flex-col gap-4">
        <div>
          <h2 className="text-xl font-bold text-foreground mb-1">Policy Document Upload</h2>
          <p className="text-sm text-muted-foreground">Upload policy documents to build a knowledge graph using LightRAG</p>
        </div>

        {/* Upload Zone */}
        <GlassCard glow={dragOver ? 'primary' : 'none'} className="p-0">
          <label
            className={`flex flex-col items-center justify-center p-8 cursor-pointer transition-all border-2 border-dashed rounded-xl ${
              dragOver ? 'border-primary bg-primary/5' : uploadedFile ? 'border-success/30 bg-success/5' : 'border-border hover:border-primary/40'
            }`}
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
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

        {/* Guiding Prompt */}
        <GlassCard className="p-4">
          <label htmlFor="guiding-prompt" className="text-sm font-medium text-foreground mb-2 block">Guiding Prompt</label>
          <Textarea
            id="guiding-prompt"
            value={guidingPrompt}
            onChange={e => setGuidingPrompt(e.target.value)}
            placeholder="What should the system extract from this document?"
            className="bg-background/50 border-border text-foreground min-h-[100px] resize-none"
          />
        </GlassCard>

        {/* Action Buttons */}
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

        {/* Stats */}
        {graphReady && (
          <GlassCard className="p-4 flex gap-6">
            <Stat label="Entities" value={knowledgeArtifact.entity_nodes.length} />
            <Stat label="Relationships" value={knowledgeArtifact.relationship_edges.length} />
            <Stat label="Text Length" value={knowledgeArtifact.document.text_length ?? 0} />
          </GlassCard>
        )}
      </div>

      {/* Right Panel — Knowledge Graph */}
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
          <div className="mb-3 flex flex-wrap gap-2">
            <FilterChip active={familyFilter === 'all'} label="All" onClick={() => setFamilyFilter('all')} />
            <FilterChip active={familyFilter === 'document'} label="Document" onClick={() => setFamilyFilter('document')} />
            <FilterChip active={familyFilter === 'facet'} label="Facet" onClick={() => setFamilyFilter('facet')} />
            {availableTypeKeys.map((typeKey) => {
              const style = NODE_TYPE_STYLES[typeKey] ?? NODE_TYPE_STYLES.other;
              const isActive = activeTypeKeys.includes(typeKey);
              return (
                <FilterChip
                  key={typeKey}
                  active={isActive}
                  label={style.label}
                  accent={style.color}
                  onClick={() => {
                    setActiveTypeKeys((current) => (
                      current.length === availableTypeKeys.length
                        ? [typeKey]
                        : current.includes(typeKey)
                          ? (current.filter((value) => value !== typeKey).length > 0
                            ? current.filter((value) => value !== typeKey)
                            : availableTypeKeys)
                          : [...current, typeKey]
                    ));
                  }}
                />
              );
            })}
          </div>
        )}
        <div ref={containerRef} className="flex-1 min-h-[300px] rounded-lg overflow-hidden bg-background/30">
          {graphReady && graphData.nodes.length > 0 ? (
            <ForceGraph2D
              ref={graphRef}
              graphData={graphData}
              width={dimensions.width}
              height={dimensions.height}
              nodeLabel={(node: { name?: string; description?: string }) => `${node.name || ''}${node.description ? `: ${node.description}` : ''}`}
              linkLabel={(link: { label?: string }) => link.label || ''}
              nodeColor={nodeColor}
              nodeRelSize={2}
              nodeCanvasObjectMode={() => 'replace'}
              nodeCanvasObject={(node: { name?: string; type?: string; styleKey?: string; facetKind?: string; x?: number; y?: number }, ctx, globalScale) => {
                if (typeof node.x !== 'number' || typeof node.y !== 'number') return;

                const label = node.name || '';
                const fontSize = Math.max(8, 11 / globalScale);
                ctx.font = `${fontSize}px Inter, sans-serif`;
                const labelX = node.x + NODE_DOT_RADIUS + NODE_LABEL_GAP;
                const labelY = node.y;
                const labelWidth = ctx.measureText(label).width;
                const backgroundX = labelX - 4;
                const backgroundY = labelY - fontSize / 2 - 3;
                const backgroundWidth = labelWidth + 8;
                const backgroundHeight = fontSize + 6;

                ctx.save();
                ctx.beginPath();
                ctx.arc(node.x, node.y, NODE_DOT_RADIUS, 0, Math.PI * 2);
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
              linkCanvasObject={(link: { label?: string; type?: string; source?: { x?: number; y?: number }; target?: { x?: number; y?: number } }, ctx, globalScale) => {
                const label = (link.label || link.type || '').trim();
                const source = link.source;
                const target = link.target;
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
                ctx.fillText(
                  readableLabel,
                  midX + normalX * offset,
                  midY + normalY * offset,
                );
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

function resolveNodeStyleKey(type?: string, facetKind?: string | null) {
  const normalizedFacet = (facetKind || '').trim().toLowerCase();
  if (normalizedFacet && NODE_TYPE_STYLES[normalizedFacet]) return normalizedFacet;
  const normalizedType = normalizeNodeType(type);
  return NODE_TYPE_STYLES[normalizedType] ? normalizedType : 'other';
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

function shortenLabel(label: string, maxLength: number) {
  if (label.length <= maxLength) return label;
  return `${label.slice(0, Math.max(6, maxLength - 1))}…`;
}
