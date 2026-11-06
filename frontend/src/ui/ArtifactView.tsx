import type { ReactNode } from 'react';

export type UiState = 'default' | 'hover' | 'focus' | 'active' | 'loading' | 'empty' | 'error';

type Props = {
  title: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  state?: UiState;
  emptyText?: string;
};

export default function ArtifactView({ title, meta, actions, children, state = 'default', emptyText = '产物还没有生成。' }: Props) {
  return <section className={`ui-artifact${state === 'default' ? '' : ` is-${state}`}`} data-state={state} aria-busy={state === 'loading' || undefined}>
    <header className="ui-artifact__head">
      <div>
        <div className="ui-artifact__title">{title}</div>
        {meta && <div className="ui-artifact__meta">{meta}</div>}
      </div>
      {actions && <div className="ui-artifact__actions">{actions}</div>}
    </header>
    <div className="ui-artifact__body">{state === 'empty' ? <p>{emptyText}</p> : children}</div>
  </section>;
}
