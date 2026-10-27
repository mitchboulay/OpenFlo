import { cloneElement, useId, type ReactElement } from 'react';

export interface FieldProps {
  /** Visible label; also the control's accessible name. */
  label: string;
  /** Helper text under the control. */
  hint?: string;
  /** Validation or API error; marks the control invalid and is announced. */
  error?: string | null;
  /** One `Input` or `Select`. It receives `id`, `aria-describedby` and `aria-invalid`. */
  children: ReactElement<{ id?: string; 'aria-describedby'?: string; 'aria-invalid'?: boolean }>;
}

/** Label + control + hint/error, wired for screen readers. */
export function Field({ label, hint, error, children }: FieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint && hintId, error && errorId].filter(Boolean).join(' ') || undefined;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[13px] font-semibold text-dim">
        {label}
      </label>
      {cloneElement(children, { id, 'aria-describedby': describedBy, 'aria-invalid': Boolean(error) })}
      {hint && (
        <p id={hintId} className="m-0 text-sm text-dim">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" className="m-0 text-sm font-medium text-bad">
          {error}
        </p>
      )}
    </div>
  );
}
