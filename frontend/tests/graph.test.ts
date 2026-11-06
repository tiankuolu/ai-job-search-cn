import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { buildGraph } from '../src/graph';
import { dateTime, number, statusNames, terminal, type RunDetail } from '../src/types';

const fixture = JSON.parse(readFileSync(new URL('./fixtures/job-runs.json', import.meta.url), 'utf-8')) as {
  completed: { run: RunDetail; events: RunDetail['trace']['events'] };
  failed: { run: RunDetail; events: RunDetail['trace']['events'] };
  legacy: { run: { action: RunDetail['action']; calls: RunDetail['trace']['calls']; total_tokens?: number } };
};
const completed = fixture.completed.run;
const completedEvents = fixture.completed.events || [];
const failed = fixture.failed.run;
const failedEvents = fixture.failed.events || [];
const legacyRaw = fixture.legacy.run;
const legacy: RunDetail = {
  run_id: 'legacy-analyze', action: legacyRaw.action, status: 'recorded', source: 'legacy',
  created_at: '2026-10-22T03:43:19+00:00', ended_at: null, error: null, jobs: [],
  model: legacyRaw.calls[0]?.model || null, event_count: 0,
  trace: { calls: legacyRaw.calls, total_tokens: legacyRaw.calls.reduce((sum, call) => sum + call.prompt_tokens + call.completion_tokens, 0) },
  artifacts: [], result: null,
};

describe('buildGraph', () => {
  it('没有运行记录时按任务类型给出流程说明', () => {
    const analyze = buildGraph('analyze', null, [], false);
    expect(analyze.nodes.map(node => node.id)).toEqual(['plan-0', 'plan-1', 'plan-2']);
    expect(analyze.edges).toHaveLength(2);
    expect(analyze.nodes.every(node => node.data.status === 'planned')).toBe(true);
    expect(analyze.nodes[0].data.detail.description).toBe('岗位原文 · 个人档案 · 项目证据');
    expect(buildGraph('apply', null, [], false).nodes).toHaveLength(4);
  });

  it('用真实事件生成根节点、Agent、模型与工具节点', () => {
    const graph = buildGraph('analyze', completed, completedEvents, false);
    expect(graph.nodes).toHaveLength(14);
    expect(graph.edges).toHaveLength(13);
    expect(graph.nodes[0].data).toMatchObject({ title: '岗位分析', status: 'completed', kind: 'run' });
    expect(graph.nodes[1].data).toMatchObject({ title: '岗位分析 Agent', kind: 'agent', status: 'completed' });
    expect(graph.nodes.filter(node => node.data.kind === 'llm')).toHaveLength(4);
    expect(graph.nodes.filter(node => node.data.kind === 'tool')).toHaveLength(8);
    expect(graph.nodes[0].data.detail.run_id).toBe('analyze-20261028-175646-f3ebd3');
  });

  it('用真实耗时与 Token 生成节点副标题', () => {
    const graph = buildGraph('analyze', completed, completedEvents, false);
    const firstModel = graph.nodes.find(node => node.id === '822ece5a2279');
    expect(firstModel?.data.subtitle).toBe('2.0 秒 · 2716 tokens');
    const firstTool = graph.nodes.find(node => node.id === 'tool-822ece5a2279-call_00_cyytx74eb37c8urh7t34xhsl');
    expect(firstTool?.data.subtitle).toBe('0 毫秒 · 执行完成');
    expect(firstTool?.data.title).toBe('read_file');
    const lastModel = graph.nodes.find(node => node.id === 'c4fa9a6c6d6f');
    expect(lastModel?.data.subtitle).toBe('3.7 秒 · 14904 tokens');
  });

  it('折叠时只保留根节点与 Agent', () => {
    const graph = buildGraph('analyze', completed, completedEvents, false, false);
    expect(graph.nodes).toHaveLength(2);
    expect(graph.edges).toHaveLength(1);
    expect(graph.nodes.every(node => node.data.vertical === true)).toBe(true);
  });

  it('真实失败运行按事件推导失败状态与错误', () => {
    const graph = buildGraph('analyze', failed, failedEvents, false);
    expect(graph.nodes).toHaveLength(8);
    expect(graph.nodes[0].data.status).toBe('failed');
    expect(graph.nodes[1].data.status).toBe('failed');
    expect(graph.nodes[1].data.detail.error).toContain('risk_confirmation_required');
    expect(graph.nodes.filter(node => node.data.status === 'failed')).toHaveLength(3);
  });

  it('历史回放按终点事件推导状态', () => {
    const graph = buildGraph('analyze', completed, completedEvents, true);
    expect(graph.nodes[0].data.status).toBe('completed');
    const partial = buildGraph('analyze', completed, completedEvents.slice(0, 4), true);
    expect(partial.nodes[0].data.status).toBe('running');
  });

  it('历史记录只有模型调用时逐个生成节点', () => {
    const graph = buildGraph('analyze', legacy, [], false);
    expect(graph.nodes).toHaveLength(76);
    expect(graph.edges).toHaveLength(75);
    expect(graph.nodes[1].data.subtitle).toBe('deepseek-flash · 4.4 秒');
    expect(graph.nodes[1].data.kind).toBe('llm');
    expect(graph.nodes[1].data.vertical).toBe(true);
  });
});

describe('格式化函数', () => {
  it('覆盖运行状态名称', () => {
    expect(statusNames.queued).toBe('等待执行');
    expect(statusNames.review_required).toBe('需要审阅');
    expect(statusNames.interrupted).toBe('执行中断');
    expect(statusNames.recorded).toBe('历史记录');
  });

  it('只把排队与执行中视为未结束', () => {
    expect(terminal('queued')).toBe(false);
    expect(terminal('running')).toBe(false);
    expect(terminal('review_required')).toBe(true);
    expect(terminal('recorded')).toBe(true);
  });

  it('按上海时区格式化时间并分组数字', () => {
    expect(dateTime('2026-10-28T09:56:46.477554+00:00')).toBe('2026/10/28 17:56:46');
    expect(number(1234567)).toBe('1,234,567');
  });
});
