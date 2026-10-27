import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/** Joins class names; later Tailwind utilities override conflicting earlier ones. */
export function cn(...classes: ClassValue[]): string {
  return twMerge(clsx(classes));
}
