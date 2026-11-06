import { Activity, Clock3, Cpu, Terminal } from 'lucide-react';
import { number } from '../types';
import type { RunMetrics } from '../hooks/useRunStream';

export default function MetricsRow({ metrics }: { metrics: RunMetrics }) {
  const cards = [
    { label: '模型调用', value: number(metrics.callCount), unit: '次', Icon: Cpu, color: 'violet' },
    { label: '工具执行', value: number(metrics.toolCount), unit: '次', Icon: Terminal, color: 'blue' },
    { label: 'Token 用量', value: number(metrics.tokens), unit: 'tokens', Icon: Activity, color: 'orange' },
    { label: '模型累计耗时', value: (metrics.latency / 1000).toFixed(1), unit: '秒', Icon: Clock3, color: 'green' },
  ];
  return <section className="metrics-row">
    {cards.map(card => <div className="metric-card" key={card.label}>
      <span className={`metric-icon ${card.color}`}><card.Icon size={19} /></span>
      <div>
        <span>{card.label}</span>
        <strong>{card.value}<small>{card.unit}</small></strong>
      </div>
    </div>)}
  </section>;
}
