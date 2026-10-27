import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

export interface ListRowProps {
  /** Main text: an info label ("Firmware") or a history title ("Dispensed a dose"). */
  title: ReactNode;
  /** Optional second line, e.g. "SE 8". */
  subtitle?: ReactNode;
  /** Right-aligned value or time. */
  value?: ReactNode;
  /** `info`: dim label, value in full text (Device info). `history`: bold title, dim value. */
  variant?: 'info' | 'history';
  /** Monospace value (serials, MACs, IPs). */
  mono?: boolean;
}

/**
 * A divided row of a card list. Serves both InfoRow and HistoryRow from the v2 mapping:
 * they differ only in which side carries the emphasis.
 */
export function ListRow({ title, subtitle, value, variant = 'info', mono = false }: ListRowProps) {
  const info = variant === 'info';
  return (
    <li className="flex items-center justify-between gap-3 border-b border-border py-2.5 text-sm last:border-b-0">
      <span className="min-w-0 flex-1">
        <span className={cn('block', info ? 'text-dim' : 'text-[14.5px] font-medium')}>{title}</span>
        {subtitle && <span className="block text-[13px] text-dim">{subtitle}</span>}
      </span>
      {value !== undefined && (
        <span
          className={cn(
            'max-w-[60%] text-right [overflow-wrap:anywhere] tabular-nums',
            info ? 'text-fg' : 'text-dim',
            mono && 'font-mono text-[13px]',
          )}
        >
          {value}
        </span>
      )}
    </li>
  );
}
