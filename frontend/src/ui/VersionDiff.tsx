export type UiState = 'default' | 'hover' | 'focus' | 'active' | 'loading' | 'empty' | 'error';

type Props = {
  before: string;
  after: string;
  title?: string;
  beforeLabel?: string;
  afterLabel?: string;
  state?: UiState;
};

type Line = { type: 'same' | 'add' | 'remove'; text: string };

function diffLines(before: string, after: string): Line[] {
  const left = before.split('\n');
  const right = after.split('\n');
  if (left.length * right.length > 250000) {
    return [
      ...left.map(text => ({ type: 'remove' as const, text })),
      ...right.map(text => ({ type: 'add' as const, text })),
    ];
  }
  const table = Array.from({ length: left.length + 1 }, () => new Uint16Array(right.length + 1));
  for (let i = left.length - 1; i >= 0; i -= 1) {
    for (let j = right.length - 1; j >= 0; j -= 1) {
      table[i][j] = left[i] === right[j] ? table[i + 1][j + 1] + 1 : Math.max(table[i + 1][j], table[i][j + 1]);
    }
  }
  const result: Line[] = [];
  let i = 0;
  let j = 0;
  while (i < left.length && j < right.length) {
    if (left[i] === right[j]) {
      result.push({ type: 'same', text: left[i] });
      i += 1;
      j += 1;
    } else if (table[i + 1][j] >= table[i][j + 1]) {
      result.push({ type: 'remove', text: left[i] });
      i += 1;
    } else {
      result.push({ type: 'add', text: right[j] });
      j += 1;
    }
  }
  while (i < left.length) result.push({ type: 'remove', text: left[i++] });
  while (j < right.length) result.push({ type: 'add', text: right[j++] });
  return result;
}

export default function VersionDiff({ before, after, title = '版本差异', beforeLabel = '上一版', afterLabel = '当前版', state = 'default' }: Props) {
  const content = state === 'empty' ? 'empty' : state === 'loading' ? 'loading' : state === 'error' ? 'error' : before === after ? 'empty' : 'default';
  const lines = content === 'default' ? diffLines(before, after).slice(0, 400) : [];
  return <section className={`ui-diff${state === 'default' ? '' : ` is-${state}`}`} data-state={content} aria-label={title}>
    <div className="ui-diff__head"><span>{title}</span><span>{beforeLabel} → {afterLabel}</span></div>
    {content === 'empty' && <p style={{ padding: '12px 14px' }}>两个版本没有差异。</p>}
    {content === 'loading' && <p style={{ padding: '12px 14px' }}>正在比较版本。</p>}
    {content === 'error' && <p style={{ padding: '12px 14px' }}>版本比较失败，请重新打开。</p>}
    {content === 'default' && lines.map((line, index) => <div className={`ui-diff__line is-${line.type}`} key={`${index}-${line.type}`}><span>{line.type === 'add' ? '+' : line.type === 'remove' ? '-' : ' '}</span><span>{line.text || ' '}</span></div>)}
  </section>;
}
