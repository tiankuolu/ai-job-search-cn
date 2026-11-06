import { ArrowUpRight, ChevronRight, History, Layers3, Workflow } from 'lucide-react';
import { actionNames, type Action, type Meta, type Run } from '../types';

type Props = {
  page: 'workspace' | 'history' | 'delivery';
  onPage: (value: 'workspace' | 'history' | 'delivery') => void;
  runs: Run[];
  action: Action;
  onAction: (value: Action) => void;
  meta: Meta | null;
  onRefreshRuns: () => void;
};

export default function Navigation({ page, onPage, runs, action, onAction, meta, onRefreshRuns }: Props) {
  return <aside className="navigation">
    <a className="brand" href="/" aria-label="求职 Agent 工作台">
      <span><Layers3 size={22} /></span>
      <div>求职 Agent<small>JOBSEARCH STUDIO</small></div>
    </a>
    <div className="nav-caption">工作空间</div>
    <button className={`nav-item${page === 'workspace' ? ' active' : ''}`} onClick={() => onPage('workspace')}>
      <Workflow size={18} />交互工作台<ChevronRight size={14} />
    </button>
    <button className={`nav-item${page === 'history' ? ' active' : ''}`} onClick={() => { onPage('history'); onRefreshRuns(); }}>
      <History size={18} />运行记录<span className="nav-count">{runs.length}</span>
    </button>
    <div className="nav-separator" />
    <button className={`nav-item${page === 'delivery' ? ' active' : ''}`} onClick={() => onPage('delivery')}>
      <ArrowUpRight size={18} />搜索与投递<ChevronRight size={14} />
    </button>
    <div className="nav-caption">任务能力</div>
    {(Object.keys(actionNames) as Action[]).map(key => <button
      className={`nav-task${action === key && page === 'workspace' ? ' chosen' : ''}`}
      key={key}
      onClick={() => onAction(key)}
    >
      <span className={`task-dot ${key}`} />{actionNames[key]}<ArrowUpRight size={13} />
    </button>)}
    <div className="nav-bottom">
      <div className="system-state"><span className={`live-dot${meta?.configured ? '' : ' offline'}`} />{meta?.configured ? '模型配置就绪' : '等待模型配置'}</div>
      <strong>{meta?.model || '未设置模型'}</strong>
      <p>本机运行 · 真实任务记录</p>
    </div>
  </aside>;
}
