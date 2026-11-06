import { useEffect, useRef, useState } from 'react';
import { ArrowDownToLine, ArrowLeft, ArrowRight, BriefcaseBusiness, Check, CheckCheck, ChevronRight, CircleAlert, ExternalLink, FileText, LoaderCircle, MapPin, Search, Settings2, Sparkles, X } from 'lucide-react';
import { api, dateTime } from '../types';
import '../styles/delivery.css';
import AddJobDialog from './AddJobDialog';
import ResumeEditor, { type ResumeEditorHandle } from './ResumeEditor';
import WebsiteProjectsCard, { type WebsiteProjectText } from './WebsiteProjectsCard';
import SupplementCards from './SupplementCards';

type Platform = 'boss' | 'liepin' | 'nowcoder' | 'shixiseng';
const platformNames: Record<Platform, string> = { boss: 'BOSS直聘', liepin: '猎聘', nowcoder: '牛客', shixiseng: '实习僧' };
type Job = { id: string; platform?: Platform | 'manual'; origin?: string; title: string; company: string; url: string; city: string; description: string; match: { eligible: boolean; status?: string; reason: string; evidence: string } };
type Package = { id: string; job_id: string; platform?: Platform; company: string; title: string; status: string; greeting: string; created_at: string; sent_at?: string; attempted_at?: string; html?: string; resume_dirty?: boolean; editor_revision?: number; exported_revision?: number; website_projects?: WebsiteProjectText[]; website_projects_revision?: number };
type Task = { id: string; action: string; status: string; progress: string; error: string | null; created_at: string; job_ids?: string[]; package_ids?: string[]; current_job_id?: string; platform?: Platform };
type Snapshot = { configured: boolean; jobs: Job[]; packages: Package[]; tasks: Task[] };
const steps = ['岗位分析', '编写简历', '确认材料', '提交申请', '查看结果'];
const activeTask = (task: Task) => ['running', 'queued'].includes(task.status);
const packageUrl = (pack: Package, kind: string) => `/api/delivery/packages/${pack.id}/${kind}`;
const sourceName = (job: Job) => job.platform === 'manual' ? '手动导入' : platformNames[job.platform || 'boss'];
const jobState = (job: Job, pack?: Package) => job.match.status === 'pending' ? '待分析' : stateLabel(pack);

function stateLabel(pack?: Package) {
  if (!pack) return '待准备材料';
  return ({ ready: '待确认', sent: '已投递', needs_verification: '待核实', sending: '正在投递' } as Record<string, string>)[pack.status] || '待确认';
}

