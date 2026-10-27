import { Link } from 'react-router';
import { Badge } from '@/components/atoms/Badge';
import { PendingBadge } from '@/components/molecules/PendingBadge';
import type { DeviceSummary } from '@/api/types';
import { cn } from '@/lib/cn';
import { GUIDANCE, LOW_BATTERY_PERCENT, summaryState } from '@/lib/deviceStatus';
import { formatWhen } from '@/lib/time';
import { StatusPill } from '@/components/molecules/StatusPill';

export interface DeviceCardProps {
  device: DeviceSummary;
  timeZone: string;
}

const TEXT_TONE = { ok: 'text-fg', warn: 'text-warn', bad: 'text-bad', neutral: 'text-dim' } as const;

/** A device in a home's list: status, bottle, battery, and what happens next (FR-2). */
export function DeviceCard({ device, timeZone }: DeviceCardProps) {
  const state = summaryState(device);
  const guidance = GUIDANCE[device.bottle_guidance];
  const lowBattery = device.battery_level !== null && device.battery_level < LOW_BATTERY_PERCENT;
  const next =
    state.condition === 'offline'
      ? `Last seen ${formatWhen(device.last_seen, timeZone) ?? 'never'}`
      : device.next_dose_at
        ? `Next dose ${formatWhen(device.next_dose_at, timeZone)}`
        : device.next_expected_sync
          ? `Next check-in around ${formatWhen(device.next_expected_sync, timeZone)}`
          : 'Waiting for its first check-in';

  return (
    <Link
      to={`/devices/${encodeURIComponent(device.device_id)}`}
      className="flex flex-col gap-4 rounded-card border border-card-border bg-surface p-[18px] text-fg no-underline shadow-card transition-transform hover:-translate-y-px hover:border-accent-border"
    >
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="m-0 text-[17px] font-semibold tracking-[-0.01em]">{device.name ?? device.device_id}</h2>
          <p className="m-0 text-sm text-dim">{device.location || 'No location set'}</p>
        </div>
        <StatusPill tone={state.tone} label={state.label} />
      </div>
      <dl className="m-0 grid grid-cols-2 gap-3">
        <div>
          <dt className="text-xs text-dim">Bottle</dt>
          <dd className={cn('m-0 font-medium', TEXT_TONE[guidance.tone])}>{guidance.label}</dd>
        </div>
        <div>
          <dt className="text-xs text-dim">Battery</dt>
          <dd className={cn('m-0 font-medium', lowBattery ? 'text-warn' : 'text-fg')}>
            {device.battery_level === null ? '—' : `${device.battery_level}%${lowBattery ? ' · low' : ''}`}
          </dd>
        </div>
      </dl>
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3.5 text-sm">
        <span className="text-dim">{next}</span>
        {device.pending_count > 0 && <PendingBadge expectedAt={device.next_expected_sync} timeZone={timeZone} />}
        {device.flagged && <Badge tone="bad">Identity warning</Badge>}
      </div>
    </Link>
  );
}
