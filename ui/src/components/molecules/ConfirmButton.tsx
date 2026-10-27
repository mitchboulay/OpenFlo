import { useEffect, useState } from 'react';
import { Button, type ButtonVariant } from '@/components/atoms/Button';

/** How long the armed state lasts before it resets on its own. */
export const CONFIRM_WINDOW_MS = 5000;

export interface ConfirmButtonProps {
  /** Resting label, e.g. "Dispense now…". */
  label: string;
  /** Label once armed, e.g. "Tap again to dispense". */
  armedLabel: string;
  /** Fired by the second click within the confirm window. */
  onConfirm: () => void;
  /** Defaults to `danger`. */
  variant?: ButtonVariant;
  disabled?: boolean;
  className?: string;
}

/**
 * Two-step button: the first click arms it and swaps the label; a second click
 * within 5 s fires `onConfirm`. Otherwise it resets after 5 s.
 */
export function ConfirmButton({
  label,
  armedLabel,
  onConfirm,
  variant = 'danger',
  disabled = false,
  className,
}: ConfirmButtonProps) {
  const [armed, setArmed] = useState(false);

  useEffect(() => {
    if (!armed) return undefined;
    const timer = window.setTimeout(() => setArmed(false), CONFIRM_WINDOW_MS);
    return () => window.clearTimeout(timer);
  }, [armed]);

  const isArmed = armed && !disabled;

  const handleClick = () => {
    if (isArmed) {
      setArmed(false);
      onConfirm();
    } else {
      setArmed(true);
    }
  };

  return (
    <>
      <Button variant={variant} disabled={disabled} onClick={handleClick} className={className}>
        {isArmed ? armedLabel : label}
      </Button>
      <span className="sr-only" aria-live="polite">
        {isArmed ? armedLabel : ''}
      </span>
    </>
  );
}
