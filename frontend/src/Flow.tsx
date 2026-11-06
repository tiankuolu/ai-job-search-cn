import { useEffect, useMemo, useRef, useState, memo } from 'react';
import { Background, Controls, ReactFlow, useStore, useReactFlow, type Node, type Edge, type NodeProps } from '@xyflow/react';
import mermaid from 'mermaid';
import { buildGraph, type FlowNode } from './graph';
import { statusNames, terminal, type Action, type RunDetail, type RunEvent } from './types';

mermaid.initialize({
  startOnLoad: false, securityLevel: 'strict', theme: 'base',
  fontFamily: 'Microsoft YaHei, sans-serif',
  themeVariables: { primaryColor: '#ffffff', primaryTextColor: '#665778', primaryBorderColor: '#d8cfe7', lineColor: '#b6a9c8', fontSize: '12px' },
  flowchart: { htmlLabels: false, useMaxWidth: false, curve: 'basis', rankSpacing: 35, nodeSpacing: 30, padding: 17 },
});
let diagramCounter = 0;

export type { FlowNode };
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

function AutoFit({ width, height }: { width: number; height: number }) {
  const canvasWidth = useStore(state => state.width);
  const canvasHeight = useStore(state => state.height);
  const { fitBounds } = useReactFlow();
  const last = useRef('');
  useEffect(() => {
    if (!width || !height || !canvasWidth || !canvasHeight) return;
    const key = `${width}x${height}`;
    if (last.current === key) return;
    last.current = key;
    void fitBounds({ x: 0, y: 0, width, height }, { padding: 0.2, duration: 0 });
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
