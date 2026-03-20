import { useState, useCallback, useRef, useEffect } from 'react';
import { Upload, FileText, Sparkles, Loader2, ArrowRight } from 'lucide-react';
import ForceGraph2D from 'react-force-graph-2d';
import { useApp } from '@/contexts/AppContext';
import { GlassCard } from '@/components/GlassCard';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { createConsoleSession, uploadKnowledgeFile } from '@/lib/console-api';
import { toast } from '@/hooks/use-toast';

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
  const graphReady = knowledgeGraphReady && knowledgeArtifact !== null;

  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver(([entry]) => {
      setDimensions({ width: entry.contentRect.width, height: entry.contentRect.height });
    });
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

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

  const graphData = graphReady ? {
    nodes: knowledgeArtifact.entity_nodes.map((node) => ({
      id: node.id,
      name: node.label,
      type: node.type,
      description: node.description,
      val: Math.max(4, Math.round((node.weight ?? 0.5) * 10)),
    })),
    links: knowledgeArtifact.relationship_edges.map((edge) => ({
      ...edge,
      label: edge.label || edge.type,
    })),
  } : { nodes: [], links: [] };

  const nodeColor = (node: { type?: string }) => {
    switch (node.type) {
      case 'policy': return 'hsl(193, 100%, 50%)';
      case 'institution': return 'hsl(38, 92%, 50%)';
      case 'person':
      case 'stakeholder':
      case 'demographic': return 'hsl(160, 84%, 39%)';
      case 'planning_area':
      case 'topic':
      case 'concept': return 'hsl(280, 70%, 60%)';
      default: return 'hsl(215, 20%, 55%)';
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-full p-6">
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
          {graphReady && (
            <div className="flex gap-3">
              {[
                { label: 'Policy', color: 'bg-primary' },
                { label: 'Institution', color: 'bg-secondary' },
                { label: 'Person', color: 'bg-success' },
                { label: 'Concept', color: 'hsl(280,70%,60%)' },
              ].map(l => (
                <span key={l.label} className="flex items-center gap-1 text-[10px] text-muted-foreground">
                  <span className={`w-2 h-2 rounded-full ${l.color.startsWith('bg-') ? l.color : ''}`} style={l.color.startsWith('hsl') ? {backgroundColor: l.color} : undefined} />
                  {l.label}
                </span>
              ))}
            </div>
          )}
        </div>
        <div ref={containerRef} className="flex-1 min-h-[300px] rounded-lg overflow-hidden bg-background/30">
          {graphReady ? (
            <ForceGraph2D
              ref={graphRef}
              graphData={graphData}
              width={dimensions.width}
              height={dimensions.height}
              nodeLabel={(node: { name?: string; description?: string }) => `${node.name || ''}${node.description ? `: ${node.description}` : ''}`}
              linkLabel={(link: { label?: string }) => link.label || ''}
              nodeColor={nodeColor}
              nodeRelSize={6}
              nodeCanvasObjectMode={() => 'after'}
              nodeCanvasObject={(node: { name?: string; val?: number; x?: number; y?: number }, ctx, globalScale) => {
                const label = node.name;
                const fontSize = 11 / globalScale;
                ctx.font = `${fontSize}px Inter, sans-serif`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = 'hsl(210, 40%, 93%)';
                ctx.fillText(label, node.x!, node.y! + (node.val || 4) + fontSize + 2);
              }}
              linkColor={() => 'hsl(225, 20%, 25%)'}
              linkWidth={1.5}
              linkDirectionalArrowLength={4}
              linkDirectionalArrowRelPos={1}
              backgroundColor="transparent"
              cooldownTicks={100}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              {knowledgeLoading ? (
                <div className="flex flex-col items-center gap-3">
                  <Loader2 className="w-8 h-8 animate-spin text-primary" />
                  <span>Building knowledge graph...</span>
                </div>
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
