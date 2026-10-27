import type { ReactNode } from 'react';
import { Link, NavLink } from 'react-router';
import { Icon } from '@/components/atoms/Icon';
import { cn } from '@/lib/cn';

export type ContentWidth = 'narrow' | 'wide';

export interface AppShellProps {
  /** Back link in the top bar, e.g. `{ to: '/', label: 'Homes' }`. */
  back?: { to: string; label: string };
  /** `narrow` (620 px) for lists, `wide` (1120 px) for detail pages. Defaults to `narrow`. */
  contentWidth?: ContentWidth;
  children: ReactNode;
}

const WIDTH_CLASSES: Record<ContentWidth, string> = {
  narrow: 'max-w-narrow',
  wide: 'max-w-wide',
};

/** Page frame: sticky translucent top bar, then the page content at its width. */
export function AppShell({ back, contentWidth = 'narrow', children }: AppShellProps) {
  const width = WIDTH_CLASSES[contentWidth];
  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-20 bg-bg/70 backdrop-blur-lg backdrop-saturate-150">
        <div className={cn('mx-auto flex h-14 items-center gap-2 px-4', width)}>
          {back && (
            <Link
              to={back.to}
              className="-ml-1.5 flex h-11 items-center gap-0.5 rounded-control pr-2.5 pl-1 font-medium whitespace-nowrap text-accent-text no-underline hover:bg-surface2"
            >
              <Icon name="back" size={22} />
              {back.label}
            </Link>
          )}
          <NavLink
            to="/settings"
            aria-label="Settings"
            className="-mr-1.5 ml-auto flex size-11 flex-none items-center justify-center rounded-control text-dim hover:bg-surface2 hover:text-fg aria-[current=page]:text-accent-text"
          >
            <Icon name="gear" size={22} strokeWidth={1.8} />
          </NavLink>
        </div>
      </header>
      <main className={cn('mx-auto flex flex-col gap-4 px-4 pt-3 pb-12', width)}>{children}</main>
    </div>
  );
}
