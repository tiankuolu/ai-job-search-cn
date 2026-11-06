import { useEffect, useState } from 'react';
import { ArrowDownToLine, Copy, LoaderCircle } from 'lucide-react';

export type SupplementPackage = { id: string; editor_revision?: number; english_resume_revision?: number; english_html?: string; self_description?: string; self_description_revision?: number };
type Props = { pack: SupplementPackage; unsaved: boolean; disabled: boolean; action?: string; onGenerate: (kind: 'english_resume' | 'self_description') => void };

export default function SupplementCards({ pack, unsaved, disabled, action, onGenerate }: Props) {
  const [copied, setCopied] = useState(false);
  useEffect(() => { setCopied(false); }, [pack.self_description]);
  const englishStale = unsaved || pack.english_resume_revision !== (pack.editor_revision || 0);
  const descriptionStale = unsaved || pack.self_description_revision !== (pack.editor_revision || 0);
  async function copy() { await navigator.clipboard.writeText(pack.self_description || ''); setCopied(true); }
  return <div className="supplement-cards">
    <section className="workspace-card">
      <div className="card-heading"><h2>英文简历</h2><button disabled={disabled} className="workspace-secondary" onClick={() => onGenerate('english_resume')}>{action === 'english_resume' && <LoaderCircle size={14} className="spin" />}{pack.english_html ? '重新生成英文简历' : '单独生成英文简历'}</button></div>
      <p>根据当前保存的简历生成英文版本。</p>
      {pack.english_html && englishStale && <p role="status">简历已修改，请重新生成英文简历后使用。</p>}
      {pack.english_html && !englishStale && <div className="supplement-downloads">{(['english_html', 'english_pdf', 'english_image'] as const).map((kind, index) => <a className="workspace-secondary" key={kind} href={`/api/delivery/packages/${pack.id}/${kind}`} target="_blank" rel="noreferrer"><ArrowDownToLine size={14} />{['可编辑 HTML', '英文 PDF', '预览图'][index]}</a>)}</div>}
    </section>
    <section className="workspace-card">
      <div className="card-heading"><h2>自我描述</h2><button disabled={disabled} className="workspace-secondary" onClick={() => onGenerate('self_description')}>{action === 'self_description' && <LoaderCircle size={14} className="spin" />}{pack.self_description ? '重新生成自我描述' : '单独生成自我描述'}</button></div>
      <p>结合当前 JD 和简历，生成可填写官网申请表的自我描述。</p>
      {pack.self_description && descriptionStale && <p role="status">简历已修改，请重新生成自我描述后使用。</p>}
      {pack.self_description && <details><summary>查看自我描述（{pack.self_description.length} 字符）</summary><textarea aria-label="自我描述正文" readOnly value={pack.self_description} rows={7} /><div className="supplement-downloads"><button disabled={descriptionStale} onClick={() => void copy()}><Copy size={14} />{copied ? '已复制' : '复制自我描述'}</button>{!descriptionStale && <a href={`/api/delivery/packages/${pack.id}/self_description_file`} download>下载自我描述</a>}</div></details>}
    </section>
  </div>;
}
