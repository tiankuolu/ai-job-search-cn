import type { ReactNode } from 'react';

export type UiState = 'default' | 'hover' | 'focus' | 'active' | 'loading' | 'empty' | 'error';

type Props = {
  seq: number;
  title: ReactNode;
  detail?: ReactNode;
  time?: ReactNode;
  state?: UiState;
  disabled?: boolean;
  onClick?: () => void;
};

export default function EventRow({ seq, title, detail, time, state = 'default', disabled, onClick }: Props) {
  const className = `ui-event-row${state === 'default' ? '' : ` is-${state}`}`;
  const content = <>
    <span className="ui-event-row__seq">{String(seq).padStart(2, '0')}</span>
    <span>
      <span className="ui-event-row__title">{title}</span>
      {detail && <span className="ui-event-row__detail">{detail}</span>}
    </span>
    {time && <span className="ui-event-row__time">{time}</span>}
  </>;
  if (!onClick) return <div className={className} data-state={state}>{content}</div>;
  return <button type="button" className={className} data-state={state} aria-disabled={disabled || undefined} disabled={disabled} onClick={onClick}>{content}</button>;
}
