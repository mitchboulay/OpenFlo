import { useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { Icon } from '@/components/atoms/Icon';
import { IconButton } from '@/components/atoms/IconButton';
import { StatusDot } from '@/components/atoms/StatusDot';
import type { HomeSummary } from '@/api/types';
import { cn } from '@/lib/cn';
import type { Tone } from '@/types/tone';
import { HomeSheet } from './HomeSheet';

export interface HomeListProps {
  homes: readonly HomeSummary[];
}

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? '' : 's'}`;
}

function homeStatus(home: HomeSummary): { tone: Tone; label: string } {
  if (home.summary === 'empty') return { tone: 'neutral', label: 'No devices yet' };
  if (home.summary === 'attention') {
    return { tone: 'warn', label: `${home.attention_count} ${home.attention_count === 1 ? 'needs' : 'need'} attention` };
  }
  return { tone: 'ok', label: 'All good' };
}

/** The Homes screen card: every home with its status, plus "Add home" (FR-1). */
export function HomeList({ homes }: HomeListProps) {
  const [search, setSearch] = useSearchParams();
  // Setup's "Add a home" lands on `/?add=home` (signed in by setup; a URL, so it also survives the 401 → sign-in
  // fallback): open the sheet.
  const addHome = search.get('add') === 'home';
  const [editing, setEditing] = useState<HomeSummary | null | undefined>(addHome ? null : undefined);
  const close = () => {
    setEditing(undefined);
    if (addHome) setSearch({}, { replace: true });
  };
  const devices = homes.reduce((sum, home) => sum + home.device_count, 0);

  return (
    <section className="flex flex-col gap-6 rounded-[28px] border border-card-border bg-surface px-4 pt-8 pb-5 shadow-card sm:px-6">
      <div className="flex flex-col items-center gap-3.5 text-center">
        <span className="flex size-16 items-center justify-center rounded-[18px] border border-border bg-surface text-accent-text shadow-raise">
          <Icon name="drop" size={28} strokeWidth={1.8} />
        </span>
        <div className="flex flex-col gap-1.5">
          <h1 className="m-0 text-[28px] font-bold tracking-tight">OpenFLO</h1>
          <p className="m-0 text-dim">{homes.length ? `${plural(homes.length, 'home')} · ${plural(devices, 'device')}` : 'No homes yet.'}</p>
        </div>
      </div>
      <ul className="m-0 flex list-none flex-col gap-3 p-0">
        {homes.map((home) => {
          const status = homeStatus(home);
          return (
            <li key={home.id} className="flex items-center rounded-[18px] border border-border bg-surface hover:border-accent-border">
              <Link to={`/homes/${home.id}`} className="flex min-w-0 flex-1 items-center gap-3.5 py-4 pl-4 text-fg no-underline">
                <span
                  className={cn(
                    'flex size-11 flex-none items-center justify-center rounded-control text-on-accent',
                    status.tone === 'warn' ? 'bg-warn' : 'bg-[image:var(--tileGrad)]',
                  )}
                >
                  <Icon name="home" />
                </span>
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="text-base font-semibold">{home.name}</span>
                  <span className="flex flex-wrap items-center gap-x-1.5 text-sm text-dim">
                    <StatusDot tone={status.tone} label={status.label} />
                    <span aria-hidden="true">·</span>
                    <span>
                      {plural(home.device_count, 'device')} · {home.timezone.replaceAll('_', ' ')}
                    </span>
                  </span>
                </span>
              </Link>
              <IconButton label={`Edit ${home.name}`} className="mr-1.5 text-faint" onClick={() => setEditing(home)}>
                <Icon name="edit" size={16} strokeWidth={1.8} />
              </IconButton>
            </li>
          );
        })}
      </ul>
      <button
        type="button"
        onClick={() => setEditing(null)}
        className="flex cursor-pointer items-center gap-3.5 rounded-[18px] border border-dashed border-border2 bg-transparent p-4 text-left text-fg hover:border-accent-border hover:bg-accent-soft"
      >
        <span className="flex size-11 flex-none items-center justify-center rounded-control bg-surface2 text-dim">
          <Icon name="plus" />
        </span>
        <span className="flex flex-col gap-0.5">
          <span className="text-base font-semibold">Add home</span>
          <span className="text-sm text-dim">A cabin, a rental, a place you look after</span>
        </span>
      </button>
      <HomeSheet open={editing !== undefined} home={editing ?? null} onClose={close} />
    </section>
  );
}
