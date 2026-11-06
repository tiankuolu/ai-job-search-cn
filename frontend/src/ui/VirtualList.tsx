import { useEffect, useRef, useState, type ReactNode } from 'react';

type Props<T> = {
  items: T[];
  height: number;
  itemHeight: number;
  renderItem: (item: T, index: number) => ReactNode;
  overscan?: number;
  ariaLabel?: string;
  empty?: ReactNode;
};

export default function VirtualList<T>({ items, height, itemHeight, renderItem, overscan = 4, ariaLabel, empty }: Props<T>) {
  const host = useRef<HTMLDivElement>(null);
  const [top, setTop] = useState(0);
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const update = () => setTop(element.scrollTop);
    element.addEventListener('scroll', update, { passive: true });
    update();
    return () => element.removeEventListener('scroll', update);
  }, []);
  if (!items.length) return <div className="ui-virtual" style={{ height }} role="list" aria-label={ariaLabel}>{empty}</div>;
  const start = Math.max(0, Math.floor(top / itemHeight) - overscan);
  const end = Math.min(items.length, Math.ceil((top + height) / itemHeight) + overscan);
  return <div className="ui-virtual" ref={host} style={{ height }} role="list" aria-label={ariaLabel}>
    <div className="ui-virtual__inner" style={{ height: items.length * itemHeight }}>
      <div className="ui-virtual__window" style={{ transform: `translateY(${start * itemHeight}px)` }}>
        {items.slice(start, end).map((item, offset) => <div key={start + offset} style={{ height: itemHeight }} role="listitem">{renderItem(item, start + offset)}</div>)}
      </div>
    </div>
  </div>;
}
