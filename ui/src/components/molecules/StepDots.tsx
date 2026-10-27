import { cn } from '@/lib/cn';

export interface StepDotsProps {
  /** 1-based current step. */
  current: number;
  total: number;
}

/** Segmented progress for short guided flows, with a "Step 2 of 3" eyebrow. */
export function StepDots({ current, total }: StepDotsProps) {
  return (
    <div className="flex flex-col gap-3">
      <div aria-hidden="true" className="flex gap-1.5">
        {Array.from({ length: total }, (_, index) => (
          <span key={index} className={cn('h-1 flex-1 rounded-sm', index < current ? 'bg-accent' : 'bg-border2')} />
        ))}
      </div>
      <p className="m-0 text-[13px] font-semibold text-dim">
        Step {current} of {total}
      </p>
    </div>
  );
}
