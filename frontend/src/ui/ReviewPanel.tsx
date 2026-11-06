import type { ReactNode } from 'react';

export type UiState = 'default' | 'hover' | 'focus' | 'active' | 'loading' | 'empty' | 'error';

export type ReviewItem = {
  id: string;
  text: ReactNode;
  checked: boolean;
  error?: boolean;
};

type Props = {
  title?: ReactNode;
  items: ReviewItem[];
  onToggle?: (id: string, checked: boolean) => void;
  onRevise?: () => void;
  state?: UiState;
  disabled?: boolean;
  emptyText?: string;
  reviseLabel?: string;
};

export default function ReviewPanel({ title = '审查意见', items, onToggle, onRevise, state = 'default', disabled, emptyText = '还没有审查意见。', reviseLabel = '按勾选意见重写' }: Props) {
  const content = state === 'empty' || !items.length ? 'empty' : state;
  return <section className={`ui-review${state === 'default' ? '' : ` is-${state}`}`} data-state={content} aria-busy={state === 'loading' || undefined}>
    <div className="ui-review__head">
      <span className="ui-review__title">{title}</span>
      {onRevise && <button type="button" className="ui-review__revise" disabled={disabled || !items.some(item => item.checked)} onClick={onRevise}>{reviseLabel}</button>}
    </div>
    {content === 'empty' ? <p>{emptyText}</p> : items.map(item => <label className={`ui-review__item${item.error ? ' is-error' : ''}`} key={item.id} aria-disabled={disabled || undefined}>
      <input type="checkbox" checked={item.checked} disabled={disabled} onChange={event => onToggle?.(item.id, event.target.checked)} />
      <span>{item.text}</span>
    </label>)}
  </section>;
}
