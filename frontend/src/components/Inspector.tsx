import { Clock3, Cpu } from 'lucide-react';
import type { FlowNode } from '../Flow';
import { number, statusNames, type Call } from '../types';
import { readable } from '../content';
import Markdown from './Markdown';

type Props = { node: FlowNode; mode: string; setMode: (value: string) => void };

export default function Inspector({ node, mode, setMode }: Props) {
  const data = node.data.detail;
  return <>
    <div className="inspector-heading">
      <span className={`kind-icon ${node.data.kind}`}><Cpu size={19} /></span>
      <div><span className="eyebrow">NODE INSPECTOR</span><h3>{node.data.title}</h3></div>
    </div>
    <div className="node-meta">
      <span className={`status ${node.data.status}`}>{statusNames[node.data.status] || node.data.status}</span>
      <span>{node.data.kind === 'llm' ? '模型调用' : node.data.kind === 'tool' ? '工具调用' : '执行节点'}</span>
    </div>
    {data.latency_ms !== undefined && <div className="detail-metrics">
      <span><Clock3 size={13} />{(data.latency_ms / 1000).toFixed(2)} 秒</span>
      {data.prompt_tokens !== undefined && <span>{number(data.prompt_tokens + (data.completion_tokens || 0))} tokens</span>}
    </div>}
    <div className="inspector-tabs">
      {['输出', '输入', '详情'].map(value => <button key={value} className={mode === value ? 'active' : ''} onClick={() => setMode(value)}>{value}</button>)}
    </div>
    <div className="inspector-content">
      {mode === '输出' && (data.error
        ? <div className="error-inline">{data.error}</div>
        : data.response?.content || data.output !== undefined
          ? <Markdown>{readable(data.response?.content || data.output)}</Markdown>
          : data.response?.tool_calls?.length
            ? <><p className="muted">模型请求执行以下工具：</p><pre>{JSON.stringify(data.response.tool_calls, null, 2)}</pre></>
            : <p className="muted">{node.data.status === 'planned' ? node.data.subtitle : node.data.status === 'running' ? '等待该节点返回结果。' : '该节点没有文本输出。'}</p>)}
      {mode === '输入' && (data.messages
        ? data.messages.map((message: Call['messages'][number], index: number) => <details key={index} open={message.role === 'user'}>
          <summary>{message.role}</summary><Markdown>{readable(message.content || message)}</Markdown>
        </details>)
        : data.arguments
          ? <pre>{JSON.stringify(data.arguments, null, 2)}</pre>
          : <Markdown>{data.input || data.description || '该节点没有独立输入。'}</Markdown>)}
      {mode === '详情' && <pre>{JSON.stringify(Object.fromEntries(Object.entries(data).filter(([key]) => !['messages', 'output', 'input', 'response'].includes(key))), null, 2)}</pre>}
    </div>
  </>;
}
