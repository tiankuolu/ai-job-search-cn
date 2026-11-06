import { Workflow, type LucideIcon } from 'lucide-react';

type Props = { title: string; text: string; icon?: LucideIcon };

export default function Empty({ title, text, icon: Icon = Workflow }: Props) {
  return <div className="empty">
    <span className="empty-icon"><Icon size={27} strokeWidth={1.4} /></span>
    <h3>{title}</h3>
    <p>{text}</p>
  </div>;
}
