export type Action = 'analyze' | 'apply' | 'rank' | 'interview';
export type Job = { id: string; key: string; title: string; documents: string[] };
export type Document = { name: string; content: string; kind?: string; label?: string };
export type JobDetail = { id: string; key: string; content: string; documents: Document[] };
export type Meta = { configured: boolean; model: string | null; missing: string[]; workspace: string };
export type Run = {
  run_id: string; action: Action; status: string; source: string; created_at: string;
  ended_at: string | null; error: string | null; jobs: { id: string; key: string }[];
  model: string | null; event_count: number;
};
export type Call = {
  call_id: string; agent: string; model: string; messages: { role: string; content?: string; [key: string]: unknown }[];
  response: { content: string | null; tool_calls?: unknown[] } | null;
  tool_calls: { name: string; arguments: unknown }[];
  prompt_tokens: number; completion_tokens: number; latency_ms: number; error: string | null;
  execution_id?: string; task_id?: string;
};
export type RunEvent = {
  seq: number; type: string; timestamp: string; run_id: string;
  data: Record<string, any>;
};
export type RunDetail = Run & {
  trace: { calls: Call[]; events?: RunEvent[]; total_tokens: number };
  artifacts: Document[]; result: Record<string, any> | null;
};
export const actionNames: Record<Action, string> = {
  analyze: '岗位分析', apply: '申请材料', rank: '岗位排序', interview: '面试准备',
};
export const agentNames: Record<string, string> = {
  analyzer: '岗位分析 Agent', writer: '材料写作 Agent', reviewer: '材料审查 Agent',
  ranker: '岗位排序 Agent', interviewer: '面试准备 Agent', researcher: '公司调研 Agent',
};
export const statusNames: Record<string, string> = {
  queued: '等待执行', running: '正在执行', completed: '执行完成', failed: '执行失败',
  review_required: '需要审阅', interrupted: '执行中断', recorded: '历史记录', planned: '流程说明',
};
export const terminal = (status: string) => !['queued', 'running'].includes(status);
export const dateTime = (value: string) => new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });
export const number = (value: number) => value.toLocaleString('zh-CN');

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init);
  if (!response.ok) {
    if (!response.headers.get('content-type')?.includes('application/json')) {
      throw new Error(`服务请求失败（HTTP ${response.status}），请查看服务终端的错误信息。`);
    }
    const value = await response.json();
    throw new Error(typeof value.detail === 'string' ? value.detail : JSON.stringify(value.detail));
  }
  return response.json();
}
