import type { PopulationArtifact } from '../../types/console';
import { GraphCanvas } from './GraphCanvas';

type Props = {
  population: PopulationArtifact | null;
};

export function PersonaGraph({ population }: Props) {
  const option = population
    ? {
        tooltip: { trigger: 'item' },
        series: [
          {
            type: 'graph',
            layout: 'force',
            roam: true,
            data: population.agent_graph.nodes.map((node: any) => ({
              name: node.label ?? node.id,
              value: node.planning_area,
              symbolSize: 18 + Math.min(24, Number(node.score ?? 0) * 20),
              itemStyle: {
                color:
                  String(node.planning_area ?? '').toLowerCase().includes('woodlands')
                    ? '#d0ff7e'
                    : '#b7c7ff',
              },
            })),
            links: population.agent_graph.links.map((link: any) => ({
              source: link.source,
              target: link.target,
              value: link.reason,
            })),
            force: { repulsion: 240, edgeLength: [60, 110] },
            label: { show: true, color: '#eef3ff', fontFamily: 'Space Grotesk' },
            lineStyle: { color: '#637596', opacity: 0.68 },
          },
        ],
      }
    : { title: { text: 'No sampled cohort yet', textStyle: { color: '#dbe5ff' } } };

  return <GraphCanvas option={option} />;
}
