import { forwardRef, type InputHTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

/** Shared with `Select` so both controls look the same. */
export const CONTROL_CLASSES =
  'h-13 w-full min-w-0 rounded-button border border-border2 bg-surface2 px-4 text-[17px] text-fg ' +
  'placeholder:text-faint disabled:opacity-50 aria-[invalid=true]:border-bad';

/** Text-like input. Pass the right `type` and `inputMode` (e.g. `decimal` for volumes). */
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...rest },
  ref,
) {
  return <input ref={ref} className={cn(CONTROL_CLASSES, className)} {...rest} />;
});
