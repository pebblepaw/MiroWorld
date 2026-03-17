import { useEffect, useRef } from 'react';
import * as echarts from 'echarts';

type Props = {
  title: string;
  option: echarts.EChartsOption;
};

export default function EChartPanel({ title, option }: Props) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const instance = echarts.init(ref.current);
    instance.setOption(option);
    const resize = () => instance.resize();
    window.addEventListener('resize', resize);
    return () => {
      window.removeEventListener('resize', resize);
      instance.dispose();
    };
  }, [option]);

  return (
    <section className="glass-card chart-panel">
      <h3>{title}</h3>
      <div ref={ref} className="chart-canvas" />
    </section>
  );
}
