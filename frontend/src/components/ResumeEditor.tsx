import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { Check, CircleAlert, Expand, LoaderCircle, Minimize2 } from 'lucide-react';
import { api } from '../types';

export type ResumeEditorHandle = { flush: () => Promise<number> };
type EditorDocument = { document: string; revision: number; dirty: boolean };
type Props = { packageId: string; readOnly: boolean; needsExport: boolean; onSaved: () => void; onUnsaved: (value: boolean) => void; onReady: (value: boolean) => void };

export default forwardRef<ResumeEditorHandle, Props>(function ResumeEditor({ packageId, readOnly, needsExport, onSaved, onUnsaved, onReady }, ref) {
  const frame = useRef<HTMLIFrameElement>(null);
  const area = useRef<HTMLDivElement>(null);
  const callbacks = useRef({ onSaved, onUnsaved, onReady });
  callbacks.current = { onSaved, onUnsaved, onReady };
  const readOnlyRef = useRef(readOnly);
  readOnlyRef.current = readOnly;
  const mounted = useRef(false);
  const version = useRef(0);
  const content = useRef('');
  const saved = useRef('');
  const loaded = useRef(false);
  const timer = useRef<number | undefined>(undefined);
  const saving = useRef<Promise<void> | null>(null);
  const snapshot = useRef<{ resolve: (value: string) => void; requestId: string } | null>(null);
  const [document, setDocument] = useState('');
  const [status, setStatus] = useState('正在加载简历…');
  const [error, setError] = useState('');
  const [scale, setScale] = useState(1);
  const [height, setHeight] = useState(1123);
  const [expanded, setExpanded] = useState(false);

  function post(type: string, data: Record<string, unknown> = {}) {
    frame.current?.contentWindow?.postMessage({ type, packageId, ...data }, '*');
  }

  async function drain() {
    if (saving.current) return saving.current;
    saving.current = (async () => {
      while (content.current !== saved.current) {
        const current = content.current;
        if (mounted.current) { setStatus('正在保存修改…'); setError(''); }
        const result = await api<{ revision: number }>(`/delivery/packages/${packageId}/resume`, {
          method: 'PATCH', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content: current, base_revision: version.current }),
        });
        version.current = result.revision;
        saved.current = current;
      }
      if (mounted.current) { setStatus('修改已保存，需要重新导出'); callbacks.current.onUnsaved(false); callbacks.current.onSaved(); }
    })();
    try { await saving.current; }
    catch (reason) {
      if (mounted.current) { setError((reason as Error).message); setStatus('保存失败'); callbacks.current.onUnsaved(true); }
      throw reason;
    } finally { saving.current = null; }
  }

  useImperativeHandle(ref, () => ({ flush: async () => {
    window.clearTimeout(timer.current);
    if (!loaded.current) throw new Error('简历尚未加载完成');
    if (!readOnlyRef.current) {
      const current = await new Promise<string>((resolve, reject) => {
        const requestId = crypto.randomUUID();
        const timeout = window.setTimeout(() => { snapshot.current = null; reject(new Error('无法读取当前简历内容，请重新打开简历')); }, 5000);
        snapshot.current = { requestId, resolve: value => { window.clearTimeout(timeout); resolve(value); } };
        post('resume.snapshot', { requestId });
      });
      content.current = current;
    }
    if (content.current !== saved.current || saving.current) await drain();
    return version.current;
  } }), [packageId]);

  useEffect(() => {
    let cancelled = false;
    mounted.current = true;
    loaded.current = false;
    callbacks.current.onReady(false);
    api<EditorDocument | { requires_conversion: true }>(`/delivery/packages/${packageId}/resume`).then(async initial => {
      if (cancelled) return;
      let result: EditorDocument;
      if ('requires_conversion' in initial) {
        setStatus('正在生成可编辑 HTML…');
        result = await api<EditorDocument>(`/delivery/packages/${packageId}/resume/convert`, { method: 'POST' });
        if (cancelled) return;
        callbacks.current.onSaved();
      } else result = initial;
      version.current = result.revision;
      setDocument(result.document);
      setStatus(result.dirty ? '修改已保存，需要重新导出' : '点击文字即可编辑');
    }).catch(reason => { if (!cancelled) { setError((reason as Error).message); setStatus('简历加载失败'); } });
    function receive(event: MessageEvent) {
      if (event.source !== frame.current?.contentWindow || event.data?.packageId !== packageId) return;
      const message = event.data;
      if (message.type === 'resume.ready' && typeof message.content === 'string') {
        saved.current = message.content;
        content.current = message.content;
        loaded.current = true;
        callbacks.current.onReady(true);
        post('resume.mode', { readOnly: readOnlyRef.current });
      }
      if (message.type === 'resume.changed' && typeof message.content === 'string' && !readOnlyRef.current) {
        content.current = message.content;
        callbacks.current.onUnsaved(content.current !== saved.current);
        setStatus('正在保存修改…');
        window.clearTimeout(timer.current);
        timer.current = window.setTimeout(() => { void drain().catch(reason => setError((reason as Error).message)); }, 500);
      }
      if (message.type === 'resume.height' && Number.isFinite(message.height)) setHeight(Math.max(1123, Math.min(message.height, 12000)));
      const pendingSnapshot = snapshot.current;
      if (message.type === 'resume.snapshot' && pendingSnapshot && message.requestId === pendingSnapshot.requestId && typeof message.content === 'string') {
        pendingSnapshot.resolve(message.content); snapshot.current = null;
      }
    }
    window.addEventListener('message', receive);
    return () => { cancelled = true; mounted.current = false; window.clearTimeout(timer.current); window.removeEventListener('message', receive); };
  }, [packageId]);

  useEffect(() => { if (loaded.current) post('resume.mode', { readOnly }); }, [readOnly]);
  useEffect(() => {
    if (!needsExport && loaded.current && content.current === saved.current) setStatus(version.current > 0 ? '修改已导出' : '点击文字即可编辑');
  }, [needsExport]);
  useEffect(() => {
    const observer = new ResizeObserver(entries => {
      const width = entries[0].contentRect.width;
      setScale(Math.min(1, Math.max(0.1, width / 794)));
    });
    if (area.current) observer.observe(area.current);
    return () => observer.disconnect();
  }, [expanded]);

  return <div className={`resume-editor ${expanded ? 'expanded' : ''}`}>
    <div className="resume-editor-toolbar"><span role="status">{error ? <CircleAlert size={13} /> : status.includes('正在') ? <LoaderCircle className="spin" size={13} /> : <Check size={13} />}{readOnly && loaded.current ? '查看简历' : status}</span><button onClick={() => setExpanded(value => !value)}>{expanded ? <Minimize2 size={14} /> : <Expand size={14} />}{expanded ? '收起编辑' : '放大编辑'}</button></div>
    {error && <p className="editor-error" role="alert">{error}</p>}
    <div className="resume-editor-area" ref={area}>
      <div className="resume-editor-paper" style={{ height: height * scale }}>
        {document && <iframe ref={frame} title="可编辑简历" sandbox="allow-scripts" srcDoc={document} style={{ width: 794, height, transform: `scale(${scale})` }} />}
      </div>
    </div>
  </div>;
});
