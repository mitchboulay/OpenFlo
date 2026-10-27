import { Badge } from '@/components/atoms/Badge';
import { cn } from '@/lib/cn';
import type { Tone } from '@/types/tone';

export interface StatusPillProps {
  tone: Tone;
  /** Always-visible status text, e.g. "Needs attention". */
  label: string;
}

const DOT: Record<Tone, string> = { ok: 'bg-ok', warn: 'bg-warn', bad: 'border-2 border-bad', neutral: 'bg-faint' };

/** A device's status as a tinted pill with a dot. Offline draws a hollow dot, so it reads without color too. */
export function StatusPill({ tone, label }: StatusPillProps) {
  return (
    <Badge tone={tone} className="font-semibold whitespace-nowrap" icon={<span className={cn('size-2 rounded-full', DOT[tone])} />}>
      {label}
    </Badge>
  );
}
