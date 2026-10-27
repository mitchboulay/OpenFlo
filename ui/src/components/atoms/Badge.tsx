import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';
import type { Tone } from '@/types/tone';

export type BadgeTone = Tone | 'accent';

export interface BadgeProps {
  /** Defaults to `neutral`. */
  tone?: BadgeTone;
  /** Optional leading icon; rendered decoratively. */
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
}

const TONE_CLASSES: Record<BadgeTone, string> = {
  ok: 'bg-ok-soft text-ok',
  warn: 'bg-warn-soft text-warn',
  bad: 'bg-bad-soft text-bad',
  neutral: 'bg-surface2 text-dim',
  accent: 'bg-accent-soft text-accent-text',
};

/** Small pill label, e.g. "Default" on a preset or a pending state. */
export function Badge({ tone = 'neutral', icon, children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[13px] font-medium',
        TONE_CLASSES[tone],
        className,
      )}
    >
      {icon && (
        <span aria-hidden="true" className="flex flex-none">
          {icon}
        </span>
      )}
      {children}
    </span>
  );
}
