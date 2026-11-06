import { ChevronRight, RefreshCw } from 'lucide-react';

type Props = { page: 'workspace' | 'history' | 'delivery'; onRefresh: () => void };

export default function Topbar({ page, onRefresh }: Props) {
  return <header className="topbar">
    <div className="breadcrumb">工作空间<ChevronRight size={13} /><strong>{page === 'history' ? '运行记录' : page === 'delivery' ? '搜索与投递' : '交互工作台'}</strong></div>
    <div className="topbar-right">
      <span className="local-tag"><span />LOCAL WORKSPACE</span>
      <button className="icon-button" aria-label="刷新工作区" onClick={onRefresh}><RefreshCw size={16} /></button>
      <span className="avatar">LT</span>
    </div>
  </header>;
}
