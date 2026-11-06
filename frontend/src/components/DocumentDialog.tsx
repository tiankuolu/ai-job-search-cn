import { useEffect, useRef } from 'react';
import { ArrowDownToLine, FileText, X } from 'lucide-react';
import type { Document } from '../types';
import Markdown from './Markdown';

type Props = { document: Document; onClose: () => void; onDownload: (document: Document) => void };

export default function DocumentDialog({ document, onClose, onDownload }: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const previousFocus = window.document.activeElement as HTMLElement | null;
    const dialog = dialogRef.current;
    dialog?.focus();
    function keyboard(event: KeyboardEvent) {
      if (event.key === 'Escape') closeRef.current();
      if (event.key === 'Tab' && dialog) {
        const controls = Array.from(dialog.querySelectorAll<HTMLElement>('button, a[href], select, input'));
        const first = controls[0], last = controls.at(-1);
        if (event.shiftKey && (window.document.activeElement === first || window.document.activeElement === dialog)) { event.preventDefault(); last?.focus(); }
        if (!event.shiftKey && window.document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    }
    window.document.addEventListener('keydown', keyboard);
    return () => { window.document.removeEventListener('keydown', keyboard); previousFocus?.focus(); };
  }, []);

  return <div className="document-overlay" role="dialog" aria-modal="true" aria-label={document.name} onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
    <div className="document-modal" ref={dialogRef} tabIndex={-1}>
      <header>
        <div><FileText size={19} /><strong>{document.name}</strong></div>
        <div>
          <button className="icon-button" aria-label="下载文档" onClick={() => onDownload(document)}><ArrowDownToLine size={18} /></button>
          <button className="icon-button" aria-label="关闭文档" onClick={onClose}><X size={20} /></button>
        </div>
      </header>
      <div className="document-scroll"><Markdown>{document.content}</Markdown></div>
    </div>
  </div>;
}
