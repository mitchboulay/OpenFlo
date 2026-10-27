import { forwardRef, type SelectHTMLAttributes } from 'react';
import { cn } from '@/lib/cn';
import { CONTROL_CLASSES } from './Input';

/** Native select (keyboard and screen-reader behavior for free), styled like `Input`. */
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select(
  { className, ...rest },
  ref,
) {
  return <select ref={ref} className={cn(CONTROL_CLASSES, 'px-3 text-base', className)} {...rest} />;
});
