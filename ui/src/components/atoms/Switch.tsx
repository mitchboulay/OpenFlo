import { cn } from '@/lib/cn';

export interface SwitchProps {
  /** Current state (controlled). */
  checked: boolean;
  /** Called with the requested next state. */
  onChange: (next: boolean) => void;
  /** Accessible name, e.g. "Dispensing". Required: the switch has no visible text. */
  label: string;
  disabled?: boolean;
  id?: string;
  className?: string;
}

/**
 * On/off switch (`role="switch"`). A native button, so Space and Enter toggle it.
 * The 51×31 track sits inside a 44 px tall hit area.
 */
export function Switch({ checked, onChange, label, disabled = false, id, className }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      id={id}
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'inline-flex min-h-11 min-w-11 flex-none cursor-pointer items-center justify-center rounded-full',
        'disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          'flex h-[31px] w-[51px] items-center rounded-full p-0.5 transition-colors duration-200',
          checked ? 'bg-accent' : 'bg-border2',
        )}
      >
        <span
          className={cn(
            'size-[27px] rounded-full bg-on-accent shadow-raise transition-transform duration-200',
            checked && 'translate-x-5',
          )}
        />
      </span>
    </button>
  );
}
