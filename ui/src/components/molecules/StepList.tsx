import { Icon } from '@/components/atoms/Icon';
import { cn } from '@/lib/cn';

export type StepState = 'done' | 'active' | 'pending';

export interface StepListItem {
  label: string;
  state: StepState;
}

export interface StepListProps {
  /** Accessible name of the list, e.g. "Setup progress". */
  label: string;
  steps: readonly StepListItem[];
}

const STATE_TEXT: Record<StepState, string> = { done: 'Done', active: 'Now', pending: 'Not yet' };

/** Live progress rows: a check when done, a pulse on the current step, always with a text state. */
export function StepList({ label, steps }: StepListProps) {
  return (
    <ol aria-label={label} className="m-0 flex list-none flex-col overflow-hidden rounded-[18px] border border-border bg-surface p-0">
      {steps.map((step) => (
        <li
          key={step.label}
          aria-current={step.state === 'active' ? 'step' : undefined}
          className="flex items-center gap-3.5 border-t border-border px-[18px] py-4 first:border-t-0"
        >
          <span
            aria-hidden="true"
            className={cn(
              'flex size-[26px] flex-none items-center justify-center rounded-full',
              step.state === 'done' && 'bg-ok text-surface',
              step.state === 'active' && 'border-2 border-accent-text',
              step.state === 'pending' && 'border-2 border-border2',
            )}
          >
            {step.state === 'done' && <Icon name="check" size={14} strokeWidth={3} />}
            {step.state === 'active' && <span className="size-2 animate-pulse rounded-full bg-accent-text" />}
          </span>
          <span className={cn('flex-1', step.state === 'active' ? 'font-semibold' : 'font-medium', step.state === 'pending' && 'text-dim')}>
            {step.label}
          </span>
          <span className={cn('text-[13px] text-dim', step.state === 'pending' && 'sr-only')}>{STATE_TEXT[step.state]}</span>
        </li>
      ))}
    </ol>
  );
}
