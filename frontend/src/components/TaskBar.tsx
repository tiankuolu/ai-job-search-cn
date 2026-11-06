import { LoaderCircle, Play } from 'lucide-react';
import { actionNames, type Action } from '../types';
import { actionDescriptions } from '../content';

type Props = {
  action: Action;
  onAction: (value: Action) => void;
  workers: number;
  onWorkers: (value: number) => void;
  canStart: boolean;
  submitting: boolean;
  onStart: () => void;
  selectedCount: number;
};

export default function TaskBar({ action, onAction, workers, onWorkers, canStart, submitting, onStart, selectedCount }: Props) {
  const note = action === 'rank'
    ? '使用全部已保存的岗位评估'
    : `已选择 ${selectedCount} 个岗位${action === 'apply' || action === 'interview' ? ' · 每次选择一个岗位' : ''}`;
  return <>
    <section className="task-bar">
      <div className="task-actions">
        {(Object.keys(actionNames) as Action[]).map(key => <button key={key} className={action === key ? 'active' : ''} onClick={() => onAction(key)}>{actionNames[key]}</button>)}
      </div>
      <div className="task-options">
        {action === 'analyze' && <label className="worker-control">并行数量
          <select aria-label="并行数量" value={workers} onChange={event => onWorkers(Number(event.target.value))}>
            {[1, 2, 3, 4, 6, 8].map(value => <option key={value}>{value}</option>)}
          </select>
        </label>}
        <button className="primary-button" disabled={!canStart} onClick={onStart}>
          {submitting ? <LoaderCircle size={15} className="spin" /> : <Play size={14} fill="currentColor" />}启动{actionNames[action]}
        </button>
      </div>
    </section>
    <div className="task-description"><span>{actionDescriptions[action]}</span><span>{note}</span></div>
  </>;
}