export default function DeliveryPage() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [selectedId, setSelectedId] = useState(() => localStorage.getItem('job-workspace-selected') || '');
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('全部岗位');
  const [companyFilter, setCompanyFilter] = useState('all');
  const [step, setStep] = useState(0);
  const [modal, setModal] = useState<'search' | 'settings' | 'jd' | 'revision' | 'regenerate' | null>(null);
  const [versionId, setVersionId] = useState('');
  const [addingJob, setAddingJob] = useState(false);
  const [deletingJob, setDeletingJob] = useState(false);
  const [platform, setPlatform] = useState<Platform>('boss');
  const [keywords, setKeywords] = useState('Agent 应用开发,科研 Agent,Python 后端');
  const [limit, setLimit] = useState(10);
  const [prepare, setPrepare] = useState(false);
  const [includeWebsiteProjects, setIncludeWebsiteProjects] = useState(false);
  const [includeEnglishResume, setIncludeEnglishResume] = useState(false);
  const [includeSelfDescription, setIncludeSelfDescription] = useState(false);
  const [connection, setConnection] = useState<Partial<Record<Platform, { loggedIn: boolean; canSubmit: boolean; message: string }>>>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [greeting, setGreeting] = useState('');
  const [revision, setRevision] = useState('');
  const [notice, setNotice] = useState('');
  const pollVersion = useRef(0);
  const selectedButton = useRef<HTMLButtonElement>(null);
  const resumeEditor = useRef<ResumeEditorHandle>(null);
  const [editorReady, setEditorReady] = useState(false);
  const [editorUnsaved, setEditorUnsaved] = useState(false);
  const [exportRequest, setExportRequest] = useState<{ taskId: string; packageId: string; continueAfter: boolean; downloadPng: boolean } | null>(null);

  async function refresh() {
    const version = ++pollVersion.current;
    const next = await api<Snapshot>('/delivery');
    if (version === pollVersion.current) setSnapshot(next);
    return next;
  }

  useEffect(() => {
    let mounted = true;
    async function poll() {
      try {
        const version = ++pollVersion.current;
        const next = await api<Snapshot>('/delivery');
        if (mounted && version === pollVersion.current) setSnapshot(next);
      } catch (reason) { if (mounted) setError((reason as Error).message); }
    }
    void poll();
    const timer = window.setInterval(() => void poll(), 3000);
    return () => { mounted = false; window.clearInterval(timer); };
  }, []);

  const jobs = snapshot?.jobs || [];
  const job = jobs.find(item => item.id === selectedId) || jobs[0];
  const packages = snapshot?.packages || [];
  const packageFor = (id: string) => packages.find(pack => pack.job_id === id);
  const pack = job ? packages.find(item => item.id === versionId && item.job_id === job.id) || packageFor(job.id) : undefined;
  const versions = job ? packages.filter(item => item.job_id === job.id) : [];
  const activeTasks = snapshot?.tasks.filter(activeTask) || [];
  const active = activeTasks[0];
  const relevant = (task: Task, id: string) => task.current_job_id === id || task.job_ids?.includes(id) || task.package_ids?.some(key => packages.some(item => item.id === key && item.job_id === id)) || false;
  const isJobWorking = (id: string) => activeTasks.some(task => relevant(task, id));
  const jobActive = job ? activeTasks.find(task => relevant(task, job.id)) : undefined;
  const jobTask = job && snapshot?.tasks.find(task => relevant(task, job.id));
  const failure = jobTask && ['failed', 'interrupted'].includes(jobTask.status) ? jobTask : undefined;
  const latestTask = snapshot?.tasks[0];
  const disabled = !!jobActive || submitting || !snapshot?.configured;
  const browserBusy = activeTasks.some(task => ['search', 'deliver', 'login', 'verify'].includes(task.action));
  const browserDisabled = browserBusy || submitting || !snapshot?.configured;
  const jobPlatform: Platform = job?.platform && job.platform !== 'manual' ? job.platform : 'boss';
  const canDeliver = !!job?.url && job.platform !== 'manual';
  const needsAnalysis = job?.match.status === 'pending';
  const jobConnection = connection[jobPlatform];
  const reached = pack?.status === 'sent' || pack?.status === 'needs_verification' ? 4 : pack ? 3 : jobActive && jobActive.action !== 'analyze' ? 1 : 0;
  const companies = [...new Set(jobs.map(item => item.company.trim()))].sort((left, right) => left.localeCompare(right, 'zh-CN'));
  const filtered = jobs.filter(item => (companyFilter === 'all' || `company:${item.company.trim()}` === companyFilter) && `${item.title} ${item.company}`.toLowerCase().includes(query.toLowerCase()) && (filter === '全部岗位' || (filter === '正在处理' ? isJobWorking(item.id) : jobState(item, packageFor(item.id)) === filter)));
  const sentCount = jobs.filter(item => packages.some(value => value.job_id === item.id && value.status === 'sent')).length;

  useEffect(() => {
    if (snapshot && companyFilter !== 'all' && !snapshot.jobs.some(item => `company:${item.company.trim()}` === companyFilter)) setCompanyFilter('all');
  }, [snapshot, companyFilter]);

  useEffect(() => {
    if (!job) return;
    setSelectedId(job.id);
    setVersionId('');
    setPlatform(job.platform && job.platform !== 'manual' ? job.platform : 'boss');
    localStorage.setItem('job-workspace-selected', job.id);
    const saved = localStorage.getItem(`job-workspace-step-${job.id}`);
    setStep(saved === null ? (pack ? (pack.status === 'ready' ? 2 : 4) : 0) : Math.min(Number(saved), reached));
    setNotice(''); setError(null);
    selectedButton.current?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }, [job?.id]);

  useEffect(() => { setGreeting(pack?.greeting || ''); }, [pack?.id, pack?.greeting]);
  useEffect(() => {
    if (modal === 'search' || modal === 'settings') void checkConnection(platform);
  }, [modal, platform]);
  useEffect(() => { setEditorReady(false); setEditorUnsaved(false); }, [pack?.id]);
  useEffect(() => {
    if (!exportRequest) return;
    const task = snapshot?.tasks.find(item => item.id === exportRequest.taskId);
    if (!task || activeTask(task)) return;
    if (task.status === 'completed' && exportRequest.continueAfter && pack?.id === exportRequest.packageId) selectStep(3);
    if (task.status === 'completed' && exportRequest.downloadPng) {
      const link = document.createElement('a');
      link.href = `/api/delivery/packages/${exportRequest.packageId}/image`;
      link.download = '';
      document.body.appendChild(link);
      link.click();
      link.remove();
    }
    setExportRequest(null);
  }, [snapshot, exportRequest]);
  const previousPackage = useRef(pack?.id);
  const previousJob = useRef(job?.id);
  useEffect(() => {
    if (pack && previousJob.current === job?.id && previousPackage.current !== pack.id && !versionId) selectStep(pack.status === 'ready' ? 2 : 4);
    previousJob.current = job?.id;
    previousPackage.current = pack?.id;
  }, [job?.id, pack?.id, versionId]);
  const previousStatus = useRef({ job: job?.id, status: pack?.status });
  useEffect(() => {
    if (!versionId && previousStatus.current.job === job?.id && previousStatus.current.status !== pack?.status && (pack?.status === 'sent' || pack?.status === 'needs_verification')) selectStep(4);
    previousStatus.current = { job: job?.id, status: pack?.status };
  }, [job?.id, pack?.status]);

  function selectStep(value: number) {
    setStep(value);
    if (job) localStorage.setItem(`job-workspace-step-${job.id}`, String(value));
  }

  async function submit(action: string, body: unknown = {}) {
    setSubmitting(true); setError(null); setNotice('');
    try {
      if (action === 'prepare' && editorUnsaved && resumeEditor.current) await resumeEditor.current.flush();
      if (action === 'prepare' && pack?.status === 'ready' && greeting !== pack.greeting && greeting.trim()) {
        if (!await saveGreeting()) return false;
        setSubmitting(true);
      }
      const payload = action === 'prepare' || action === 'search' ? { ...(body as Record<string, unknown>), include_website_projects: includeWebsiteProjects, include_english_resume: includeEnglishResume, include_self_description: includeSelfDescription } : body;
      await api(`/delivery/${action}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      if (action === 'prepare') setVersionId('');
      await refresh();
      if (action.startsWith('login')) await checkConnection(platform);
      else setModal(null);
      if (action === 'prepare') selectStep(1);
      return true;
    } catch (reason) { setError((reason as Error).message); return false; }
    finally { setSubmitting(false); }
  }

  async function checkConnection(target: Platform) {
    setSubmitting(true); setError(null);
    try {
      const result = await api<{ logged_in: boolean; initialized: boolean; can_submit?: boolean }>(`/delivery/connection?platform=${target}`);
      setConnection(current => ({ ...current, [target]: { loggedIn: result.logged_in, canSubmit: target === 'boss' || result.can_submit === true,
        message: result.logged_in ? '账号已登录' : result.initialized ? '请在浏览器中完成登录' : '请打开登录浏览器' } }));
    } catch (reason) { setError((reason as Error).message); }
    finally { setSubmitting(false); }
  }

  async function deleteJob() {
    if (!job) return;
    setSubmitting(true); setError(null);
    try {
      if (editorUnsaved && resumeEditor.current) await resumeEditor.current.flush();
      await api(`/delivery/jobs/${job.id}`, { method: 'DELETE' });
      localStorage.removeItem(`job-workspace-step-${job.id}`);
      localStorage.removeItem('job-workspace-selected');
      await refresh(); setSelectedId(''); setStep(0); setDeletingJob(false);
    } catch (reason) { setError((reason as Error).message); }
    finally { setSubmitting(false); }
  }

  async function saveGreeting() {
    if (!pack) return false;
    setSubmitting(true); setError(null);
    try {
      await api(`/delivery/packages/${pack.id}/greeting`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ greeting }) });
      await refresh(); setNotice('打招呼语已保存'); return true;
    } catch (reason) { setError((reason as Error).message); return false; }
    finally { setSubmitting(false); }
  }

  async function send() {
    if (!pack) return;
    if (greeting !== pack.greeting && !await saveGreeting()) return;
    await submit('send', { package_ids: [pack.id] });
  }

  async function selectJob(id: string) {
    try {
      if (editorUnsaved && resumeEditor.current) await resumeEditor.current.flush();
      setSelectedId(id);
    } catch (reason) { setError((reason as Error).message); }
  }

  async function navigateStep(value: number) {
    try {
      if (editorUnsaved && resumeEditor.current) await resumeEditor.current.flush();
      selectStep(value);
    } catch (reason) { setError((reason as Error).message); }
  }

  async function selectVersion(id: string) {
    try {
      if (editorUnsaved && resumeEditor.current) await resumeEditor.current.flush();
      if (pack?.status === 'ready' && greeting !== pack.greeting && !await saveGreeting()) return;
      setVersionId(id);
      selectStep(2);
    } catch (reason) { setError((reason as Error).message); }
  }

  async function exportMaterials(continueAfter: boolean, downloadPng = false) {
    if (!pack || !resumeEditor.current) return;
    setSubmitting(true); setError(null);
    try {
      const expectedRevision = await resumeEditor.current.flush();
      if (greeting !== pack.greeting) await api(`/delivery/packages/${pack.id}/greeting`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ greeting }) });
      const task = await api<Task>('/delivery/export', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ package_ids: [pack.id], expected_revision: expectedRevision }) });
      setExportRequest({ taskId: task.id, packageId: pack.id, continueAfter, downloadPng });
      await refresh();
    } catch (reason) { setError((reason as Error).message); }
    finally { setSubmitting(false); }
  }

  const progressText = jobActive?.progress || (pack?.status === 'sent' ? '申请已投递，记录已保存' : pack?.status === 'needs_verification' ? '发送结果待核实' : editorUnsaved ? '正在保存简历修改…' : pack?.resume_dirty ? '简历已保存，等待重新导出' : pack ? '材料已准备完成' : needsAnalysis ? 'JD 已保存，等待分析' : '岗位分析已完成');

  async function generateWebsiteProjects() {
    if (!pack) return;
    setSubmitting(true); setError(null);
    try {
      const expectedRevision = resumeEditor.current ? await resumeEditor.current.flush() : pack.editor_revision || 0;
      await api('/delivery/website-projects', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ package_ids: [pack.id], expected_revision: expectedRevision }) });
      await refresh();
    } catch (reason) { setError((reason as Error).message); }
    finally { setSubmitting(false); }
  }

  async function generateSupplement(kind: 'english_resume' | 'self_description') {
    if (!pack) return;
    setSubmitting(true); setError(null);
    try {
      const expectedRevision = resumeEditor.current ? await resumeEditor.current.flush() : pack.editor_revision || 0;
      await api(`/delivery/supplements/${kind}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ package_ids: [pack.id], expected_revision: expectedRevision }) });
      await refresh();
    } catch (reason) { setError((reason as Error).message); }
    finally { setSubmitting(false); }
  }

  const websiteProjectsOption = <fieldset className="generation-options"><legend>同时生成（可多选）</legend>
    <label className="website-projects-option"><input type="checkbox" checked={includeEnglishResume} disabled={disabled} onChange={event => setIncludeEnglishResume(event.target.checked)} />中英文简历</label>
    <label className="website-projects-option"><input type="checkbox" checked={includeWebsiteProjects} disabled={disabled} onChange={event => setIncludeWebsiteProjects(event.target.checked)} />项目职责和项目描述</label>
    <label className="website-projects-option"><input type="checkbox" checked={includeSelfDescription} disabled={disabled} onChange={event => setIncludeSelfDescription(event.target.checked)} />自我描述</label>
  </fieldset>;

  return <div className="application-workspace">
    <a className="workspace-skip" href="#application-main">跳到申请内容</a>
    <aside className="job-sidebar" aria-label="岗位列表" inert={!!modal || addingJob || deletingJob}>
      <div className="workspace-brand"><span className="brand-icon"><BriefcaseBusiness size={20} /></span><div><strong>求职工作台</strong><span>每个机会，认真准备</span></div></div>
      <div className="sidebar-create-actions"><button className="workspace-primary search-jobs" onClick={() => setModal('search')}><Search size={16} />搜索岗位</button><button className="workspace-secondary" onClick={() => setAddingJob(true)}>添加 JD</button></div>
      <label className="job-search"><Search size={15} /><input aria-label="搜索公司或岗位" placeholder="搜索公司或岗位" value={query} onChange={event => setQuery(event.target.value)} /></label>
      <label className="job-company-filter"><span>公司</span><select aria-label="筛选岗位公司" value={companyFilter} onChange={event => setCompanyFilter(event.target.value)}><option value="all">全部公司</option>{companies.map(company => <option key={company} value={`company:${company}`}>{company || '公司未填写'}</option>)}</select></label>
      <div className="job-list-heading"><span>我的岗位 <b>{jobs.length}</b></span><select aria-label="筛选岗位状态" value={filter} onChange={event => setFilter(event.target.value)}>{['全部岗位', '正在处理', '待分析', '待准备材料', '待确认', '已投递', '待核实'].map(value => <option key={value}>{value}</option>)}</select></div>
      <nav className="job-list">
        {!snapshot && <p className="sidebar-empty">正在读取岗位…</p>}
        {snapshot && !filtered.length && <p className="sidebar-empty">{jobs.length ? '没有符合搜索条件的岗位' : '搜索岗位后，申请进度会保存在这里。'}</p>}
        {filtered.map(item => {
          const value = packageFor(item.id);
          const working = isJobWorking(item.id);
          return <button key={item.id} ref={job?.id === item.id ? selectedButton : undefined} className={`job-list-item ${job?.id === item.id ? 'selected' : ''}`} aria-current={job?.id === item.id ? 'page' : undefined} onClick={() => void selectJob(item.id)}>
            <span className="job-title"><strong>{item.title}</strong>{working && <LoaderCircle className="spin job-spinner" size={15} aria-label="正在处理该岗位" />}</span><span className="job-company">{item.company}</span>
            <span className="job-item-bottom"><span className={`job-status ${value?.status || ''}`}><i />{working ? '正在处理' : item.match.status === 'pending' ? '待分析' : stateLabel(value)}</span><span>{sourceName(item)}</span></span>
          </button>;
        })}
      </nav>
      {job && <button className="workspace-secondary" disabled={!!jobActive || submitting} onClick={() => { setError(null); setDeletingJob(true); }}>删除当前岗位</button>}
      <div className="sidebar-footer"><span><CheckCheck size={15} />已投递 {sentCount} 个岗位</span><button onClick={() => setModal('settings')}><Settings2 size={17} />设置</button></div>
    </aside>
    <main className="application-main" id="application-main" inert={!!modal || addingJob}>
      <header className="workspace-topbar"><span>我的申请 <ChevronRight size={14} /><span>{job?.company || '求职工作台'}</span></span><div className="workspace-topbar-actions"><button disabled={!job || disabled} onClick={() => { setRevision(''); setModal('regenerate'); }}><Sparkles size={15} />重新生成简历</button><button onClick={() => setModal('settings')}><Settings2 size={15} />平台与设置</button></div></header>
      {error && <div className="workspace-alert" role="alert"><CircleAlert size={17} /><span>{error}</span><button aria-label="关闭错误提示" onClick={() => setError(null)}><X size={16} /></button></div>}
      {!snapshot?.configured && snapshot && <div className="workspace-alert">搜索与投递服务尚未配置，请使用 start-integrated.ps1 启动。</div>}
      {job ? <>
        <section className="application-heading"><div className="heading-caption">正在准备的机会</div><h1>{job.title}</h1><div className="job-meta"><span className="company-avatar">{job.company.slice(0, 1)}</span><strong>{job.company}</strong><span className="meta-divider" /><span><MapPin size={14} />{job.city || '地点未填写'}</span><span className="platform-badge">{sourceName(job)}</span><button onClick={() => setModal('jd')}>查看完整 JD<ExternalLink size={13} /></button></div></section>
        <nav className="application-steps" aria-label="申请流程">{steps.map((label, index) => <button key={label} className={`${step === index ? 'current' : ''} ${index < reached ? 'complete' : ''}`} disabled={index > reached} aria-current={step === index ? 'step' : undefined} onClick={() => void navigateStep(index)}><span className="step-number">{index < reached && step !== index ? <Check size={15} /> : String(index + 1).padStart(2, '0')}</span><span>{label}</span></button>)}</nav>
        <div className={`workspace-progress ${jobActive ? 'working' : ''}`} role="status" aria-live="polite">{jobActive ? <LoaderCircle className="spin" size={16} /> : <Check size={16} />}<span className="progress-copy" key={progressText}>{progressText}</span>{active && !jobActive && <small>其他岗位正在处理，可以继续操作当前岗位</small>}</div>
        {failure && <div className="workspace-alert" role="alert"><CircleAlert size={17} /><span>{failure.error || '任务已中断，请重新准备材料。'}</span></div>}
        {!active && latestTask?.status === 'failed' && latestTask !== failure && <div className="workspace-alert" role="alert"><CircleAlert size={17} /><span>{latestTask.error}</span></div>}
        <div className="application-content">
          {(step === 2 || step === 3) && pack && <SupplementCards key={`supplements-${pack.id}`} pack={pack} unsaved={editorUnsaved} disabled={disabled || !editorReady} action={jobActive?.action} onGenerate={kind => void generateSupplement(kind)} />}
          {(step === 2 || step === 3) && pack && <WebsiteProjectsCard key={pack.id} packageId={pack.id} projects={pack.website_projects}
            stale={!!pack.website_projects && (editorUnsaved || pack.website_projects_revision !== (pack.editor_revision || 0))}
            disabled={disabled || !editorReady} generating={jobActive?.action === 'website_projects'} onGenerate={() => void generateWebsiteProjects()} />}
          {(step === 0 || step === 1) && !pack && !jobActive && websiteProjectsOption}
          {step === 0 && <section className="analysis-layout"><article className="workspace-card analysis-card"><div className="section-caption"><Sparkles size={17} />岗位分析</div><h2>这份岗位与你的经历有什么联系</h2><div className="match-label">{needsAnalysis ? <FileText size={14} /> : <Check size={14} />}{needsAnalysis ? '等待岗位分析' : job.match.eligible ? '符合当前申请条件' : '申请条件需要关注'}</div><h3>匹配依据</h3><p>{job.match.reason}</p><h3>可以重点展示的经历</h3><p>{job.match.evidence}</p></article><article className="workspace-card jd-card"><div className="card-heading"><h2>岗位要求</h2><button onClick={() => setModal('jd')}>展开阅读<ExternalLink size={13} /></button></div><p className="jd-excerpt">{job.description}</p></article></section>}
          {step === 1 && <section className="workspace-card preparation-card"><span className="preparation-icon">{jobActive ? <LoaderCircle className="spin" size={28} /> : <FileText size={28} />}</span><h2>{jobActive ? '正在为这个岗位准备申请材料' : pack ? '定制材料已准备完成' : '准备一份有针对性的简历'}</h2><p>根据岗位要求选择项目经历，检查内容，导出简历并准备打招呼语。</p>{!pack && !jobActive && <button className="workspace-primary" disabled={disabled} onClick={() => void submit('prepare', { job_ids: [job.id] })}>生成定制材料<ArrowRight size={16} /></button>}{pack && <button className="workspace-primary" onClick={() => selectStep(2)}>查看简历<ArrowRight size={16} /></button>}</section>}
          {(step === 2 || step === 3) && pack && <section className="materials-layout">
            <article className="resume-card">
              <div className="card-heading"><div><FileText size={16} /><h2>定制简历</h2><span>A4 · 单页</span></div><div className="resume-download-actions">{pack.resume_dirty || editorUnsaved ? <><button disabled={disabled || !editorReady} onClick={() => void exportMaterials(false)}><ArrowDownToLine size={14} />重新导出 PDF</button><button disabled={disabled || !editorReady} onClick={() => void exportMaterials(false, true)}><ArrowDownToLine size={14} />导出 PNG</button></> : <><a href={packageUrl(pack, 'pdf')} target="_blank" rel="noreferrer"><ArrowDownToLine size={14} />下载 PDF</a><a href={packageUrl(pack, 'image')} download><ArrowDownToLine size={14} />导出 PNG</a></>}</div></div>
              <ResumeEditor key={pack.id} ref={resumeEditor} packageId={pack.id} needsExport={!!pack.resume_dirty} readOnly={!!jobActive || step === 3 || pack.status !== 'ready'} onReady={setEditorReady} onUnsaved={setEditorUnsaved} onSaved={() => void refresh().catch(reason => setError((reason as Error).message))} />
              {versions.length > 1 && <label className="resume-version">简历版本<select aria-label="简历版本" disabled={!!jobActive || submitting} value={pack.id} onChange={event => void selectVersion(event.target.value)}>{versions.map((item, index) => <option key={item.id} value={item.id}>{index === 0 ? '最新版本 · ' : ''}{dateTime(item.created_at)} · {stateLabel(item)}</option>)}</select></label>}
            </article>
            <div className="material-side">
              <article className="workspace-card greeting-card">
                <div className="card-heading"><h2>打招呼语</h2><span>{greeting.length} 字符</span></div><p>与这份简历一起发送给招聘者</p>
                <textarea aria-label="打招呼语" maxLength={500} value={greeting} readOnly={pack.status !== 'ready' || !!jobActive} onChange={event => setGreeting(event.target.value)} />
                <div className="greeting-footer"><span role="status">{notice || (greeting !== pack.greeting ? '修改尚未保存' : '已保存')}</span>{pack.status === 'ready' && <button disabled={disabled || !greeting.trim() || greeting === pack.greeting} onClick={() => void saveGreeting()}>保存修改</button>}</div>
              </article>
              {step === 2 ? <article className="workspace-card materials-note"><CheckCheck size={18} /><h3>{pack.resume_dirty || editorUnsaved ? '简历已修改，等待重新导出' : '确认简历与打招呼语'}</h3><p>点击简历文字可以直接微调。确认后重新导出，并检查页面占用与文字边界。</p><button disabled={disabled || pack.status !== 'ready'} onClick={() => { setRevision(''); setModal('revision'); }}>填写修改要求<ArrowRight size={14} /></button></article> :
                <article className="workspace-card submission-card"><h2>确认投递信息</h2>
                  <dl><dt>招聘平台</dt><dd>{sourceName(job)}</dd><dt>目标公司</dt><dd>{job.company}</dd><dt>申请材料</dt><dd>打招呼语、对应岗位的简历</dd></dl>
                  {canDeliver ? <><p>{jobConnection?.message || '投递前检查平台登录状态'}</p><button disabled={disabled || browserBusy} onClick={() => void checkConnection(jobPlatform)}>检查登录状态</button>{jobConnection && !jobConnection.canSubmit && <p className="submission-warning">该平台目前支持准备材料，可以通过岗位原文入口完成申请。</p>}</> : <><p>下载简历后，通过招聘方提供的渠道完成申请。</p>{job.url && <a href={job.url} target="_blank" rel="noreferrer">打开招聘链接<ExternalLink size={14} /></a>}</>}
                </article>}
            </div>
          </section>}
          {step === 4 && pack && <section className="workspace-card result-card"><span className={`result-icon ${pack.status === 'sent' ? 'sent' : ''}`}>{pack.status === 'sent' ? <CheckCheck size={32} /> : <CircleAlert size={32} />}</span><h2>{pack.status === 'sent' ? '简历已投递' : '发送结果待核实'}</h2><p>{job.company} · {job.title}</p><span>{dateTime(pack.sent_at || pack.attempted_at || pack.created_at)}</span><div className="result-detail"><FileText size={18} /><div><strong>本次投递材料</strong><span>定制简历与打招呼语</span></div><button onClick={() => selectStep(2)}>查看材料<ArrowRight size={14} /></button></div>{pack.status === 'needs_verification' && <button className="workspace-primary" disabled={disabled} onClick={() => void submit('verify', { package_ids: [pack.id] })}>核实发送结果</button>}</section>}
        </div>
        <footer className="application-actions"><span>{step === 0 ? needsAnalysis ? '分析完整 JD，查看岗位与经历的匹配情况' : '岗位分析已完成，可以开始准备材料' : step === 1 ? jobActive ? '材料完成后会自动展示简历预览' : '材料按当前岗位要求编写' : step === 2 ? '确认简历内容和打招呼语后继续' : step === 3 ? canDeliver ? `将通过${platformNames[jobPlatform]}发送申请材料` : '下载材料后通过招聘方提供的渠道申请' : '申请材料和投递记录已保存'}</span><div>
          {step > 0 && step < 4 && <button className="workspace-secondary" onClick={() => void navigateStep(step - 1)}><ArrowLeft size={15} />上一步</button>}
          {step === 0 && <button className="workspace-primary" disabled={disabled && !pack} onClick={() => pack ? selectStep(2) : void submit(needsAnalysis ? 'analyze' : 'prepare', { job_ids: [job.id] })}>{pack ? '查看申请材料' : needsAnalysis ? '分析 JD' : '生成定制材料'}<ArrowRight size={16} /></button>}
          {step === 1 && pack && <button className="workspace-primary" onClick={() => selectStep(2)}>查看申请材料<ArrowRight size={16} /></button>}
          {step === 2 && pack?.status === 'ready' && <button className="workspace-primary" disabled={disabled || !editorReady || !greeting.trim()} onClick={() => void exportMaterials(true)}>确认材料，继续<ArrowRight size={16} /></button>}
          {step === 2 && pack?.status !== 'ready' && <button className="workspace-primary" onClick={() => selectStep(4)}>查看投递结果<ArrowRight size={16} /></button>}
          {step === 3 && (canDeliver ? <button className="workspace-primary" disabled={disabled || browserBusy || pack?.status !== 'ready' || pack.resume_dirty || editorUnsaved || !jobConnection?.loggedIn || !jobConnection?.canSubmit || !greeting.trim()} onClick={() => void send()}>确认并投递<ArrowRight size={16} /></button> : pack && !pack.resume_dirty && !editorUnsaved && <a className="workspace-primary" href={packageUrl(pack, 'pdf')} target="_blank" rel="noreferrer">下载简历，前往申请<ArrowDownToLine size={16} /></a>)}
          {step === 4 && <a className="workspace-secondary" href={job.url} target="_blank" rel="noreferrer">前往招聘平台<ExternalLink size={14} /></a>}
        </div></footer>
      </> : <section className="workspace-welcome"><span className="preparation-icon"><BriefcaseBusiness size={30} /></span><h1>{snapshot ? '从一个合适的岗位开始' : '正在读取你的申请'}</h1><p>搜索岗位，准备定制简历，在这里完成每一步申请。</p>{active && <div className="workspace-progress" role="status"><LoaderCircle className="spin" size={16} />{active.progress}</div>}{latestTask?.error && <div className="workspace-alert" role="alert">{latestTask.error}</div>}<button className="workspace-primary" disabled={!snapshot || disabled} onClick={() => setModal('search')}><Search size={16} />搜索岗位</button></section>}
    </main>
    {modal && <div className="workspace-modal-backdrop" onClick={event => { if (event.target === event.currentTarget) setModal(null); }} onKeyDown={event => { if (event.key === 'Escape') setModal(null); }}><section className={`workspace-modal ${modal === 'jd' ? 'jd-modal' : ''}`} role="dialog" aria-modal="true" aria-labelledby="workspace-dialog-title"><header><h2 id="workspace-dialog-title">{modal === 'search' ? '寻找新的岗位' : modal === 'settings' ? '平台与设置' : modal === 'revision' ? '修改定制材料' : modal === 'regenerate' ? '重新生成简历' : '完整岗位说明'}</h2><button autoFocus aria-label="关闭窗口" onClick={() => setModal(null)}><X size={20} /></button></header>
      {modal === 'search' && <form onSubmit={event => { event.preventDefault(); void submit('search', { platform, keywords: keywords.split(/[,，]/).map(value => value.trim()).filter(Boolean), limit, prepare, include_website_projects: includeWebsiteProjects }); }}>
        <label>招聘平台<select value={platform} onChange={event => setPlatform(event.target.value as Platform)}>{Object.entries(platformNames).map(([value, name]) => <option value={value} key={value}>{name}</option>)}</select></label>
        <div className="settings-account"><BriefcaseBusiness size={22} /><div><strong>{platformNames[platform]}</strong><p role="status">{connection[platform]?.message || '正在检查登录状态…'}</p></div></div>
        <div className="settings-buttons"><button type="button" className="workspace-secondary" disabled={browserDisabled} onClick={() => void submit(`login?platform=${platform}`)}>打开登录浏览器</button><button type="button" className="workspace-secondary" disabled={browserDisabled} onClick={() => void checkConnection(platform)}>检查登录状态</button></div>
        <label>岗位关键词<input value={keywords} onChange={event => setKeywords(event.target.value)} placeholder="使用逗号分隔多个关键词" /></label>
        <div className="search-options"><label>读取岗位数量<input type="number" min={1} max={100} value={limit} onChange={event => setLimit(Number(event.target.value))} /></label><span><MapPin size={15} />北京 · 实习</span></div>
        <label className="checkbox-label"><input type="checkbox" checked={prepare} onChange={event => setPrepare(event.target.checked)} />搜索后自动准备已导入岗位的材料</label><p>搜索导入的岗位会保存到左侧列表，分析意见供你决定是否申请。</p>
        {prepare && websiteProjectsOption}
        <button className="workspace-primary" disabled={browserDisabled || !keywords.trim() || !connection[platform]?.loggedIn} type="submit"><Search size={16} />搜索岗位</button>
      </form>}
      {modal === 'settings' && <div className="workspace-settings"><label>招聘平台<select value={platform} onChange={event => setPlatform(event.target.value as Platform)}>{Object.entries(platformNames).map(([value, name]) => <option key={value} value={value}>{name}</option>)}</select></label><div className="settings-account"><BriefcaseBusiness size={22} /><div><strong>{platformNames[platform]}</strong><p>{connection[platform]?.message || '尚未检查登录状态'}</p></div></div><div className="settings-buttons"><button className="workspace-secondary" disabled={browserDisabled} onClick={() => void submit(`login?platform=${platform}`)}>打开登录浏览器</button><button className="workspace-primary" disabled={browserDisabled} onClick={() => void checkConnection(platform)}>检查登录状态</button></div><p>在浏览器中完成平台登录，再返回这里检查登录状态。</p></div>}
      {modal === 'jd' && job && <div className="full-jd"><h3>{job.company} · {job.title}</h3><p>{job.description}</p>{job.url && <a className="workspace-secondary" href={job.url} target="_blank" rel="noreferrer">查看招聘平台原文<ExternalLink size={14} /></a>}</div>}
      {modal === 'revision' && job && <form onSubmit={event => { event.preventDefault(); void submit('prepare', { job_ids: [job.id], revision, base_package_id: pack?.id }); }}><label>希望怎样修改<textarea value={revision} onChange={event => setRevision(event.target.value)} placeholder="例如：增加科研工具项目的篇幅，突出检索和引用核验。" maxLength={4000} rows={6} /></label>{websiteProjectsOption}<p>根据修改要求重新生成并检查材料，完成后显示新的简历。</p><button className="workspace-primary" disabled={disabled || !revision.trim()} type="submit">重新生成材料<ArrowRight size={16} /></button></form>}
      {modal === 'regenerate' && job && <form onSubmit={event => { event.preventDefault(); void submit('prepare', { job_ids: [job.id], revision, fresh: true }); }}><label>生成要求（选填）<textarea aria-label="生成要求（选填）" value={revision} onChange={event => setRevision(event.target.value)} placeholder="可以留空，也可以指定项目、重点或表达方式。" maxLength={4000} rows={5} /></label>{websiteProjectsOption}<p>根据完整 JD 和最新个人资料重新选择项目并编写简历，原有版本和手动修改会保留。</p><button className="workspace-primary" disabled={disabled} type="submit">开始重新生成<ArrowRight size={16} /></button></form>}
      {error && <p className="modal-error" role="alert">{error}</p>}
    </section></div>}
    {deletingJob && job && <div className="workspace-modal-backdrop"><section className="workspace-modal" role="dialog" aria-modal="true" aria-labelledby="delete-job-title"><header><h2 id="delete-job-title">删除岗位</h2><button disabled={submitting} aria-label="关闭删除窗口" onClick={() => setDeletingJob(false)}><X size={20} /></button></header><p>确认删除「{job.company} · {job.title}」？岗位将从列表移除，岗位原文、申请材料和投递记录会保留。</p><div className="settings-buttons"><button className="workspace-secondary" disabled={submitting} onClick={() => setDeletingJob(false)}>取消</button><button className="workspace-primary" disabled={submitting || !!jobActive} onClick={() => void deleteJob()}>{submitting ? '正在删除…' : '确认删除'}</button></div>{error && <p role="alert">{error}</p>}</section></div>}
    {addingJob && <AddJobDialog onClose={() => setAddingJob(false)} onSaved={async id => { await refresh(); setSelectedId(id); setFilter('全部岗位'); setCompanyFilter('all'); setQuery(''); setAddingJob(false); }} />}
  </div>;
}
