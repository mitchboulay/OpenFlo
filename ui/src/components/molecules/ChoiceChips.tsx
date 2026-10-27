import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

export interface ChoiceChip<T extends string | number> {
  value: T;
  label: string;
  /** Second line, e.g. "177 mL" under "Standard", or "Not calibrated yet". */
  detail?: string;
  /** Tints the detail in the warn tone. */
  detailTone?: 'dim' | 'warn';
}

export interface ChoiceChipsProps<T extends string | number> {
  /** Accessible name of the group, e.g. "Dose presets". */
  label: string;
  options: readonly ChoiceChip<T>[];
  /** The selected value, or null when none matches. */
  selected: T | null;
  onSelect: (value: T) => void;
  disabled?: boolean;
  /** Extra trailing chip-shaped control, e.g. "New liquid…". */
  trailing?: ReactNode;
  className?: string;
}

/** Wrapping row of pressable chips (liquids, dose presets, fill levels). One may be selected. */
export function ChoiceChips<T extends string | number>({
  label,
  options,
  selected,
  onSelect,
  disabled = false,
  trailing,
  className,
}: ChoiceChipsProps<T>) {
  return (
    <div role="group" aria-label={label} className={cn('flex flex-wrap gap-2', className)}>
      {options.map((option) => {
        const active = option.value === selected;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            disabled={disabled}
            onClick={() => onSelect(option.value)}
            className={cn(
              'flex min-h-11 cursor-pointer flex-col justify-center rounded-control border px-3.5 py-1.5 text-left',
              'disabled:cursor-not-allowed disabled:opacity-50',
              active ? 'border-accent-border bg-accent-soft' : 'border-border bg-surface hover:border-border2',
            )}
          >
            <span className="text-sm font-semibold">{option.label}</span>{' '}
            {option.detail && (
              <span className={cn('text-xs', option.detailTone === 'warn' ? 'text-warn' : 'text-dim')}>{option.detail}</span>
            )}
          </button>
        );
      })}
      {trailing}
    </div>
  );
}
