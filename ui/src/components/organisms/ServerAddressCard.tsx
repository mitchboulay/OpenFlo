import { useId, useState } from 'react';
import { Button } from '@/components/atoms/Button';
import { Notice } from '@/components/atoms/Notice';
import { StatusDot } from '@/components/atoms/StatusDot';
import { CheckList } from '@/components/molecules/CheckList';
import { ListRow } from '@/components/molecules/ListRow';
import { SectionCard } from '@/components/molecules/SectionCard';
import { Sheet } from '@/components/templates/Sheet';
import { useAddressCheck, useRunAddressCheck } from '@/hooks/useServer';
import { checkRows, checkSummary, checkVerdict, pendingRows, type CheckVerdict } from '@/lib/addressCheck';
import { formatRelative } from '@/lib/time';
import type { Tone } from '@/types/tone';
import { ServerAddressForm } from './ServerAddressForm';

export interface ServerAddressCardProps {
  address: string | null;
}

const VERDICT_TONES: Record<CheckVerdict, Tone> = { ok: 'ok', warn: 'warn', fail: 'bad' };

/** Settings → Server address (FR-16): the address, its last check, re-check and Change. */
export function ServerAddressCard({ address }: ServerAddressCardProps) {
  const formId = useId();
  const listId = useId();
  const check = useAddressCheck();
  const run = useRunAddressCheck();
  const [changing, setChanging] = useState(false);
  const [open, setOpen] = useState(false);

  // A stored check of an earlier address says nothing about this one.
  const result = check.data && check.data.address === address ? check.data : null;
  const verdict = result && checkVerdict(result);
  const summary = result && verdict && (
    <StatusDot tone={VERDICT_TONES[verdict]} label={`Checked ${formatRelative(result.at)} · ${checkSummary(result)}`} />
  );
  const showList = run.isPending || (verdict !== null && (verdict !== 'ok' || open));

  return (
    <SectionCard title="Server address" icon="globe">
      <ul className="m-0 list-none p-0">
        <ListRow
          variant="history"
          title={<span className="font-mono text-[13.5px] [overflow-wrap:anywhere]">{address ?? 'Not set'}</span>}
          value={
            <Button variant="ghost" onClick={() => setChanging(true)}>
              Change
            </Button>
          }
        />
      </ul>
      {run.isPending ? (
        <StatusDot tone="neutral" label="Checking…" />
      ) : verdict === 'ok' ? (
        <button type="button" aria-expanded={open} aria-controls={listId} onClick={() => setOpen(!open)} className="flex min-h-11 cursor-pointer items-center text-left text-sm">
          {summary}
        </button>
      ) : (
        <span className="text-sm">{summary ?? <StatusDot tone="neutral" label="Not checked yet" />}</span>
      )}
      {run.isError && (
        <Notice tone="bad" role="alert">
          Couldn’t run the check. Check again.
        </Notice>
      )}
      {showList && address && (
        <div id={listId}>
          <CheckList label="Address check" rows={result && !run.isPending ? checkRows(result) : pendingRows(address, 'checking')} />
        </div>
      )}
      <div>
        <Button disabled={run.isPending || !address} onClick={() => run.mutate()}>
          Check again
        </Button>
      </div>
      <Sheet
        open={changing}
        onClose={() => setChanging(false)}
        title="Server address"
        footer={
          <Button type="submit" form={formId} variant="primary">
            Save and check
          </Button>
        }
      >
        {changing && (
          <ServerAddressForm
            formId={formId}
            initial={address}
            onSaved={() => {
              setChanging(false);
              run.mutate();
            }}
          />
        )}
      </Sheet>
    </SectionCard>
  );
}
