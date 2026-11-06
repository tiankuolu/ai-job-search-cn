import type { ReactNode } from 'react';

export type UiState = 'default' | 'hover' | 'focus' | 'active' | 'loading' | 'empty' | 'error';

type Props = {
  title: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  state?: UiState;
  disabled?: boolean;
  selected?: boolean;
  onClick?: () => void;
  ariaLabel?: string;
};

export default function TaskCard({ title, meta, actions, children, state = 'default', disabled, selected, onClick, ariaLabel }: Props) {
  const className = `ui-task-card${state === 'default' ? '' : ` is-${state}`}${selected ? ' is-selected' : ''}`;
  const content = <>
    <div className="ui-task-card__body">
      <div className="ui-task-card__title">{title}</div>
      {meta && <div className="ui-task-card__meta">{meta}</div>}
      {children}
    </div>
    {actions && <div className="ui-task-card__actions">{actions}</div>}
  </>;
  if (!onClick) return <div className={className} data-state={state}>{content}</div>;
  return <button type="button" className={className} data-state={state} aria-label={ariaLabel} aria-disabled={disabled || undefined} disabled={disabled} onClick={onClick}>{content}</button>;
}
