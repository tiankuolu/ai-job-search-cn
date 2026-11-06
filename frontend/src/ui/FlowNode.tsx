import type { ReactNode } from 'react';

export type UiState = 'default' | 'hover' | 'focus' | 'active' | 'loading' | 'empty' | 'error';

type Props = {
  title: ReactNode;
  meta?: ReactNode;
  status?: string;
  state?: UiState;
  disabled?: boolean;
  selected?: boolean;
  onClick?: () => void;
  ariaLabel?: string;
};

export default function FlowNode({ title, meta, status = 'pending', state = 'default', disabled, selected, onClick, ariaLabel }: Props) {
  const className = `ui-flow-node${state === 'default' ? '' : ` is-${state}`}${selected ? ' is-selected' : ''}`;
  return <button type="button" className={className} data-state={state} data-status={status} aria-label={ariaLabel} aria-disabled={disabled || undefined} disabled={disabled} onClick={onClick}>
    <span className="ui-flow-node__title">{title}</span>
    {meta && <span className="ui-flow-node__meta">{meta}</span>}
  </button>;
}
