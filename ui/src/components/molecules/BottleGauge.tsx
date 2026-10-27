import { cn } from '@/lib/cn';
import type { Tone } from '@/types/tone';

export interface BottleGaugeProps {
  /** Fill from 0 to 1, or null when the level is unknown (empty track). */
  fraction: number | null;
  /** Dose marks as fractions of the bottle (0..1), so "≈ 3 doses" is visible. */
  ticks?: readonly number[];
  tone: Tone;
  /** Spoken summary, e.g. "Bottle about half full". */
  label: string;
  className?: string;
}

const FILL: Record<Tone, string> = { ok: 'bg-ok', warn: 'bg-warn', bad: 'bg-bad', neutral: 'bg-faint' };

/** Horizontal bottle level with dose ticks. Display only: fractions come from API values. */
export function BottleGauge({ fraction, ticks = [], tone, label, className }: BottleGaugeProps) {
  const percent = fraction === null ? 0 : Math.round(Math.min(Math.max(fraction, 0), 1) * 100);
  return (
    <div
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={fraction === null ? undefined : percent}
      aria-valuetext={label}
      className={cn('relative h-7 overflow-hidden rounded-[9px] border border-border bg-surface2', className)}
    >
      <div className={cn('absolute inset-y-0 left-0 opacity-85 transition-[width] duration-300', FILL[tone])} style={{ width: `${percent}%` }} />
      {ticks
        .filter((tick) => tick > 0 && tick < 1)
        .map((tick) => (
          <div key={tick} className="absolute inset-y-0 w-0.5 bg-surface" style={{ left: `${tick * 100}%` }} />
        ))}
    </div>
  );
}
