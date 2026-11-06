import type { ReactNode } from 'react';
import { CircleAlert, FileText, Pause, Play, Terminal, Workflow } from 'lucide-react';
import { dateTime, statusNames, terminal, type RunDetail } from '../types';

const tabs = ['流程图', '事件记录', '生成成果'];

type Props = {
  tab: string;
  onTab: (value: string) => void;
  run: RunDetail | null;
  artifactCount: number;
  streamState: string;
  playback: number | null;
  playing: boolean;
  eventCount: number;
  onPlayback: (value: number | null) => void;
  onPlaying: (value: boolean) => void;
  children: ReactNode;
};

export default function CanvasPanel({ tab, onTab, run, artifactCount, streamState, playback, playing, eventCount, onPlayback, onPlaying, children }: Props) {
  const connection = streamState === 'reconnecting' ? '连接中断，正在重新连接' : streamState === 'connected' ? '实时连接' : run ? dateTime(run.created_at) : '';
  return <section className="canvas-panel">
    <div className="canvas-header">
      <div className="content-tabs">
        {tabs.map(value => <button className={tab === value ? 'active' : ''} key={value} onClick={() => onTab(value)}>
          {value === '流程图' ? <Workflow size={15} /> : value === '事件记录' ? <Terminal size={15} /> : <FileText size={15} />}
          {value}
          {value === '生成成果' && artifactCount > 0 && <span>{artifactCount}</span>}
        </button>)}
      </div>
      {run ? <span className={`status ${run.status}`}>{statusNames[run.status]}</span> : <span className="preview-label">流程说明</span>}
    </div>
    {run && <div className="run-caption"><span title={run.run_id}>{run.run_id}</span><span>{connection}</span></div>}
    {run?.error && <div className="run-error"><CircleAlert size={15} />{run.error}</div>}
    {run?.status === 'review_required' && <div className="review-warning">材料已生成，审查仍有未通过项目。请查看审查意见和最终正文。</div>}
    <div className="canvas-body">{children}</div>
    <div className="canvas-footer">
      <span><span className="legend-dot completed" />已完成</span>
      <span><span className="legend-dot running" />执行中</span>
      <span><span className="legend-dot failed" />失败</span>
      <span className="canvas-hint">拖动浏览 · 滚轮缩放 · 点击节点查看详情</span>
    </div>
    {run && terminal(run.status) && eventCount > 0 && <div className="playback">
      <button className="icon-button" aria-label={playing ? '暂停回放' : '播放运行记录'} onClick={() => {
        if (!playing && (playback === null || playback >= eventCount)) onPlayback(0);
        onPlaying(!playing);
      }}>{playing ? <Pause size={16} /> : <Play size={16} />}</button>
      <span>运行回放</span>
      <input type="range" min={0} max={eventCount} aria-label="运行回放进度" value={playback ?? eventCount} onChange={event => { onPlaying(false); onPlayback(Number(event.target.value)); }} />
      <small>{playback ?? eventCount} / {eventCount}</small>
      <button className="text-button" onClick={() => { onPlayback(null); onPlaying(false); }}>全部事件</button>
    </div>}
  </section>;
}
