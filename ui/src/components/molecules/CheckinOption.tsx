import { LevelBars } from '@/components/atoms/LevelBars';
import { cn } from '@/lib/cn';

export interface CheckinOptionProps {
  name: string;
  /** Plain-words trade-off, e.g. "Checks in hourly. Uses more battery." */
  line: string;
  /** Battery use, 1 (lowest) to 4 (very high). */
  cost: 1 | 2 | 3 | 4;
  /** Spoken cost, e.g. "Higher battery use". */
  costLabel: string;
  selected: boolean;
  recommended?: boolean;
  onSelect: () => void;
  disabled?: boolean;
}

const BAR_TONE: Record<CheckinOptionProps['cost'], string> = { 1: 'bg-fg', 2: 'bg-fg', 3: 'bg-warn', 4: 'bg-bad' };

/** A radio row for a check-in preset, with battery-use bars. Use inside `role="radiogroup"`. */
export function CheckinOption({ name, line, cost, costLabel, selected, recommended = false, onSelect, disabled = false }: CheckinOptionProps) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      disabled={disabled}
      onClick={onSelect}
      className={cn(
        'flex w-full cursor-pointer items-center gap-3 rounded-button border px-3.5 py-3 text-left',
        'disabled:cursor-not-allowed disabled:opacity-50',
        selected ? 'border-accent-border bg-accent-soft' : 'border-border hover:border-border2',
      )}
    >
      <span
        aria-hidden="true"
        className={cn('flex size-5 flex-none items-center justify-center rounded-full border-2', selected ? 'border-accent' : 'border-border2')}
      >
        {selected && <span className="size-2.5 rounded-full bg-accent" />}
      </span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="flex flex-wrap items-center gap-2 font-semibold">
          {name}
          {recommended && (
            <span className="rounded-full bg-accent-soft px-2 py-px text-[11.5px] font-semibold text-accent-text">Recommended</span>
          )}
        </span>
        <span className="text-[13.5px] text-dim">{line}</span>
        <span className="sr-only">{costLabel}</span>
      </span>
      <LevelBars level={cost} fillClassName={BAR_TONE[cost]} />
    </button>
  );
}
