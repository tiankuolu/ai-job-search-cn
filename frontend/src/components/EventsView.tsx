import { useState } from 'react';
import { Terminal } from 'lucide-react';
import { actionNames, agentNames, type Action, type RunDetail, type RunEvent } from '../types';
import { eventNames, readable } from '../content';
import EventRow from '../ui/EventRow';
import VirtualList from '../ui/VirtualList';
import Empty from './Empty';
import Markdown from './Markdown';

type Props = { events: RunEvent[]; run: RunDetail | null };

export default function EventsView({ events, run }: Props) {
  const [selected, setSelected] = useState<number | null>(null);
  if (!events.length) return <Empty
    title="等待执行事件"
    text={run?.source === 'legacy' ? '这条历史记录保留了模型调用，可在流程图中查看输入和输出。' : '启动任务后，这里会按实际发生顺序记录每个执行步骤。'}
    icon={Terminal}
  />;
  const current = events.find(event => event.seq === selected);
  return <div className="event-view">
    <VirtualList
      items={events}
      height={Math.min(430, Math.max(180, events.length * 52))}
      itemHeight={52}
      ariaLabel="运行事件列表"
      renderItem={event => <EventRow
        seq={event.seq}
        title={eventNames[event.type] || event.type}
        detail={event.data.name || (event.data.agent ? agentNames[event.data.agent] : undefined) || event.data.agent || event.data.error || (event.data.round ? `第 ${event.data.round} 轮${event.type === 'review.finished' ? event.data.pass ? ' · 审查通过' : ' · 审查未通过' : ''}` : event.data.action ? actionNames[event.data.action as Action] : '')}
        state={event.type.includes('failed') ? 'error' : 'default'}
        onClick={() => setSelected(event.seq)}
      />}
    />
    {current && <div className="event-detail">
      <div className="event-detail-head"><strong>事件 {current.seq} · {eventNames[current.type] || current.type}</strong><button onClick={() => setSelected(null)}>收起</button></div>
      {current.type === 'review.finished' && <Markdown>{readable(current.data.violations)}</Markdown>}
      <pre>{readable(current.data)}</pre>
    </div>}
  </div>;
}
