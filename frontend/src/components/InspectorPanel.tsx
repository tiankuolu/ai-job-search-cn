import { ArrowLeft, ArrowUpRight, Bot, FileText, Layers3, Maximize2 } from 'lucide-react';
import type { ReactNode } from 'react';
import type { FlowNode } from '../Flow';
import type { Document, JobDetail } from '../types';
import SharedFlowNode from '../ui/FlowNode';
import Empty from './Empty';
import Inspector from './Inspector';
import Markdown from './Markdown';

type Props = {
  panel: string;
  job: JobDetail | null;
  node: FlowNode | null;
  mode: string;
  onMode: (value: string) => void;
  onBack: () => void;
  onRead: (document: Document) => void;
  nodes?: FlowNode[];
  onSelectNode?: (node: FlowNode) => void;
  extra?: ReactNode;
};

export default function InspectorPanel({ panel, job, node, mode, onMode, onBack, onRead, nodes = [], onSelectNode, extra }: Props) {
  return <aside className="inspector-panel">
    <div className="panel-heading">
      <h2>{panel === 'job' ? <><FileText size={16} />岗位资料</> : <><Layers3 size={16} />节点详情</>}</h2>
      {panel === 'job' && <button className="icon-button" aria-label="返回节点详情" onClick={onBack}><ArrowLeft size={15} /></button>}
    </div>
    {extra}
    {nodes.length > 0 && panel === 'node' && <div className="ui-node-rail" role="group" aria-label="流程节点">
      {nodes.slice(0, 8).map(item => <SharedFlowNode key={item.id} title={item.data.title} meta={item.data.subtitle} status={item.data.status} selected={node?.id === item.id} onClick={onSelectNode ? () => onSelectNode(item) : undefined} />)}
    </div>}
    {panel === 'job' && job
      ? <div className="job-detail">
        <h3>{job.key}</h3>
        <button className="document-link" onClick={() => onRead({ name: `${job.key}-岗位JD.md`, content: job.content })}>
          <FileText size={17} /><span>阅读完整岗位原文</span><Maximize2 size={14} />
        </button>
        <div className="detail-caption">已有材料</div>
        {job.documents.length
          ? job.documents.map(document => <button key={document.kind} className="document-link" onClick={() => onRead(document)}>
            <FileText size={17} /><span>{document.label}</span><ArrowUpRight size={14} />
          </button>)
          : <p className="muted">该岗位暂未生成相关材料。</p>}
        <div className="detail-caption">岗位原文</div>
        <Markdown>{job.content}</Markdown>
      </div>
      : node
        ? <Inspector node={node} mode={mode} setMode={onMode} />
        : <>
          <Empty title="探索执行细节" text="点击流程中的节点，查看使用的资料、模型响应和工具执行结果。" icon={Bot} />
          <div className="inspector-tip">
            <span className="eyebrow">HOW IT WORKS</span>
            <p>左侧选择目标岗位，启动任务后，流程会随真实执行更新。</p>
            <p>运行记录保留模型输入、输出和工具结果，便于解释每一步的依据。</p>
          </div>
        </>}
  </aside>;
}
