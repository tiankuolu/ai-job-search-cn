import { useEffect, useMemo, useRef, useState, memo } from 'react';
import { Background, Controls, MarkerType, ReactFlow, useStore, useReactFlow, type Node, type Edge, type NodeProps } from '@xyflow/react';
import mermaid from 'mermaid';
import { actionNames, agentNames, statusNames, terminal, type Action, type RunDetail, type RunEvent } from './types';

mermaid.initialize({
  startOnLoad: false, securityLevel: 'strict', theme: 'base',
  fontFamily: 'Microsoft YaHei, sans-serif',
  themeVariables: { primaryColor: '#ffffff', primaryTextColor: '#665778', primaryBorderColor: '#d8cfe7', lineColor: '#b6a9c8', fontSize: '12px' },
  flowchart: { htmlLabels: false, useMaxWidth: false, curve: 'basis', rankSpacing: 35, nodeSpacing: 30, padding: 17 },
});
let diagramCounter = 0;

export type FlowData = {
  title: string; subtitle: string; status: string; kind: string;
  detail: Record<string, any>; [key: string]: unknown;
};
export type FlowNode = Node<FlowData, 'process'>;
type DiagramNode = Node<{ svg: string; processes: FlowNode[]; select: (node: FlowNode) => void }, 'mermaid'>;

const MermaidNode = memo(({ data }: NodeProps<DiagramNode>) => {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    data.processes.forEach((process, index) => {
      const element = container.current?.querySelector(`[id*="-flowchart-n${index}-"]`);
      if (element) {
        element.setAttribute('data-process-id', process.id);
        element.setAttribute('role', 'button');
        element.setAttribute('tabindex', '0');
        element.setAttribute('aria-label', `${process.data.title}，${statusNames[process.data.status] || process.data.status}`);
        element.classList.add('nopan');
      }
    });
  }, [data]);
  function select(target: EventTarget | null) {
    const element = target instanceof Element ? target.closest('[data-process-id]') : null;
    const process = data.processes.find(node => node.id === element?.getAttribute('data-process-id'));
    if (process) {
      container.current?.querySelectorAll('.is-selected').forEach(node => node.classList.remove('is-selected'));
      element?.classList.add('is-selected');
      data.select(process);
    }
  }
  return <div ref={container} className="mermaid-diagram nodrag" onClick={event => select(event.target)}
    onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); select(event.target); } }}
    dangerouslySetInnerHTML={{ __html: data.svg }} />;
});
const nodeTypes = { mermaid: MermaidNode };

const blueprints: Record<Action, { title: string; subtitle: string; kind: string }[]> = {
  analyze: [
    { title: '读取岗位与个人资料', subtitle: '岗位原文 · 个人档案 · 项目证据', kind: 'run' },
    { title: '并行分析选中岗位', subtitle: '独立 Agent 调用工具读取资料', kind: 'agent' },
    { title: '保存岗位评估', subtitle: '匹配依据 · 相关成果 · 申请建议', kind: 'output' },
  ],
  apply: [
    { title: '读取岗位与事实依据', subtitle: '岗位原文 · 已有评估 · 项目证据', kind: 'run' },
    { title: '生成申请材料', subtitle: '材料写作 Agent', kind: 'agent' },
    { title: '审查与修改', subtitle: '最多三轮审查，记录每轮意见', kind: 'agent' },
    { title: '保存申请材料', subtitle: '记录审查结果与最终正文', kind: 'output' },
  ],
  rank: [
    { title: '汇集现有评估', subtitle: '读取各岗位评估和个人偏好', kind: 'run' },
    { title: '分析申请优先顺序', subtitle: '岗位排序 Agent', kind: 'agent' },
    { title: '保存排序报告', subtitle: '排序依据与建议动作', kind: 'output' },
  ],
  interview: [
    { title: '读取目标岗位与项目证据', subtitle: '岗位原文 · 个人档案 · 已有评估', kind: 'run' },
    { title: '生成面试准备', subtitle: '面试准备 Agent', kind: 'agent' },
    { title: '保存准备材料', subtitle: '项目讲解与岗位相关追问', kind: 'output' },
  ],
};

function layout(nodes: FlowNode[], edges: Edge[], vertical: boolean): FlowNode[] {
  return nodes.map(node => ({ ...node, data: { ...node.data, vertical } }));
}

