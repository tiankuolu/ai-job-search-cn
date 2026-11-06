import { ArrowDownToLine, Check, FileText, Maximize2, Pencil } from 'lucide-react';
import type { Document } from '../types';
import ArtifactView from '../ui/ArtifactView';
import VersionDiff from '../ui/VersionDiff';
import Markdown from './Markdown';

type Props = {
  artifacts: Document[];
  documentIndex: number;
  onDocumentIndex: (value: number) => void;
  current: Document | undefined;
  onRead: (document: Document) => void;
  onDownload: (document: Document) => void;
  editing: boolean;
  onEditing: (value: boolean) => void;
  draft: string;
  onDraft: (value: string) => void;
  onSaveDraft: () => void;
  onFinalize: () => void;
  finalized: boolean;
  baseContent: string;
  showDiff: boolean;
  onShowDiff: () => void;
};

export default function ArtifactsView({ artifacts, documentIndex, onDocumentIndex, current, onRead, onDownload, editing, onEditing, draft, onDraft, onSaveDraft, onFinalize, finalized, baseContent, showDiff, onShowDiff }: Props) {
  const content = draft || current?.content || '';
  const actions = current ? <>
    <select aria-label="选择成果文件" value={documentIndex} onChange={event => onDocumentIndex(Number(event.target.value))}>
      {artifacts.map((document, index) => <option key={document.name} value={index}>{document.name}</option>)}
    </select>
    <button className="icon-button" aria-label="展开成果文件" onClick={() => onRead(current)}><Maximize2 size={15} /></button>
    <button className="icon-button" aria-label={showDiff ? '关闭版本对比' : '对比上一版'} onClick={onShowDiff} disabled={!baseContent}><FileText size={15} /></button>
    <button className="icon-button" aria-label="下载成果文件" onClick={() => onDownload(current)}><ArrowDownToLine size={16} /></button>
  </> : undefined;

  return <ArtifactView
    title={current?.name || '申请材料'}
    meta={current ? `${content.length.toLocaleString()} 字符${finalized ? ' · 已定稿' : ''}` : ''}
    actions={actions}
    state={current ? (editing ? 'loading' : 'default') : 'empty'}
    emptyText="运行一次申请材料任务，成果会出现在这里。"
  >
    {current && <>
      <div className="ui-artifact-tabs" role="tablist" aria-label="成果操作">
        <button type="button" role="tab" aria-selected={!editing} className={!editing ? 'active' : ''} onClick={() => onEditing(false)}>阅读</button>
        <button type="button" role="tab" aria-selected={editing} className={editing ? 'active' : ''} onClick={() => onEditing(true)}><Pencil size={13} />修改</button>
        <button type="button" role="tab" aria-selected={finalized} className={finalized ? 'active' : ''} onClick={onFinalize} disabled={!content}><Check size={13} />{finalized ? '已定稿' : '定稿'}</button>
      </div>
      {editing ? <div className="draft-editor">
        <label className="field">材料正文
          <textarea aria-label="材料正文" value={draft || current.content} onChange={event => onDraft(event.target.value)} rows={22} />
        </label>
        <div className="note-actions"><span>修改只保存在本机；定稿后可下载。</span><button className="secondary" onClick={onSaveDraft}>保存修改</button></div>
      </div> : <div className="ui-prose"><Markdown>{content}</Markdown></div>}
      {showDiff && baseContent && <VersionDiff before={baseContent} after={content} title="上一版与当前稿" beforeLabel="上一版" afterLabel="当前稿" />}
    </>}
  </ArtifactView>;
}
