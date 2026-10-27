import { useState, type FormEvent } from 'react';
import { Button } from '@/components/atoms/Button';
import { Input } from '@/components/atoms/Input';
import { Notice } from '@/components/atoms/Notice';
import { Select } from '@/components/atoms/Select';
import { ConfirmButton } from '@/components/molecules/ConfirmButton';
import { Field } from '@/components/molecules/Field';
import { Sheet } from '@/components/templates/Sheet';
import type { HomeSummary } from '@/api/types';
import { useDeleteHome, useSaveHome } from '@/hooks/useHomes';
import { errorMessage } from '@/lib/errors';

export interface HomeSheetProps {
  open: boolean;
  /** The home to edit, or null to add one. */
  home: HomeSummary | null;
  onClose: () => void;
}

const MAX_NAME = 60;

function timeZones(current: string): string[] {
  const zones = Intl.supportedValuesOf('timeZone');
  return zones.includes(current) ? zones : [current, ...zones];
}

/** Add or edit a home: name and time zone (FR-1). Delete lives here, behind the API's device check. */
export function HomeSheet({ open, home, onClose }: HomeSheetProps) {
  return (
    <Sheet open={open} onClose={onClose} title={home ? 'Edit home' : 'Add home'}>
      {open && <HomeForm key={home?.id ?? 'new'} home={home} onDone={onClose} />}
    </Sheet>
  );
}

function HomeForm({ home, onDone }: { home: HomeSummary | null; onDone: () => void }) {
  const [name, setName] = useState(home?.name ?? '');
  const [timezone, setTimezone] = useState(home?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone);
  const save = useSaveHome();
  const remove = useDeleteHome();
  const trimmed = name.trim();

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!trimmed) return;
    save.mutate({ homeId: home?.id ?? null, body: { name: trimmed, timezone } }, { onSuccess: onDone });
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <Field label="Name" error={save.isError ? errorMessage(save.error) : null}>
        <Input value={name} onChange={(event) => setName(event.target.value)} maxLength={MAX_NAME} placeholder="Main house" autoComplete="off" required />
      </Field>
      <Field label="Time zone" hint="Schedules and times for this home use this time zone.">
        <Select value={timezone} onChange={(event) => setTimezone(event.target.value)}>
          {timeZones(timezone).map((zone) => (
            <option key={zone} value={zone}>
              {zone.replaceAll('_', ' ')}
            </option>
          ))}
        </Select>
      </Field>
      <Button type="submit" variant="primary" disabled={!trimmed || save.isPending}>
        {home ? 'Save' : 'Add home'}
      </Button>
      {home && (
        <>
          <ConfirmButton
            label="Delete home"
            armedLabel="Tap again to delete"
            disabled={remove.isPending}
            onConfirm={() => remove.mutate(home.id, { onSuccess: onDone })}
          />
          {remove.isError && (
            <Notice tone="bad" role="alert">
              {errorMessage(remove.error)}
            </Notice>
          )}
        </>
      )}
    </form>
  );
}
