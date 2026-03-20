import { useEffect, useRef } from 'react';
import * as echarts from 'echarts';

type Props = {
  title: string;
  option: echarts.EChartsOption;
  onItemClick?: (params: unknown) => void;
};

export default function EChartPanel({ title, option, onItemClick }: Props) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const instance = echarts.init(ref.current);
    instance.setOption(option);
    const clickHandler = (params: unknown) => onItemClick?.(params);
    if (onItemClick) {
      instance.on('click', clickHandler);
    }
    const resize = () => instance.resize();
    window.addEventListener('resize', resize);
    return () => {
      if (onItemClick) {
        instance.off('click', clickHandler);
      }
      window.removeEventListener('resize', resize);
      instance.dispose();
    };
  }, [option, onItemClick]);

  return (
    <section className="glass-card chart-panel">
      <h3>{title}</h3>
      <div ref={ref} className="chart-canvas" />
    </section>
  );
}
