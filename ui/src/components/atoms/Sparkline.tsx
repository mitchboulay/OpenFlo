import { cn } from '@/lib/cn';

export interface SparklineProps {
  /** Values in order, oldest first. Needs at least two to draw. */
  values: readonly number[];
  /** Accessible description, e.g. "Battery over the last 30 days, 98% to 82%". */
  label: string;
  /** `bad` draws in the bad tone; otherwise ok. */
  tone?: 'ok' | 'bad';
  className?: string;
}

const WIDTH = 300;
const HEIGHT = 64;
const PAD = 3;

/** Inline SVG trend line with a soft area fill. Scales to its container's width. */
export function Sparkline({ values, label, tone = 'ok', className }: SparklineProps) {
  if (values.length < 2) return null;
  const low = Math.min(...values) - PAD;
  const high = Math.max(...values) + PAD;
  const points = values.map((value, index) => {
    const x = (index / (values.length - 1)) * WIDTH;
    const y = HEIGHT - 2 - ((value - low) / (high - low)) * (HEIGHT - 4);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const line = points.join(' ');
  return (
    <svg
      role="img"
      aria-label={label}
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      preserveAspectRatio="none"
      className={cn('block h-16 w-full', tone === 'bad' ? 'text-bad' : 'text-ok', className)}
    >
      <polygon points={`0,${HEIGHT} ${line} ${WIDTH},${HEIGHT}`} fill="currentColor" opacity="0.12" />
      <polyline
        points={line}
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
