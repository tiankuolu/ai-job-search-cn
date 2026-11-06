import { History, LoaderCircle, RefreshCw } from 'lucide-react';
import { actionNames, dateTime, statusNames, type Run } from '../types';
import TaskCard from '../ui/TaskCard';
import VirtualList from '../ui/VirtualList';
import Empty from './Empty';

type Props = { runs: Run[]; loading: boolean; onOpen: (id: string) => void; onRefresh: () => void };

export default function HistoryPage({ runs, loading, onOpen, onRefresh }: Props) {
  return <section className="history-panel">
    <div className="section-heading">
      <h2>运行记录 <span>{runs.length}</span></h2>
      <button className="text-button" onClick={onRefresh}><RefreshCw size={14} />刷新记录</button>
    </div>
    {loading
      ? <div className="loading"><LoaderCircle className="spin" />正在读取运行记录</div>
      : runs.length
        ? <div className="history-list">
          <VirtualList
            items={runs}
            height={Math.min(560, Math.max(168, runs.length * 84))}
            itemHeight={84}
            ariaLabel="运行记录列表"
            renderItem={item => <TaskCard
              title={actionNames[item.action] || item.action}
              meta={`${item.jobs.map(job => job.key).join('、') || item.run_id} · ${dateTime(item.created_at)}`}
              actions={<span className={`status ${item.status}`}>{statusNames[item.status]}</span>}
              state={item.status === 'failed' ? 'error' : 'default'}
              onClick={() => onOpen(item.run_id)}
              ariaLabel={`打开运行 ${item.run_id}，${actionNames[item.action]}，${statusNames[item.status]}`}
            />}
          />
        </div>
        : <Empty title="尚无运行记录" text="选择岗位并启动一次任务，执行过程和成果会保留在这里。" icon={History} />}
  </section>;
}
