import type { KnowledgeArtifact } from '../../types/console';
import { GraphCanvas } from './GraphCanvas';

type Props = {
  artifact: KnowledgeArtifact | null;
};

export function KnowledgeGraph({ artifact }: Props) {
  const option = artifact
    ? {
        tooltip: { trigger: 'item' },
        series: [
          {
            type: 'graph',
            layout: 'force',
            roam: true,
            data: artifact.entity_nodes.map((node) => ({
              name: node.label,
              category: node.type,
              symbolSize: node.type === 'policy' ? 32 : node.type === 'planning_area' ? 24 : 20,
            })),
            links: artifact.relationship_edges.map((edge) => ({
              source: artifact.entity_nodes.find((node) => node.id === edge.source)?.label ?? edge.source,
              target: artifact.entity_nodes.find((node) => node.id === edge.target)?.label ?? edge.target,
              value: edge.type,
            })),
            force: { repulsion: 280, edgeLength: [80, 150] },
            label: { show: true, color: '#eef3ff', fontFamily: 'Space Grotesk' },
            lineStyle: { color: '#6176ae', opacity: 0.74 },
          },
        ],
      }
    : { title: { text: 'No knowledge graph loaded', textStyle: { color: '#dbe5ff' } } };

  return <GraphCanvas option={option} />;
}
