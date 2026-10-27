import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';
import type { Tone } from '@/types/tone';

export interface NoticeProps {
  /** Background tone; the text stays full-contrast. Defaults to `neutral`. */
  tone?: Tone;
  /** `alert` announces errors; `status` announces results. Omit for static copy. */
  role?: 'alert' | 'status';
  children: ReactNode;
  className?: string;
}

const TONE_CLASSES: Record<Tone, string> = {
  ok: 'bg-ok-soft',
  warn: 'bg-warn-soft',
  bad: 'bg-bad-soft',
  neutral: 'bg-surface2 text-dim',
};

/** A short message block: limits, warnings, API errors, empty states. */
export function Notice({ tone = 'neutral', role, children, className }: NoticeProps) {
  return (
    <div role={role} className={cn('rounded-control px-3.5 py-2.5 text-sm text-pretty text-fg', TONE_CLASSES[tone], className)}>
      {children}
    </div>
  );
}
