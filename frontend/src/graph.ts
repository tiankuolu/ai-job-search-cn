import type { Edge, MarkerType, Node } from '@xyflow/react';
import { actionNames, agentNames, statusNames, type Action, type RunDetail, type RunEvent, type RunEventData } from './types';

export type NodeDetail = RunEventData & { calls?: RunEventData[]; description?: string; [key: string]: unknown };
export type FlowData = {
  title: string; subtitle: string; status: string; kind: string;
  detail: NodeDetail; [key: string]: unknown;
};
export type FlowNode = Node<FlowData, 'process'>;

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

export function buildGraph(action: Action, run: RunDetail | null, events: RunEvent[], historical: boolean, expanded = true) {
  const nodes: FlowNode[] = [];
  const edges: Edge[] = [];
  const add = (id: string, data: FlowData) => nodes.push({ id, type: 'process', position: { x: 0, y: 0 }, data });
  const connect = (source: string, target: string) => edges.push({
    id: `${source}-${target}`, source, target, type: 'smoothstep',
    animated: run?.status === 'running' && !historical,
    markerEnd: { type: 'arrowclosed' as MarkerType }, style: { stroke: '#bcc5d2', strokeWidth: 1.5 },
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
    add(d.execution_id || '', { title: agentNames[d.agent || ''] || d.agent || 'Agent', subtitle: d.task_id || '全局任务', status: state, kind: 'agent', detail: { ...d, output: finished?.data.output, error: finished?.data.error || (failed && !finished ? run.error : null), calls: events.filter(e => e.type === 'llm.finished' && e.data.execution_id === d.execution_id).map(e => e.data) } });
    connect(run.action === 'analyze' ? 'root' : previousAgent, d.execution_id || '');
    previousAgent = d.execution_id || '';
    if (!expanded) continue;
    let previousCall = d.execution_id || '';
    for (const call of events.filter(e => e.type === 'llm.started' && e.data.execution_id === d.execution_id)) {
      const end = events.find(e => ['llm.finished', 'llm.failed'].includes(e.type) && e.data.call_id === call.data.call_id);
      const data = end?.data || call.data;
      add(data.call_id || '', { title: data.model || '模型调用', subtitle: end ? `${((data.latency_ms || 0) / 1000).toFixed(1)} 秒 · ${(data.prompt_tokens || 0) + (data.completion_tokens || 0)} tokens` : '正在等待模型响应', kind: 'llm', status: data.error ? 'failed' : end ? 'completed' : failed ? 'failed' : 'running', detail: data });
      connect(previousCall, data.call_id || '');
      previousCall = data.call_id || '';
      for (const tool of events.filter(e => e.type === 'tool.started' && e.data.call_id === data.call_id)) {
        const toolEnd = events.find(e => ['tool.finished', 'tool.failed'].includes(e.type) && e.data.tool_id === tool.data.tool_id && e.data.call_id === data.call_id);
        const id = `tool-${data.call_id}-${tool.data.tool_id}`;
        const toolFailed = toolEnd?.type === 'tool.failed' || (!toolEnd && failed);
        add(id, { title: tool.data.name || '工具调用', subtitle: toolFailed ? '工具执行失败' : toolEnd ? `${toolEnd.data.latency_ms} 毫秒 · 执行完成` : '正在执行工具', kind: 'tool', status: toolFailed ? 'failed' : toolEnd ? 'completed' : 'running', detail: toolEnd?.data || { ...tool.data, error: failed ? run.error : null } });
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

export { blueprints, statusNames };