function mermaidSource(nodes: FlowNode[], edges: Edge[]): string {
  const escape = (value: string) => value.replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('\n', ' ');
  const shorten = (value: string) => value.length > 24 ? `${value.slice(0, 24)}…` : value;
  const ids = new Map(nodes.map((node, index) => [node.id, `n${index}`]));
  const lines = [`flowchart ${nodes[0]?.data.vertical ? 'TB' : 'LR'}`];
  nodes.forEach(node => {
    const kind = { run: 'WORKFLOW', agent: 'AGENT', llm: 'MODEL CALL', tool: 'TOOL', output: 'DOCUMENT' }[node.data.kind] || 'WORKFLOW';
    const style = node.data.status === 'completed' ? 'done' : node.data.status === 'running' ? 'active' : node.data.status === 'failed' ? 'failed' : 'waiting';
    lines.push(`${ids.get(node.id)}["${kind}<br/>${escape(shorten(node.data.title))}<br/>${escape(shorten(node.data.subtitle))}<br/>${escape(statusNames[node.data.status] || node.data.status)}"]:::${style}`);
  });
  edges.forEach(edge => lines.push(`${ids.get(edge.source)} --> ${ids.get(edge.target)}`));
  lines.push('classDef done fill:#ffffff,stroke:#bdd7ca,stroke-width:1.5px,color:#647e6f');
  lines.push('classDef active fill:#faf7ff,stroke:#a891cf,stroke-width:2px,color:#77608f');
  lines.push('classDef failed fill:#fff5f5,stroke:#d2a0aa,stroke-width:1.5px,color:#a26e7d');
  lines.push('classDef waiting fill:#ffffff,stroke:#ddd6e8,stroke-width:1.3px,color:#88779a');
  return lines.join('\n');
}

export function buildGraph(action: Action, run: RunDetail | null, events: RunEvent[], historical: boolean, expanded = true) {
  const nodes: FlowNode[] = [];
  const edges: Edge[] = [];
  const add = (id: string, data: FlowData) => nodes.push({ id, type: 'process', position: { x: 0, y: 0 }, data });
  const connect = (source: string, target: string) => edges.push({
    id: `${source}-${target}`, source, target, type: 'smoothstep',
    animated: run?.status === 'running' && !historical,
    markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: '#bcc5d2', strokeWidth: 1.5 },
  });
  if (!run) {
    blueprints[action].forEach((step, i) => {
      add(`plan-${i}`, { ...step, status: 'planned', detail: { description: step.subtitle } });
      if (i) connect(`plan-${i - 1}`, `plan-${i}`);
    });
    return { nodes: layout(nodes, edges, true), edges };
  }
  const lastTerminal = events.filter(e => ['run.completed', 'run.failed', 'run.interrupted', 'run.review_required'].includes(e.type)).at(-1);
  const runState = historical ? lastTerminal ? lastTerminal.type.slice(4) : events.some(e => e.type === 'run.started') ? 'running' : 'queued' : run.status;
  add('root', { title: actionNames[run.action] || run.action, subtitle: run.source === 'legacy' ? '已保存的模型调用记录' : `${run.jobs.length || '全部'} 个岗位 · ${run.model || '模型未记录'}`, kind: 'run', status: runState, detail: { run_id: run.run_id, action: run.action, status: runState } });
  const started = events.filter(e => e.type === 'agent.started');
  const failed = ['failed', 'interrupted'].includes(runState);
  let previousAgent = 'root';
  for (const event of started) {
    const d = event.data;
    const finished = events.find(e => ['agent.finished', 'agent.failed'].includes(e.type) && e.data.execution_id === d.execution_id);
    const state = finished?.type === 'agent.failed' ? 'failed' : finished ? 'completed' : failed ? 'failed' : 'running';
    add(d.execution_id, { title: agentNames[d.agent] || d.agent, subtitle: d.task_id || '全局任务', status: state, kind: 'agent', detail: { ...d, output: finished?.data.output, error: finished?.data.error || (failed && !finished ? run.error : null), calls: events.filter(e => e.type === 'llm.finished' && e.data.execution_id === d.execution_id).map(e => e.data) } });
    connect(run.action === 'analyze' ? 'root' : previousAgent, d.execution_id);
    previousAgent = d.execution_id;
    if (!expanded) continue;
    let previousCall = d.execution_id;
    for (const call of events.filter(e => e.type === 'llm.started' && e.data.execution_id === d.execution_id)) {
      const end = events.find(e => ['llm.finished', 'llm.failed'].includes(e.type) && e.data.call_id === call.data.call_id);
      const data = end?.data || call.data;
      add(data.call_id, { title: data.model, subtitle: end ? `${((data.latency_ms || 0) / 1000).toFixed(1)} 秒 · ${(data.prompt_tokens || 0) + (data.completion_tokens || 0)} tokens` : '正在等待模型响应', kind: 'llm', status: data.error ? 'failed' : end ? 'completed' : failed ? 'failed' : 'running', detail: data });
      connect(previousCall, data.call_id);
      previousCall = data.call_id;
      for (const tool of events.filter(e => e.type === 'tool.started' && e.data.call_id === data.call_id)) {
        const toolEnd = events.find(e => ['tool.finished', 'tool.failed'].includes(e.type) && e.data.tool_id === tool.data.tool_id && e.data.call_id === data.call_id);
        const id = `tool-${data.call_id}-${tool.data.tool_id}`;
        const toolFailed = toolEnd?.type === 'tool.failed' || (!toolEnd && failed);
        add(id, { title: tool.data.name, subtitle: toolFailed ? '工具执行失败' : toolEnd ? `${toolEnd.data.latency_ms} 毫秒 · 执行完成` : '正在执行工具', kind: 'tool', status: toolFailed ? 'failed' : toolEnd ? 'completed' : 'running', detail: toolEnd?.data || { ...tool.data, error: failed ? run.error : null } });
        connect(previousCall, id);
        previousCall = id;
      }
    }
  }
  if (!started.length && run.source === 'legacy') {
    run.trace.calls.forEach((call, index) => {
      add(call.call_id, { title: agentNames[call.agent] || call.agent, subtitle: `${call.model} · ${(call.latency_ms / 1000).toFixed(1)} 秒`, kind: 'llm', status: call.error ? 'failed' : call.response ? 'completed' : 'recorded', detail: call });
      connect(index ? run.trace.calls[index - 1].call_id : 'root', call.call_id);
    });
  }
  return { nodes: layout(nodes, edges, !expanded || run.source === 'legacy'), edges };
}

