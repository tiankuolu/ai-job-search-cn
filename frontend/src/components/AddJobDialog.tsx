import { useState, type FormEvent } from 'react';
import { ArrowRight, FileUp, LoaderCircle, X } from 'lucide-react';
import { api } from '../types';

type JobFields = { company: string; title: string; city: string; url: string | null; platform: string | null; responsibilities: string; requirements: string; bonus: string; details: string };
type Extraction = { import_id: string; filename: string; description: string; pages: number; method: string; fields: JobFields };
const sectionLabels = { responsibilities: '岗位职责', requirements: '岗位要求', bonus: '加分项', details: '其他详情' } as const;

export default function AddJobDialog({ onClose, onSaved }: { onClose: () => void; onSaved: (id: string) => Promise<void> }) {
  const [mode, setMode] = useState<'text' | 'file' | 'url'>('text');
  const [company, setCompany] = useState('');
  const [title, setTitle] = useState('');
  const [city, setCity] = useState('');
  const [platform, setPlatform] = useState('');
  const [url, setUrl] = useState('');
  const [description, setDescription] = useState('');
  const [extraction, setExtraction] = useState<Extraction | null>(null);
  const [sections, setSections] = useState({ responsibilities: '', requirements: '', bonus: '', details: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [urlNotice, setUrlNotice] = useState('');

  function useExtraction(result: Extraction) {
    setExtraction(result); setDescription(result.description);
    setCompany(result.fields.company); setTitle(result.fields.title); setCity(result.fields.city);
    setUrl(result.fields.url || ''); setPlatform(result.fields.platform || '');
    setSections({ responsibilities: result.fields.responsibilities, requirements: result.fields.requirements,
      bonus: result.fields.bonus, details: result.fields.details });
  }

  async function readUrl() {
    setBusy(true); setError(''); setUrlNotice('');
    try {
      const result = await api<Extraction | { status: 'login_required'; message: string }>('/delivery/imports/url', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url: url.trim() }),
      });
      if ('fields' in result) useExtraction(result);
      else setUrlNotice(result.message);
    } catch (reason) { setError((reason as Error).message); }
    finally { setBusy(false); }
  }

  async function openUrl() {
    setBusy(true); setError('');
    try {
      const result = await api<{ message: string }>('/delivery/imports/url/open', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url: url.trim() }),
      });
      setUrlNotice(result.message);
    } catch (reason) { setError((reason as Error).message); }
    finally { setBusy(false); }
  }

  async function extract(file: File) {
    setError('');
    if (file.size > 20 * 1024 * 1024) { setError('文件大小不能超过 20 MB'); return; }
    setBusy(true);
    try {
      const body = new FormData();
      body.append('file', file);
      const result = await api<Extraction>('/delivery/imports/extract', { method: 'POST', body });
      useExtraction(result);
    } catch (reason) { setError((reason as Error).message); }
    finally { setBusy(false); }
  }

  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const job = await api<{ id: string }>('/delivery/jobs', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company: company.trim(), title: title.trim(), city: city.trim(),
          platform: platform || null, url: url.trim() || null, description: description.trim(), import_id: extraction?.import_id || null,
          fields: extraction ? { company: company.trim(), title: title.trim(), city: city.trim(), url: url.trim() || null, platform: platform || null, ...sections } : null }),
      });
      await onSaved(job.id);
    } catch (reason) { setError((reason as Error).message); }
    finally { setBusy(false); }
  }

  return <div className="workspace-modal-backdrop" onClick={event => { if (!busy && event.target === event.currentTarget) onClose(); }} onKeyDown={event => { if (!busy && event.key === 'Escape') onClose(); }}>
    <section className="workspace-modal add-job-modal" role="dialog" aria-modal="true" aria-labelledby="add-job-title">
      <header><div><h2 id="add-job-title">添加 JD</h2><p className="add-job-subtitle">保存你找到的机会，继续准备对应的申请材料。</p></div><button autoFocus aria-label="关闭添加岗位" disabled={busy} onClick={onClose}><X size={20} /></button></header>
      <div className="import-modes" role="tablist" aria-label="添加岗位方式">
        <button role="tab" disabled={busy} aria-selected={mode === 'text'} onClick={() => setMode('text')}>手动填写</button>
        <button role="tab" disabled={busy} aria-selected={mode === 'file'} onClick={() => setMode('file')}>导入文件</button>
        <button role="tab" disabled={busy} aria-selected={mode === 'url'} onClick={() => setMode('url')}>解析链接</button>
      </div>
      <form onSubmit={event => void save(event)}>
        {mode === 'url' && <div className="url-import-area"><label>招聘页面 URL<input aria-label="招聘页面 URL" type="url" value={url} disabled={busy} onChange={event => { setUrl(event.target.value); setExtraction(null); setDescription(''); setCompany(''); setTitle(''); setUrlNotice(''); }} placeholder="粘贴具体岗位的招聘链接" /></label><div className="settings-buttons"><button type="button" className="workspace-primary" disabled={busy || !url.trim()} onClick={() => void readUrl()}>{busy ? <LoaderCircle className="spin" size={16} /> : <ArrowRight size={16} />}解析链接</button><button type="button" className="workspace-secondary" disabled={busy || !url.trim()} onClick={() => void openUrl()}>打开网页登录</button></div><p role="status">{urlNotice || '读取完整岗位后自动填写。需要登录时，完成网页登录后再次点击解析链接。'}</p></div>}
        {mode === 'file' && <div className="job-upload-area"><FileUp size={25} /><strong>{busy ? '正在识别文字并提取岗位信息…' : extraction?.filename || '选择 JD 文件'}</strong><span>PDF、Markdown、PNG、JPEG、WebP · 最大 20 MB</span><input aria-label="导入 JD 文件" type="file" accept=".pdf,.md,.png,.jpg,.jpeg,.webp" disabled={busy} onChange={event => { const file = event.target.files?.[0]; if (file) void extract(file); event.target.value = ''; }} />{busy && <LoaderCircle className="spin" size={18} />}</div>}
        {extraction && <p className="import-result" role="status">已解析 {extraction.pages} 页 · {extraction.method}。岗位信息已自动填写，可以核对和修改；原文未提供的字段留空。</p>}
        <div className="job-form-row"><label>公司名称（选填）<input aria-label="公司名称" maxLength={200} disabled={busy} value={company} onChange={event => setCompany(event.target.value)} placeholder="未提供公司名称时留空" /></label><label>岗位名称<input required maxLength={200} disabled={busy} value={title} onChange={event => setTitle(event.target.value)} placeholder="填写岗位名称" /></label></div>
        <div className="job-form-row"><label>工作地点（选填）<input maxLength={100} disabled={busy} value={city} onChange={event => setCity(event.target.value)} placeholder="按照 JD 填写" /></label><label>招聘平台（选填）<select disabled={busy} value={platform} onChange={event => setPlatform(event.target.value)}><option value="">手动保存</option><option value="boss">BOSS直聘</option><option value="liepin">猎聘</option><option value="nowcoder">牛客</option><option value="shixiseng">实习僧</option></select></label></div>
        {mode !== 'url' && <label>招聘链接（选填）<input type="url" disabled={busy} value={url} onChange={event => setUrl(event.target.value)} placeholder="https://" /></label>}
        <label>JD 正文<textarea required maxLength={100000} rows={10} disabled={busy} value={description} onChange={event => setDescription(event.target.value)} placeholder={mode === 'file' ? '文件解析后显示在这里，可以直接修改识别结果。' : '粘贴完整的岗位职责、任职要求和其他招聘信息。'} /></label>
        {extraction && (Object.keys(sectionLabels) as (keyof typeof sectionLabels)[]).map(key => <label key={key}>{sectionLabels[key]}<textarea aria-label={sectionLabels[key]} maxLength={100000} rows={4} disabled={busy} value={sections[key]} onChange={event => setSections(current => ({ ...current, [key]: event.target.value }))} placeholder="原文未提供时留空" /></label>)}
        <div className="import-form-footer"><span>保存后进入左侧岗位列表，可继续分析和准备简历。</span><button className="workspace-primary" type="submit" disabled={busy || !title.trim() || !description.trim()}>{busy ? <LoaderCircle className="spin" size={16} /> : <ArrowRight size={16} />}保存岗位</button></div>
        {error && <p className="modal-error" role="alert">{error}</p>}
      </form>
    </section>
  </div>;
}
