import { ArrowUpRight, BriefcaseBusiness, FolderOpen, LoaderCircle, Search } from 'lucide-react';
import type { Job } from '../types';
import { documentNames } from '../content';
import Empty from './Empty';

type Props = {
  jobs: Job[];
  loading: boolean;
  query: string;
  onQuery: (value: string) => void;
  selected: string[];
  onToggle: (id: string, checked: boolean) => void;
  onSelectVisible: (ids: string[]) => void;
  onClear: () => void;
  onInspect: (id: string) => void;
};

export default function JobsPanel({ jobs, loading, query, onQuery, selected, onToggle, onSelectVisible, onClear, onInspect }: Props) {
  const visible = jobs.filter(item => item.title.toLowerCase().includes(query.toLowerCase()));
  return <section className="jobs-panel">
    <div className="panel-heading">
      <h2><BriefcaseBusiness size={16} />岗位列表</h2>
      <span className="count-badge">{jobs.length}</span>
    </div>
    <div className="search-field">
      <Search size={15} />
      <input placeholder="搜索公司或岗位" aria-label="搜索公司或岗位" value={query} onChange={event => onQuery(event.target.value)} />
    </div>
    <div className="selection-controls">
      <button onClick={() => onSelectVisible(visible.map(item => item.id))}>选择搜索结果</button>
      <button onClick={onClear}>清除选择</button>
    </div>
    <div className="job-list">
      {loading
        ? <div className="loading"><LoaderCircle size={18} className="spin" />正在读取岗位</div>
        : visible.length
          ? visible.map(item => <div className={`job-card${selected.includes(item.id) ? ' selected' : ''}`} key={item.id}>
            <div className="job-card-main">
              <input type="checkbox" aria-label={`选择 ${item.title}`} checked={selected.includes(item.id)} onChange={event => onToggle(item.id, event.target.checked)} />
              <button onClick={() => onInspect(item.id)}>
                <strong>{item.title}</strong>
                <span>{item.documents.length ? item.documents.map(kind => documentNames[kind]).join(' · ') : '等待分析'}</span>
              </button>
            </div>
            <button className="job-view" onClick={() => onInspect(item.id)}>查看岗位与材料<ArrowUpRight size={12} /></button>
          </div>)
          : <Empty title="没有匹配岗位" text="请调整搜索关键词或检查岗位资料目录。" icon={Search} />}
    </div>
    <div className="jobs-footer"><FolderOpen size={13} />从本地求职资料读取</div>
  </section>;
}