function AutoFit({ width, height }: { width: number; height: number }) {
  const canvasWidth = useStore(state => state.width);
  const canvasHeight = useStore(state => state.height);
  const { fitBounds } = useReactFlow();
  useEffect(() => {
    if (width && height && canvasWidth && canvasHeight) void fitBounds({ x: 0, y: 0, width, height }, { padding: 0.2, duration: 250 });
  }, [width, height, canvasWidth, canvasHeight, fitBounds]);
  return null;
}

export default function Flow({ action, run, events, historical, onSelect }: {
  action: Action; run: RunDetail | null; events: RunEvent[]; historical: boolean; onSelect: (node: FlowNode) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const graph = useMemo(() => buildGraph(action, run, events, historical, expanded), [action, run, events, historical, expanded]);
  const source = useMemo(() => mermaidSource(graph.nodes, graph.edges), [graph]);
  const [diagram, setDiagram] = useState<{ svg: string; width: number; height: number; processes: FlowNode[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const processes = useRef(graph.nodes);
  processes.current = graph.nodes;
  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(() => {
      const snapshot = processes.current;
      mermaid.render(`jobsearch-diagram-${++diagramCounter}`, source).then(({ svg }) => {
        if (cancelled) return;
        const root = new DOMParser().parseFromString(svg, 'text/html').querySelector('svg');
        if (!root) throw new Error('Mermaid 没有返回 SVG 流程图。');
        const bounds = root.viewBox.baseVal;
        setDiagram({ svg, width: bounds.width, height: bounds.height, processes: snapshot });
        setError(null);
      }).catch(reason => { if (!cancelled) { setDiagram(null); setError(String(reason.message)); } });
    }, 80);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [source]);
  const nodes: DiagramNode[] = diagram ? [{ id: 'mermaid-canvas', type: 'mermaid', position: { x: 0, y: 0 },
    data: { svg: diagram.svg, processes: diagram.processes, select: onSelect },
    style: { width: diagram.width, height: diagram.height, pointerEvents: 'all' }, draggable: false, selectable: false }] : [];
  return <ReactFlow<DiagramNode> key={String(expanded)} nodes={nodes} edges={[]} nodeTypes={nodeTypes}
    fitView fitViewOptions={{ padding: 0.25, maxZoom: 1 }}
    minZoom={0.01} maxZoom={1.5} nodesConnectable={false} deleteKeyCode={null}
    ariaLabelConfig={{ 'controls.zoomIn.ariaLabel': '放大流程图', 'controls.zoomOut.ariaLabel': '缩小流程图', 'controls.fitView.ariaLabel': '适应全部节点', 'controls.interactive.ariaLabel': '切换交互模式' }}>
    <Background color="#d6dce6" gap={20} size={1} /><Controls showInteractive={false} />
    <AutoFit width={diagram?.width || 0} height={diagram?.height || 0} />
    {error && <div className="run-error">流程图绘制失败：{error}</div>}
    {run && run.source !== 'legacy' && <button className="graph-detail-toggle nodrag nopan" onClick={() => setExpanded(value => !value)}>{expanded ? '查看 Agent 流程' : '展开模型与工具'}</button>}
    {!run && <div className="canvas-note">流程说明 · 启动任务后显示实际执行过程</div>}
    {run?.source === 'legacy' && <div className="canvas-note">历史记录保留了模型输入与输出，未记录实时事件</div>}
    {run && !terminal(run.status) && <div className="live-pill"><span className="live-dot" />正在接收执行事件</div>}
  </ReactFlow>;
}
