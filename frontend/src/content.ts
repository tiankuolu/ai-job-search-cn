import type { Action } from './types';

export const actionDescriptions: Record<Action, string> = {
  analyze: '并行读取岗位与项目证据，生成有依据的匹配评估。',
  apply: '围绕目标岗位生成材料，逐轮展示审查意见与修改结果。',
  rank: '结合个人偏好与已保存的评估，整理岗位申请优先顺序。',
  interview: '围绕岗位职责和个人项目，准备讲解材料与面试追问。',
};

export const eventNames: Record<string, string> = {
  'run.queued': '任务加入队列', 'run.started': '任务开始执行', 'run.completed': '任务执行完成',
  'run.failed': '任务执行失败', 'run.interrupted': '任务执行中断', 'run.review_required': '材料需要审阅',
  'agent.started': 'Agent 开始执行', 'agent.finished': 'Agent 执行完成',
  'agent.failed': 'Agent 执行失败', 'tool.failed': '工具执行失败',
  'llm.started': '请求模型', 'llm.finished': '收到模型响应', 'llm.failed': '模型调用失败',
  'tool.started': '调用工具', 'tool.finished': '工具执行完成',
  'review.started': '开始材料审查', 'review.finished': '材料审查完成', 'artifact.saved': '保存成果文件',
};

export const documentNames: Record<string, string> = { evaluation: '岗位评估', application: '申请材料', research: '公司调研', interview: '面试准备' };

export function readable(value: unknown): string {
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2) || '';
}
