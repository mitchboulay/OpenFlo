import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Icon } from '@/components/atoms/Icon';
import { Notice } from '@/components/atoms/Notice';
import { StatusDot } from '@/components/atoms/StatusDot';
import { Menu } from '@/components/molecules/Menu';
import { PendingRow } from '@/components/molecules/PendingRow';
import { StatusPill } from '@/components/molecules/StatusPill';
import { api } from '@/api/endpoints';
import type { DeviceDetail, PendingChange } from '@/api/types';
import { useDeviceAction } from '@/hooks/useDevice';
import { detailState, headline } from '@/lib/deviceStatus';
import { errorMessage } from '@/lib/errors';
import { moveNetworkPath } from '@/lib/provisioning';
import { formatWhen, zoneLabel } from '@/lib/time';
import { DeviceSheet } from './DeviceSheet';
import { DispensePanel } from './DispensePanel';
import { RetireSheet } from './RetireSheet';

export interface DeviceHeaderProps {
  device: DeviceDetail;
  timeZone: string;
  /** Called after the device is retired, e.g. to leave its page. */
  onRetired: () => void;
}

/** Names for the API's pending kinds (FR-14). */
export const PENDING_LABELS: Record<PendingChange['kind'], string> = {
  controls: 'Dispensing or check-in change',
  dose: 'Dose change',
  dispense: 'Dispense now',
  schedule: 'Schedule change',
  retire: 'Retire',
};

function syncLine(device: DeviceDetail, offline: boolean, timeZone: string): string {
  const zone = zoneLabel(timeZone);
  const last = device.last_sync ? `Last check-in ${formatWhen(device.last_sync, timeZone)}` : 'No check-in yet';
  const next = formatWhen(device.next_expected_sync, timeZone);
  if (!next) return last;
  return offline ? `${last} · missed since ${next}` : `${last} · next around ${next}${zone ? ` ${zone}` : ''}`;
}

/** The device's status header: headline, sync honesty, named pending changes, the wake hint and Dispense now. */
export function DeviceHeader({ device, timeZone, onRetired }: DeviceHeaderProps) {
  const [sheet, setSheet] = useState<'edit' | 'retire' | null>(null);
  const navigate = useNavigate();
  const state = detailState(device);
  const lock = useDeviceAction(device.device_id, (enabled: boolean) =>
    api.updateControls(device.device_id, { dispensing_enabled: enabled }),
  );
  const dispensing = device.controls.dispensing_enabled;
  const retired = device.status === 'retired';
  const hasPending = device.pending.length > 0;
  const movePath = moveNetworkPath(device);

  return (
    <section aria-label="Status" className="flex flex-col gap-4 rounded-sheet border border-card-border bg-surface p-5 shadow-card sm:p-[22px]">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <h1 className="m-0 text-[26px] font-bold tracking-tight [overflow-wrap:anywhere]">{device.name ?? device.device_id}</h1>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1.5">
            <span className="text-dim">{device.location || 'No location set'}</span>
            <StatusPill tone={state.tone} label={state.label} />
          </div>
        </div>
        {!retired && (
          <Menu
            label="Device actions"
            items={[
              { label: 'Edit name and location', onSelect: () => setSheet('edit') },
              dispensing
                ? { label: 'Pause dispensing', onSelect: () => lock.mutate(false) }
                : { label: 'Resume dispensing', onSelect: () => lock.mutate(true) },
              ...(movePath ? [{ label: 'Move to a new network…', onSelect: () => navigate(movePath) }] : []),
              { label: 'Retire device…', tone: 'danger', onSelect: () => setSheet('retire') },
            ]}
          />
        )}
      </div>
      <p className="m-0 text-lg font-medium tracking-[-0.01em] text-pretty">{headline(device, state.condition, timeZone)}</p>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-dim">
        <span className="flex items-center gap-2">
          <Icon name="clock" size={16} strokeWidth={1.8} />
          {syncLine(device, state.condition === 'offline', timeZone)}
        </span>
        {!retired && <StatusDot tone={dispensing ? 'ok' : 'neutral'} label={`Dispensing · ${dispensing ? 'On' : 'Paused'}`} />}
      </div>
      {lock.isError && <Notice tone="bad" role="alert">{errorMessage(lock.error)}</Notice>}
      {hasPending && (
        <ul aria-label="Waiting for device" className="m-0 list-none overflow-hidden rounded-button border border-border p-0">
          {device.pending.map((change) => (
            <PendingRow key={change.kind} label={PENDING_LABELS[change.kind]} expectedAt={device.next_expected_sync} timeZone={timeZone} />
          ))}
        </ul>
      )}
      {!retired && (
        <div className="flex items-center gap-3 rounded-button bg-surface2 px-3.5 py-3 text-sm text-pretty text-dim">
          <Icon name="refresh" className="text-dim" strokeWidth={1.8} />
          <p className="m-0">
            Changes apply at the next check-in. To {hasPending ? 'apply now' : 'make it check in now'}, twist the bottle or press the
            device’s button.
          </p>
        </div>
      )}
      {!retired && <DispensePanel device={device} timeZone={timeZone} />}
      <DeviceSheet open={sheet === 'edit'} device={device} onClose={() => setSheet(null)} />
      <RetireSheet
        open={sheet === 'retire'}
        device={device}
        timeZone={timeZone}
        onClose={() => setSheet(null)}
        onRetired={onRetired}
      />
    </section>
  );
}
