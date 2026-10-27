import { cn } from '@/lib/cn';
import { WEEKDAYS } from '@/lib/schedule';

export interface DayPickerProps {
  /** Selected weekdays as the API's `days_mask` (bit 0 = Monday). */
  mask: number;
  onChange: (mask: number) => void;
  /** Accessible name of the group. Defaults to "Days". */
  label?: string;
}

/** Seven toggle chips, Sunday first. Each shows a letter and is named by its full day. */
export function DayPicker({ mask, onChange, label = 'Days' }: DayPickerProps) {
  return (
    <div role="group" aria-label={label} className="grid grid-cols-7 gap-1.5">
      {WEEKDAYS.map((day) => {
        const bit = 1 << day.bit;
        const on = (mask & bit) !== 0;
        return (
          <button
            key={day.bit}
            type="button"
            aria-pressed={on}
            aria-label={day.name}
            onClick={() => onChange(mask ^ bit)}
            className={cn(
              'min-h-11 cursor-pointer rounded-control font-semibold',
              on ? 'bg-accent text-on-accent' : 'border border-border bg-surface2 text-fg hover:border-border2',
            )}
          >
            {day.short[0]}
          </button>
        );
      })}
    </div>
  );
}
