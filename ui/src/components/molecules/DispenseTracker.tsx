import type { ReactNode } from 'react';
import { Icon } from '@/components/atoms/Icon';
import { cn } from '@/lib/cn';

export type DispenseStage = 'queued' | 'sent' | 'dispensed';

const STAGES: readonly { stage: DispenseStage; label: string }[] = [
  { stage: 'queued', label: 'Queued' },
  { stage: 'sent', label: 'Sent' },
  { stage: 'dispensed', label: 'Dispensed' },
];

export interface DispenseTrackerProps {
  stage: DispenseStage;
  /** Line under the bars, e.g. "Waiting for device · ~4:42 PM. To dispense sooner, twist the bottle…". */
  note: string;
  /** Title over the bars, e.g. "Queued for next check-in". */
  title: string;
  /** Trailing action, e.g. "Cancel request" while queued or "Done" once dispensed. */
  action?: ReactNode;
}

/** Queued · Sent · Dispensed progress for one remote dispense. */
export function DispenseTracker({ stage, note, title, action }: DispenseTrackerProps) {
  const current = STAGES.findIndex((item) => item.stage === stage);
  return (
    <div className="flex flex-col gap-3.5 rounded-button border border-border bg-surface2 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="m-0 font-semibold" aria-live="polite">
          {title}
        </p>
        {action}
      </div>
      <ol className="m-0 grid list-none grid-cols-3 gap-2 p-0">
        {STAGES.map((item, index) => {
          const done = index <= current;
          return (
            <li key={item.stage} aria-current={index === current ? 'step' : undefined} className="flex flex-col gap-1.5">
              <span
                aria-hidden="true"
                className={cn('h-1 rounded-sm', done ? (item.stage === 'dispensed' ? 'bg-ok' : 'bg-accent') : 'bg-border2')}
              />
              <span className={cn('flex items-center gap-1 text-[13px]', done ? 'text-fg' : 'text-dim', index === current ? 'font-semibold' : 'font-medium')}>
                {done && <Icon name="check" size={13} strokeWidth={2.6} />}
                {item.label}
                <span className="sr-only">{done ? ' (done)' : ' (not yet)'}</span>
              </span>
            </li>
          );
        })}
      </ol>
      <p className="m-0 text-sm text-pretty text-dim">{note}</p>
    </div>
  );
}
