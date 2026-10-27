import { Button } from '@/components/atoms/Button';
import { Icon } from '@/components/atoms/Icon';
import { Notice } from '@/components/atoms/Notice';
import { api } from '@/api/endpoints';
import type { Flag } from '@/api/types';
import { useDeviceAction } from '@/hooks/useDevice';
import { errorMessage } from '@/lib/errors';
import { formatWhen } from '@/lib/time';

export interface IdentityFlagCardProps {
  deviceId: string;
  flag: Flag;
  timeZone: string;
}

function describe(flag: Flag): { title: string; facts: string[] } {
  if (flag.kind === 'ip_conflict') {
    return {
      title: 'We saw this device check in from two places at once.',
      facts: (flag.detail.source_ips ?? []).map((ip) => `Checked in from ${ip}`),
    };
  }
  const changes = flag.detail.changes.length
    ? flag.detail.changes
    : flag.detail.field
      ? [{ field: flag.detail.field, old: flag.detail.old, new: flag.detail.new }]
      : [];
  return {
    title: 'This device reported different hardware details than before.',
    facts: changes.map((change) => `${change.field}: ${change.old ?? '—'} → ${change.new ?? '—'}`),
  };
}

/**
 * An unacknowledged identity flag (FR-13). Device IDs can be guessed, so remote dispensing and schedules
 * stay on hold until the owner confirms. Careful, not alarming.
 */
export function IdentityFlagCard({ deviceId, flag, timeZone }: IdentityFlagCardProps) {
  const ack = useDeviceAction(deviceId, () => api.ackFlag(flag.id));
  const { title, facts } = describe(flag);
  return (
    <section aria-label="Device warning" className="flex flex-col gap-3 rounded-card border border-card-border bg-warn-soft p-5">
      <h2 className="m-0 flex items-start gap-2.5 text-base font-semibold">
        <Icon name="warning" className="mt-0.5 text-warn" />
        {title}
      </h2>
      <ul className="m-0 flex list-none flex-col gap-1 p-0 text-sm">
        {facts.map((fact) => (
          <li key={fact} className="font-mono text-[13px] [overflow-wrap:anywhere]">
            {fact}
          </li>
        ))}
        <li className="text-dim">Noticed {formatWhen(flag.raised_at, timeZone)}</li>
      </ul>
      <p className="m-0 text-sm text-pretty">
        Remote dispensing and schedules are paused until you confirm. If you moved it or changed its network, it’s fine.
      </p>
      {ack.isError && <Notice tone="bad" role="alert">{errorMessage(ack.error)}</Notice>}
      <div>
        <Button variant="primary" disabled={ack.isPending} onClick={() => ack.mutate(undefined)}>
          It’s fine (I moved it)
        </Button>
      </div>
    </section>
  );
}
