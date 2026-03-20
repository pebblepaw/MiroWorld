import { useEffect, useRef } from 'react';
import * as echarts from 'echarts';

type Props = {
  option: echarts.EChartsOption;
  className?: string;
};

export function GraphCanvas({ option, className }: Props) {
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

  return <div ref={ref} className={className ?? 'mk-chart'} />;
}
