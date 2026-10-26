import { useEffect, useMemo, useRef, useState } from 'react';
import { Activity, ArrowDownToLine, ArrowLeft, ArrowRight, ArrowUpRight, Bot, BriefcaseBusiness, Check, ChevronRight, CircleAlert, Clock3, Cpu, FileText, FolderOpen, History, Layers3, LoaderCircle, Maximize2, Pause, Play, Radio, RefreshCw, Search, Settings2, Terminal, Workflow, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Flow, { buildGraph, type FlowNode } from './Flow';
import { actionNames, agentNames, api, dateTime, number, statusNames, terminal, type Action, type Call, type Document, type Job, type JobDetail, type Meta, type Run, type RunDetail, type RunEvent } from './types';

const actionDescriptions: Record<Action, string> = {
  analyze: '并行读取岗位与项目证据，生成有依据的匹配评估。',
  apply: '围绕目标岗位生成材料，逐轮展示审查意见与修改结果。',
  rank: '结合个人偏好与已保存的评估，整理岗位申请优先顺序。',
  interview: '围绕岗位职责和个人项目，准备讲解材料与面试追问。',
};
const eventNames: Record<string, string> = {
  'run.queued': '任务加入队列', 'run.started': '任务开始执行', 'run.completed': '任务执行完成',
  'run.failed': '任务执行失败', 'run.interrupted': '任务执行中断', 'run.review_required': '材料需要审阅',
  'agent.started': 'Agent 开始执行', 'agent.finished': 'Agent 执行完成',
  'agent.failed': 'Agent 执行失败', 'tool.failed': '工具执行失败',
  'llm.started': '请求模型', 'llm.finished': '收到模型响应', 'llm.failed': '模型调用失败',
  'tool.started': '调用工具', 'tool.finished': '工具执行完成',
  'review.started': '开始材料审查', 'review.finished': '材料审查完成', 'artifact.saved': '保存成果文件',
};
const documentNames: Record<string, string> = { evaluation: '岗位评估', application: '申请材料', research: '公司调研', interview: '面试准备' };

function Markdown({ children }: { children: string }) {
  return <div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{
    a: props => <a {...props} target="_blank" rel="noreferrer" />,
  }}>{children}</ReactMarkdown></div>;
}
function Empty({ title, text, icon: Icon = Workflow }: { title: string; text: string; icon?: typeof Workflow }) {
  return <div className="empty"><span><Icon size={27} strokeWidth={1.4} /></span><h3>{title}</h3><p>{text}</p></div>;
}
function download(document: Document) {
  const url = URL.createObjectURL(new Blob([document.content], { type: 'text/markdown;charset=utf-8' }));
  const anchor = window.document.createElement('a');
  anchor.href = url; anchor.download = document.name; anchor.click(); URL.revokeObjectURL(url);
}
function readable(value: unknown): string {
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2) || '';
}

