import { useMemo } from 'react';
import type { ReportFrictionMap } from '../../types/console';
import { GraphCanvas } from '../graphs/GraphCanvas';

type Props = {
  friction: ReportFrictionMap | null;
  mapReady: boolean;
};

export function FrictionMap({ friction, mapReady }: Props) {
  const option = useMemo(() => {
    if (!mapReady) {
      return { title: { text: 'Loading Singapore planning areas…', textStyle: { color: '#eaf1ff' } } };
    }
    const rows = friction?.map_metrics ?? [];
    return {
      tooltip: { trigger: 'item' },
      visualMap: {
        min: 0,
        max: 1,
        orient: 'horizontal',
        left: 'center',
        bottom: 8,
        inRange: { color: ['#3fee71', '#f6ce39', '#e96339', '#cc3344'] },
        textStyle: { color: '#dfe7ff' },
      },
      series: [
        {
          type: 'map',
          map: 'sg-planning-areas',
          roam: true,
          emphasis: { label: { color: '#ffffff' } },
          data: rows.map((row: any) => ({
            name: String(row.planning_area ?? '').toUpperCase(),
            value: Number(row.friction_index ?? row.friction ?? 0),
          })),
        },
      ],
    };
  }, [friction, mapReady]);

  return <GraphCanvas option={option} />;
}
