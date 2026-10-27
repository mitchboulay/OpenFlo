import { cn } from '@/lib/cn';
import type { Tone } from '@/types/tone';

export interface StatusDotProps {
  tone: Tone;
  /** Visible text. Status is never conveyed by color alone. */
  label: string;
  className?: string;
}

const TEXT_CLASSES: Record<Tone, string> = {
  ok: 'text-ok',
  warn: 'text-warn',
  bad: 'text-bad',
  neutral: 'text-dim',
};

const DOT_CLASSES: Record<Tone, string> = {
  ok: 'bg-ok',
  warn: 'bg-warn',
  bad: 'bg-bad',
  neutral: 'bg-faint',
};

/** A colored dot with its always-visible text label, e.g. "● Online". */
export function StatusDot({ tone, label, className }: StatusDotProps) {
  return (
    <span className={cn('inline-flex items-center gap-1.5 font-medium', TEXT_CLASSES[tone], className)}>
      <span aria-hidden="true" className={cn('size-[7px] flex-none rounded-full', DOT_CLASSES[tone])} />
      {label}
    </span>
  );
}