function Inspector({ node, mode, setMode }: { node: FlowNode; mode: string; setMode: (value: string) => void }) {
  const data = node.data.detail;
  return <>
    <div className="inspector-heading"><span className={`kind-icon ${node.data.kind}`}><Cpu size={19} /></span><div><span className="eyebrow">NODE INSPECTOR</span><h3>{node.data.title}</h3></div></div>
    <div className="node-meta"><span className={`status ${node.data.status}`}>{statusNames[node.data.status] || node.data.status}</span><span>{node.data.kind === 'llm' ? '模型调用' : node.data.kind === 'tool' ? '工具调用' : '执行节点'}</span></div>
    {data.latency_ms !== undefined && <div className="detail-metrics"><span><Clock3 size={13} />{(data.latency_ms / 1000).toFixed(2)} 秒</span>{data.prompt_tokens !== undefined && <span>{number(data.prompt_tokens + data.completion_tokens)} tokens</span>}</div>}
    <div className="inspector-tabs">{['输出', '输入', '详情'].map(tab => <button key={tab} className={mode === tab ? 'active' : ''} onClick={() => setMode(tab)}>{tab}</button>)}</div>
    <div className="inspector-content">
      {mode === '输出' && (data.error ? <div className="error-inline">{data.error}</div> : data.response?.content || data.output !== undefined ? <Markdown>{readable(data.response?.content || data.output)}</Markdown> : data.response?.tool_calls?.length ? <><p className="muted">模型请求执行以下工具：</p><pre>{JSON.stringify(data.response.tool_calls, null, 2)}</pre></> : <p className="muted">{node.data.status === 'planned' ? node.data.subtitle : node.data.status === 'running' ? '等待该节点返回结果。' : '该节点没有文本输出。'}</p>)}
      {mode === '输入' && (data.messages ? data.messages.map((message: Call['messages'][number], i: number) => <details key={i} open={message.role === 'user'}><summary>{message.role}</summary><Markdown>{readable(message.content || message)}</Markdown></details>) : data.arguments ? <pre>{JSON.stringify(data.arguments, null, 2)}</pre> : <Markdown>{data.input || data.description || '该节点没有独立输入。'}</Markdown>)}
      {mode === '详情' && <pre>{JSON.stringify(Object.fromEntries(Object.entries(data).filter(([key]) => !['messages', 'output', 'input', 'response'].includes(key))), null, 2)}</pre>}
    </div>
  </>;
}

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [selectedJobs, setSelectedJobs] = useState<string[]>([]);
  const [job, setJob] = useState<JobDetail | null>(null);
  const [query, setQuery] = useState('');
  const [action, setAction] = useState<Action>('analyze');
  const [workers, setWorkers] = useState(4);
  const [page, setPage] = useState<'workspace' | 'history'>('workspace');
  const [tab, setTab] = useState('流程图');
  const [run, setRun] = useState<RunDetail | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [selectedNode, setSelectedNode] = useState<FlowNode | null>(null);
  const [inspectorMode, setInspectorMode] = useState('输出');
  const [panel, setPanel] = useState('node');
  const [documentIndex, setDocumentIndex] = useState(0);
  const [reading, setReading] = useState<Document | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [streamState, setStreamState] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [playback, setPlayback] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const selectionVersion = useRef(0);
  const jobVersion = useRef(0);
  const dialogRef = useRef<HTMLDivElement>(null);
  const runRef = useRef<RunDetail | null>(null);
  runRef.current = run;

  useEffect(() => {
    if (!reading) return;
    const previousFocus = document.activeElement as HTMLElement | null;
    const dialog = dialogRef.current;
    dialog?.focus();
    function keyboard(event: KeyboardEvent) {
      if (event.key === 'Escape') setReading(null);
      if (event.key === 'Tab' && dialog) {
        const controls = Array.from(dialog.querySelectorAll<HTMLElement>('button, a[href], select, input'));
        const first = controls[0], last = controls.at(-1);
        if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog)) { event.preventDefault(); last?.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    }
    document.addEventListener('keydown', keyboard);
    return () => { document.removeEventListener('keydown', keyboard); previousFocus?.focus(); };
  }, [reading]);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([api<Meta>('/meta', { signal: controller.signal }), api<Job[]>('/jobs', { signal: controller.signal }), api<Run[]>('/runs', { signal: controller.signal })])
      .then(([configuration, knownJobs, history]) => { setMeta(configuration); setJobs(knownJobs); setRuns(history); setLoading(false); })
      .catch(reason => { if (!controller.signal.aborted) { setError(String(reason.message)); setLoading(false); } });
    return () => controller.abort();
  }, []);

  async function refresh() {
    try {
      const [knownJobs, history, configuration] = await Promise.all([api<Job[]>('/jobs'), api<Run[]>('/runs'), api<Meta>('/meta')]);
      setJobs(knownJobs); setRuns(history); setMeta(configuration);
    } catch (reason) { setError((reason as Error).message); }
  }

  async function loadRun(id: string) {
    const version = ++selectionVersion.current;
    setPlaying(false); setPlayback(null); setSelectedNode(null); setError(null);
    try {
      const value = await api<RunDetail>(`/runs/${id}`);
      if (version !== selectionVersion.current) return;
      setRun(value); if (value.action in actionDescriptions) setAction(value.action); setEvents(value.trace.events || []);
      setPage('workspace'); setTab('流程图'); setPanel('node'); setDocumentIndex(0);
    } catch (reason) { if (version === selectionVersion.current) setError((reason as Error).message); }
  }

  const activeId = run && !terminal(run.status) ? run.run_id : null;
  useEffect(() => {
    if (!activeId) return;
    const last = runRef.current?.trace.events?.at(-1)?.seq || 0;
    const source = new EventSource(`/api/runs/${activeId}/events?after=${last}`);
    setStreamState('connecting');
    source.onopen = () => setStreamState('connected');
    source.onmessage = message => {
      const event: RunEvent = JSON.parse(message.data);
      setEvents(current => current.some(item => item.seq === event.seq) ? current : [...current, event].sort((a, b) => a.seq - b.seq));
    };
    source.onerror = () => setStreamState('reconnecting');
    source.addEventListener('end', () => {
      source.close(); setStreamState('');
      api<RunDetail>(`/runs/${activeId}`).then(value => {
        if (runRef.current?.run_id === activeId) { setRun(value); setEvents(value.trace.events || []); }
        return refresh();
      }).catch(reason => setError(reason.message));
    });
    return () => { source.close(); setStreamState(''); };
  }, [activeId]);

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => setPlayback(current => {
      if (current === null || current >= events.length) { setPlaying(false); return current; }
      return current + 1;
    }), 650);
    return () => window.clearInterval(timer);
  }, [playing, events.length]);

  async function inspectJob(id: string) {
    const version = ++jobVersion.current;
    try {
      const value = await api<JobDetail>(`/jobs/${id}`);
      if (version === jobVersion.current) { setJob(value); setPanel('job'); }
    } catch (reason) { setError((reason as Error).message); }
  }

  async function start() {
    setSubmitting(true); setError(null);
    try {
      const created = await api<Run>('/runs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action, job_ids: action === 'rank' ? [] : selectedJobs, max_workers: workers }) });
      await loadRun(created.run_id); await refresh();
    } catch (reason) { setError((reason as Error).message); }
    finally { setSubmitting(false); }
  }

  function newTask(next?: Action) {
    ++selectionVersion.current; setRun(null); setEvents([]); setSelectedNode(null); setPlayback(null);
    setPlaying(false); setPage('workspace'); setTab('流程图'); setPanel('node');
    if (next) setAction(next);
  }

  const filteredJobs = jobs.filter(item => item.title.toLowerCase().includes(query.toLowerCase()));
  const visibleEvents = useMemo(() => playback === null ? events : events.slice(0, playback), [events, playback]);
  const graph = useMemo(() => buildGraph(action, run, visibleEvents, playback !== null), [action, run, visibleEvents, playback]);
  const inspected = selectedNode ? graph.nodes.find(node => node.id === selectedNode.id) || null : null;
  const liveCalls = visibleEvents.filter(event => ['llm.finished', 'llm.failed'].includes(event.type));
  const callCount = run?.source === 'legacy' ? run.trace.calls.length : visibleEvents.filter(event => event.type === 'llm.started').length;
  const tokens = run?.source === 'legacy' ? run.trace.total_tokens : liveCalls.reduce((sum, event) => sum + (event.data.prompt_tokens || 0) + (event.data.completion_tokens || 0), 0);
  const latency = run?.source === 'legacy' ? run.trace.calls.reduce((sum, call) => sum + call.latency_ms, 0) : liveCalls.reduce((sum, event) => sum + (event.data.latency_ms || 0), 0);
  const toolCount = run?.source === 'legacy' ? run.trace.calls.reduce((sum, call) => sum + call.tool_calls.length, 0) : visibleEvents.filter(event => event.type === 'tool.started').length;
  const busyRun = runs.find(item => !terminal(item.status));
  const wrongSelection = action === 'analyze' ? !selectedJobs.length : action === 'rank' ? !jobs.some(item => item.documents.includes('evaluation')) : selectedJobs.length !== 1;
  const canStart = meta?.configured && !submitting && !busyRun && !wrongSelection;
  const artifacts = run?.artifacts || [];
  const currentDocument = artifacts[documentIndex] || artifacts[0];

  return <div className="app-shell">
    <aside className="navigation">
      <a className="brand" href="/" aria-label="求职 Agent 工作台"><span><Layers3 size={22} /></span><div>求职 Agent<small>JOBSEARCH STUDIO</small></div></a>
      <div className="nav-caption">工作空间</div>
      <button className={`nav-item ${page === 'workspace' ? 'active' : ''}`} onClick={() => setPage('workspace')}><Workflow size={18} />交互工作台<ChevronRight size={14} /></button>
      <button className={`nav-item ${page === 'history' ? 'active' : ''}`} onClick={() => { setPage('history'); void refresh(); }}><History size={18} />运行记录<span className="nav-count">{runs.length}</span></button>
      <div className="nav-separator" />
      <div className="nav-caption">任务能力</div>
      {(Object.keys(actionNames) as Action[]).map(key => <button className={`nav-task ${action === key && page === 'workspace' ? 'chosen' : ''}`} key={key} onClick={() => newTask(key)}><span className={`task-dot ${key}`} />{actionNames[key]}<ArrowUpRight size={13} /></button>)}
      <div className="nav-bottom"><div className="system-state"><span className={`live-dot ${meta?.configured ? '' : 'offline'}`} />{meta?.configured ? '模型配置就绪' : '等待模型配置'}</div><strong>{meta?.model || '未设置模型'}</strong><p>本机运行 · 真实任务记录</p></div>
    </aside>

    <div className="main-shell">
      <header className="topbar"><div className="breadcrumb">工作空间<ChevronRight size={13} /><strong>{page === 'history' ? '运行记录' : '交互工作台'}</strong></div><div className="topbar-right"><span className="local-tag"><span />LOCAL WORKSPACE</span><button className="icon-button" aria-label="刷新工作区" onClick={() => void refresh()}><RefreshCw size={16} /></button><span className="avatar">LT</span></div></header>
      <main>
        <section className="page-heading"><div><div className="eyebrow">{page === 'history' ? 'RUN HISTORY' : 'AGENT WORKBENCH'}</div><h1>{page === 'history' ? '每一次运行，都有迹可循。' : '让求职过程，清晰可见。'}</h1><p>{page === 'history' ? '查看真实调用记录，回放执行过程，阅读生成成果。' : '选择岗位、启动任务，查看 Agent 如何使用资料完成分析与写作。'}</p></div><button className="secondary-button" onClick={() => newTask()}><Workflow size={15} />新建任务<ArrowUpRight size={15} /></button></section>

        {error && <div className="alert error" role="alert"><CircleAlert size={17} /><span>{error}</span><button aria-label="关闭错误提示" onClick={() => setError(null)}><X size={16} /></button></div>}
        {meta && !meta.configured && <div className="alert config"><Settings2 size={17} /><span>模型配置缺失：{meta.missing.join('、')}。配置环境变量后重新启动服务。</span></div>}

        {page === 'history' ? <section className="history-panel"><div className="section-heading"><h2>运行记录 <span>{runs.length}</span></h2><button className="text-button" onClick={() => void refresh()}><RefreshCw size={14} />刷新记录</button></div>{loading ? <div className="loading"><LoaderCircle className="spin" />正在读取运行记录</div> : runs.length ? <div className="history-list">{runs.map(item => <button className="history-row" key={item.run_id} onClick={() => void loadRun(item.run_id)}><span className={`history-icon ${item.action}`}><Workflow size={20} /></span><div><strong>{actionNames[item.action] || item.action}</strong><p>{item.jobs.map(j => j.key).join('、') || item.run_id}</p></div><div className="history-time">{dateTime(item.created_at)}<small>{item.model || '模型未记录'}</small></div><span className={`status ${item.status}`}>{statusNames[item.status]}</span><ArrowRight size={17} /></button>)}</div> : <Empty title="尚无运行记录" text="启动任务后，可以在这里查看执行过程和成果。" icon={History} />}</section> : <>
          <section className="metrics-row">
            {[{ label: '模型调用', value: number(callCount), unit: '次', Icon: Cpu, color: 'violet' }, { label: '工具执行', value: number(toolCount), unit: '次', Icon: Terminal, color: 'blue' }, { label: 'Token 用量', value: number(tokens), unit: 'tokens', Icon: Activity, color: 'orange' }, { label: '模型累计耗时', value: (latency / 1000).toFixed(1), unit: '秒', Icon: Clock3, color: 'green' }].map(metric => <div className="metric-card" key={metric.label}><span className={`metric-icon ${metric.color}`}><metric.Icon size={19} /></span><div><span>{metric.label}</span><strong>{metric.value}<small>{metric.unit}</small></strong></div></div>)}
          </section>

          <section className="task-bar"><div className="task-actions">{(Object.keys(actionNames) as Action[]).map(key => <button key={key} className={action === key ? 'active' : ''} onClick={() => newTask(key)}>{actionNames[key]}</button>)}</div><div className="task-options">{action === 'analyze' && <label className="worker-control">并行数量<select aria-label="并行数量" value={workers} onChange={event => setWorkers(Number(event.target.value))}>{[1, 2, 3, 4, 6, 8].map(n => <option key={n}>{n}</option>)}</select></label>}<button className="primary-button" disabled={!canStart} onClick={() => void start()}>{submitting ? <LoaderCircle size={15} className="spin" /> : <Play size={14} fill="currentColor" />}启动{actionNames[action]}</button></div></section>
          <div className="task-description"><span>{actionDescriptions[action]}</span><span>{action === 'rank' ? '使用全部已保存的岗位评估' : `已选择 ${selectedJobs.length} 个岗位${action === 'apply' || action === 'interview' ? ' · 每次选择一个岗位' : ''}`}</span></div>
          {busyRun && <div className="busy-banner"><Radio size={15} />已有{actionNames[busyRun.action]}任务正在执行<button onClick={() => void loadRun(busyRun.run_id)}>查看执行过程<ArrowRight size={14} /></button></div>}

          <div className="workbench">
            <section className="jobs-panel"><div className="panel-heading"><h2><BriefcaseBusiness size={16} />岗位列表</h2><span className="count-badge">{jobs.length}</span></div><div className="search-field"><Search size={15} /><input placeholder="搜索公司或岗位" aria-label="搜索公司或岗位" value={query} onChange={event => setQuery(event.target.value)} /></div><div className="selection-controls"><button onClick={() => setSelectedJobs(current => Array.from(new Set([...current, ...filteredJobs.map(item => item.id)])))}>选择搜索结果</button><button onClick={() => setSelectedJobs([])}>清除选择</button></div><div className="job-list">{loading ? <div className="loading"><LoaderCircle size={18} className="spin" />正在读取岗位</div> : filteredJobs.length ? filteredJobs.map(item => <div className={`job-card ${selectedJobs.includes(item.id) ? 'selected' : ''}`} key={item.id}><div className="job-card-main"><input type="checkbox" aria-label={`选择 ${item.title}`} checked={selectedJobs.includes(item.id)} onChange={event => setSelectedJobs(current => event.target.checked ? [...current, item.id] : current.filter(id => id !== item.id))} /><button onClick={() => void inspectJob(item.id)}><strong>{item.title}</strong><span>{item.documents.length ? item.documents.map(kind => documentNames[kind]).join(' · ') : '等待分析'}</span></button></div><button className="job-view" onClick={() => void inspectJob(item.id)}>查看岗位与材料<ArrowUpRight size={12} /></button></div>) : <Empty title="没有匹配岗位" text="请调整搜索关键词或检查岗位资料目录。" icon={Search} />}</div><div className="jobs-footer"><FolderOpen size={13} />从本地求职资料读取</div></section>

            <section className="canvas-panel"><div className="canvas-header"><div className="content-tabs">{['流程图', '事件记录', '生成成果'].map(value => <button className={tab === value ? 'active' : ''} key={value} onClick={() => setTab(value)}>{value === '流程图' ? <Workflow size={15} /> : value === '事件记录' ? <Terminal size={15} /> : <FileText size={15} />}{value}{value === '生成成果' && artifacts.length > 0 && <span>{artifacts.length}</span>}</button>)}</div>{run ? <span className={`status ${run.status}`}>{statusNames[run.status]}</span> : <span className="preview-label">流程说明</span>}</div>
              {run && <div className="run-caption"><span title={run.run_id}>{run.run_id}</span><span>{streamState === 'reconnecting' ? '连接中断，正在重新连接' : streamState === 'connected' ? '实时连接' : dateTime(run.created_at)}</span></div>}
              {run?.error && <div className="run-error"><CircleAlert size={15} />{run.error}</div>}
              {run?.status === 'review_required' && <div className="review-warning">材料已生成，审查仍有未通过项目。请查看审查意见和最终正文。</div>}
              <div className="canvas-body">
                {tab === '流程图' && <Flow key={run?.run_id || action} action={action} run={run} events={visibleEvents} historical={playback !== null} onSelect={node => { setSelectedNode(node); setPanel('node'); setInspectorMode('输出'); }} />}
                {tab === '事件记录' && (visibleEvents.length ? <div className="event-list">{visibleEvents.map(event => <div className={`event-item ${event.type.includes('failed') ? 'event-error' : ''}`} key={event.seq}><span className="event-seq">{String(event.seq).padStart(2, '0')}</span><div><strong>{eventNames[event.type] || event.type}</strong><p>{event.data.name || agentNames[event.data.agent] || event.data.agent || event.data.error || (event.data.round ? `第 ${event.data.round} 轮${event.type === 'review.finished' ? event.data.pass ? ' · 审查通过' : ' · 审查未通过' : ''}` : event.data.action ? actionNames[event.data.action as Action] : '')}</p>{event.type === 'review.finished' && <Markdown>{readable(event.data.violations)}</Markdown>}</div><time>{new Date(event.timestamp).toLocaleTimeString('zh-CN', { hour12: false, timeZone: 'Asia/Shanghai' })}</time></div>)}</div> : <Empty title="等待执行事件" text={run?.source === 'legacy' ? '这条历史记录保留了模型调用，可在流程图中查看输入和输出。' : '启动任务后，这里会按实际发生顺序记录每个执行步骤。'} icon={Terminal} />)}
                {tab === '生成成果' && (currentDocument ? <div className="artifact-view"><div className="artifact-toolbar"><select aria-label="选择成果文件" value={documentIndex} onChange={event => setDocumentIndex(Number(event.target.value))}>{artifacts.map((document, index) => <option key={document.name} value={index}>{document.name}</option>)}</select><button className="icon-button" aria-label="展开成果文件" onClick={() => setReading(currentDocument)}><Maximize2 size={15} /></button><button className="icon-button" aria-label="下载成果文件" onClick={() => download(currentDocument)}><ArrowDownToLine size={16} /></button></div><Markdown>{currentDocument.content}</Markdown></div> : <Empty title="成果会保存在这里" text="任务结束后查看该次运行保存的评估或申请材料。" icon={FileText} />)}
              </div>
              <div className="canvas-footer"><span><span className="legend-dot completed" />已完成</span><span><span className="legend-dot running" />执行中</span><span><span className="legend-dot failed" />失败</span><span className="canvas-hint">拖动浏览 · 滚轮缩放 · 点击节点查看详情</span></div>
              {run && terminal(run.status) && events.length > 0 && <div className="playback"><button className="icon-button" aria-label={playing ? '暂停回放' : '播放运行记录'} onClick={() => { if (!playing && (playback === null || playback >= events.length)) setPlayback(0); setPlaying(value => !value); }}>{playing ? <Pause size={16} /> : <Play size={16} />}</button><span>运行回放</span><input type="range" min={0} max={events.length} aria-label="运行回放进度" value={playback ?? events.length} onChange={event => { setPlaying(false); setPlayback(Number(event.target.value)); }} /><small>{playback ?? events.length} / {events.length}</small><button className="text-button" onClick={() => { setPlayback(null); setPlaying(false); }}>全部事件</button></div>}
            </section>

            <aside className="inspector-panel"><div className="panel-heading"><h2>{panel === 'job' ? <><FileText size={16} />岗位资料</> : <><Layers3 size={16} />节点详情</>}</h2>{panel === 'job' && <button className="icon-button" aria-label="返回节点详情" onClick={() => setPanel('node')}><ArrowLeft size={15} /></button>}</div>{panel === 'job' && job ? <div className="job-detail"><h3>{job.key}</h3><button className="document-link" onClick={() => setReading({ name: `${job.key}-岗位JD.md`, content: job.content })}><FileText size={17} /><span>阅读完整岗位原文</span><Maximize2 size={14} /></button><div className="detail-caption">已有材料</div>{job.documents.length ? job.documents.map(document => <button key={document.kind} className="document-link" onClick={() => setReading(document)}><FileText size={17} /><span>{document.label}</span><ArrowUpRight size={14} /></button>) : <p className="muted">该岗位暂未生成相关材料。</p>}<div className="detail-caption">岗位原文</div><Markdown>{job.content}</Markdown></div> : inspected ? <Inspector node={inspected} mode={inspectorMode} setMode={setInspectorMode} /> : <><Empty title="探索执行细节" text="点击流程中的节点，查看使用的资料、模型响应和工具执行结果。" icon={Bot} /><div className="inspector-tip"><span className="eyebrow">HOW IT WORKS</span><p>左侧选择目标岗位，启动任务后，流程会随真实执行更新。</p><p>运行记录保留模型输入、输出和工具结果，便于解释每一步的依据。</p></div></>}</aside>
          </div>
          <footer className="page-footer"><span><Check size={13} />读取本地资料 · 成果保存至求职材料目录</span><span>React + Python · Agent 可观测工作台</span></footer>
        </>}
      </main>
    </div>
    {reading && <div className="document-overlay" role="dialog" aria-modal="true" aria-label={reading.name} onClick={event => { if (event.target === event.currentTarget) setReading(null); }}><div className="document-modal" ref={dialogRef} tabIndex={-1}><header><div><FileText size={19} /><strong>{reading.name}</strong></div><div><button className="icon-button" aria-label="下载文档" onClick={() => download(reading)}><ArrowDownToLine size={18} /></button><button className="icon-button" aria-label="关闭文档" onClick={() => setReading(null)}><X size={20} /></button></div></header><div className="document-scroll"><Markdown>{reading.content}</Markdown></div></div></div>}
  </div>;
}
