import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Visual weight. One `primary` per view. Defaults to `secondary`. */
  variant?: ButtonVariant;
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-on-accent hover:brightness-110',
  secondary: 'border border-border bg-surface text-fg hover:bg-surface2',
  ghost: 'bg-transparent text-accent-text hover:bg-surface2',
  danger: 'bg-bad-soft text-bad hover:brightness-95',
};

/** The button look, for a router `Link` that navigates but should read as a button. */
export function buttonClassName(variant: ButtonVariant = 'secondary', className?: string): string {
  return cn(
    'inline-flex min-h-11 min-w-11 cursor-pointer items-center justify-center gap-2 whitespace-nowrap',
    'rounded-button px-4 font-semibold no-underline transition-[filter,background-color]',
    'disabled:cursor-not-allowed disabled:opacity-50',
    VARIANT_CLASSES[variant],
    className,
  );
}

/** Text button with a 44 px minimum touch target. Defaults to `type="button"`. */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'secondary', type = 'button', className, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={buttonClassName(variant, className)}
      {...rest}
    />
  );
});
