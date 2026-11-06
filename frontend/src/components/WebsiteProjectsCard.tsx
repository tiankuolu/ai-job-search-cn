import { useState } from 'react';
import { ArrowDownToLine, Copy, LoaderCircle } from 'lucide-react';

export type WebsiteProjectText = { name: string; description: string; responsibilities: string };

type Props = {
  packageId: string;
  projects?: WebsiteProjectText[];
  stale: boolean;
  disabled: boolean;
  generating: boolean;
  onGenerate: () => void;
};

export default function WebsiteProjectsCard({ packageId, projects, stale, disabled, generating, onGenerate }: Props) {
  const [message, setMessage] = useState('');
  async function copy(text: string) {
    setMessage('');
    await navigator.clipboard.writeText(text);
    setMessage('已复制');
  }
  return <section className="workspace-card website-projects-card">
    <div className="card-heading"><h2>官网投递项目介绍</h2><button className="workspace-secondary" disabled={disabled} onClick={onGenerate}>
      {generating && <LoaderCircle className="spin" size={14} />}{projects?.length ? '根据当前简历重新生成' : '根据当前 JD 和简历生成'}
    </button></div>
    <p>分别复制项目描述和项目职责，填写招聘官网的项目经历。</p>
    {stale && <p role="status">简历已修改，请重新生成项目介绍后使用。</p>}
    <span role="status">{message}</span>
    {!!projects?.length && <details><summary>查看项目描述和项目职责（{projects.length} 个项目）</summary>{projects.map((project, index) => <article className="website-project" key={`${packageId}-${index}`}>
      <h3>{project.name}</h3>
      {(['description', 'responsibilities'] as const).map(field => {
        const label = field === 'description' ? '项目描述' : '项目职责';
        return <div className="website-project-field" key={field}>
          <div className="card-heading"><label htmlFor={`website-${packageId}-${index}-${field}`}>{label} · {project[field].length} 字符</label>
            <button disabled={stale} onClick={() => void copy(project[field])}><Copy size={14} />复制{label}</button></div>
          <textarea id={`website-${packageId}-${index}-${field}`} aria-label={`${project.name} ${label}`} readOnly value={project[field]} rows={6} />
        </div>;
      })}
    </article>)}</details>}
    {!!projects?.length && !stale && <a className="workspace-secondary" href={`/api/delivery/packages/${packageId}/website_projects_file`} download><ArrowDownToLine size={14} />下载项目介绍</a>}
  </section>;
}
