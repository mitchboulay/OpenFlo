import { Icon } from '@/components/atoms/Icon';
import { cn } from '@/lib/cn';

export interface StepperProps {
  /** Number shown, already in display units (e.g. "177" or "6.0"). */
  value: string;
  /** Unit after the number, e.g. "mL". */
  unit: string;
  /** What the number is, for screen readers, e.g. "Dose". */
  label: string;
  onDecrement: () => void;
  onIncrement: () => void;
  /** Disables − at the lower bound. */
  atMin?: boolean;
  /** Disables + at the upper bound. */
  atMax?: boolean;
  disabled?: boolean;
  /** `lg` (68 px number) for the dose, `md` (52 px) in sheets. Defaults to `lg`. */
  size?: 'md' | 'lg';
}

const ROUND_BUTTON =
  'flex size-14 flex-none cursor-pointer items-center justify-center rounded-full border border-border bg-surface ' +
  'active:scale-95 disabled:cursor-not-allowed disabled:opacity-35';

/** A big number with − / + buttons. The caller owns the bounds and the step. */
export function Stepper({
  value,
  unit,
  label,
  onDecrement,
  onIncrement,
  atMin = false,
  atMax = false,
  disabled = false,
  size = 'lg',
}: StepperProps) {
  return (
    <div className="flex w-full items-center justify-center gap-4">
      <button type="button" aria-label={`Less ${label.toLowerCase()}`} className={ROUND_BUTTON} disabled={disabled || atMin} onClick={onDecrement}>
        <Icon name="minus" size={22} strokeWidth={2.2} />
      </button>
      <output aria-live="polite" aria-label={label} className="flex min-w-0 items-baseline justify-center gap-1.5">
        <span
          className={cn(
            'leading-none font-semibold tracking-[-0.045em] tabular-nums',
            size === 'lg' ? 'text-[56px] sm:text-[68px]' : 'text-[52px]',
          )}
        >
          {value}
        </span>
        <span className="text-[22px] font-medium text-dim">{unit}</span>
      </output>
      <button type="button" aria-label={`More ${label.toLowerCase()}`} className={ROUND_BUTTON} disabled={disabled || atMax} onClick={onIncrement}>
        <Icon name="plus" size={22} strokeWidth={2.2} />
      </button>
    </div>
  );
}
