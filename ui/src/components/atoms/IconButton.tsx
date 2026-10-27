import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

export interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'aria-label'> {
  /** Accessible name. Required: the button shows only an icon. */
  label: string;
}

/** A 44×44 icon-only button. The icon (children) is decorative; `label` names it. */
export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { label, type = 'button', className, children, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      aria-label={label}
      className={cn(
        'flex size-11 flex-none cursor-pointer items-center justify-center rounded-control text-dim',
        'hover:bg-surface2 hover:text-fg disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...rest}
    >
      <span aria-hidden="true" className="flex">
        {children}
      </span>
    </button>
  );
});
