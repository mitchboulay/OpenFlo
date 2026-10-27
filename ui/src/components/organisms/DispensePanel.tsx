import { useState } from 'react';
import { Button } from '@/components/atoms/Button';
import { Notice } from '@/components/atoms/Notice';
import { DispenseTracker, type DispenseStage } from '@/components/molecules/DispenseTracker';
import { api } from '@/api/endpoints';
import type { DeviceDetail } from '@/api/types';
import { useDeviceAction } from '@/hooks/useDevice';
import { useUnits } from '@/hooks/useUnits';
import { errorMessage } from '@/lib/errors';
import { formatClockTime, formatWhen } from '@/lib/time';
import { formatVolume } from '@/lib/units';

export interface DispensePanelProps {
  device: DeviceDetail;
  timeZone: string;
}

/** A delivered request stays on screen for a day (or until "Done"). */
const TRACK_RECENT_MS = 24 * 60 * 60 * 1000;
const WAKE_HINT = 'To dispense sooner, twist the bottle or press the device’s button.';

interface Tracked {
  stage: DispenseStage;
  at: string | null;
}

function trackedStage(device: DeviceDetail, dismissedId: number | null, now: number): Tracked | null {
  const { pending, last_delivered: delivered } = device.remote_dispense;
  if (pending) return { stage: 'queued', at: null };
  if (!delivered?.delivered_at || delivered.id === dismissedId) return null;
  if (now - new Date(delivered.delivered_at).getTime() > TRACK_RECENT_MS) return null;
  return delivered.confirmed_at ? { stage: 'dispensed', at: delivered.confirmed_at } : { stage: 'sent', at: null };
}

function blockedReason(device: DeviceDetail): string | null {
  if (device.status !== 'active' || device.retire_requested_at) return 'Not available for a retired device.';
  if (device.flags.some((flag) => flag.acked_at === null)) return 'On hold until you review the device warning.';
  if (!device.controls.dispensing_enabled) return 'Dispensing is paused. Resume it from the menu to use this.';
  return null;
}

/**
 * "Dispense now…" (FR-6): a two-step confirm that says when it will happen, then the
 * queued · sent · dispensed tracker. Every stage comes from the API; nothing is assumed.
 */
export function DispensePanel({ device, timeZone }: DispensePanelProps) {
  const [confirming, setConfirming] = useState(false);
  const [dismissedId, setDismissedId] = useState<number | null>(null);
  const { unit } = useUnits();
  const queue = useDeviceAction(device.device_id, () => api.queueDispense(device.device_id));
  const cancel = useDeviceAction(device.device_id, () => api.cancelDispense(device.device_id));

  const dose = device.dosing.dose_ml === null ? 'one dose' : formatVolume(device.dosing.dose_ml, unit);
  const liquid = device.dosing.profile.slug === 'standard' ? 'cartridge liquid' : device.dosing.profile.name.toLowerCase();
  const nextClock = formatClockTime(device.next_expected_sync, timeZone, true);
  const tracked = trackedStage(device, dismissedId, Date.now());
  const blocked = blockedReason(device);

  const titles: Record<DispenseStage, string> = {
    queued: 'Queued for next check-in',
    sent: 'Sent to device',
    dispensed: `Dispensed ${dose}`,
  };
  const notes: Record<DispenseStage, string> = {
    queued: `Waiting for device${nextClock ? ` · ~${nextClock}` : ''}. ${WAKE_HINT}`,
    sent: 'Your iFLO has the request. It confirms the dose when it next reports its events.',
    dispensed: `Confirmed by the device · ${formatWhen(tracked?.at, timeZone) ?? ''}`,
  };
  const trackerAction =
    tracked?.stage === 'queued' ? (
      <Button variant="ghost" className="text-bad" disabled={cancel.isPending} onClick={() => cancel.mutate(undefined)}>
        Cancel request
      </Button>
    ) : tracked?.stage === 'dispensed' ? (
      <Button variant="ghost" onClick={() => setDismissedId(device.remote_dispense.last_delivered?.id ?? null)}>
        Done
      </Button>
    ) : undefined;

  return (
    <div className="flex flex-col gap-3">
      {tracked && <DispenseTracker stage={tracked.stage} title={titles[tracked.stage]} note={notes[tracked.stage]} action={trackerAction} />}
      {cancel.isError && <Notice tone="bad" role="alert">{errorMessage(cancel.error)}</Notice>}
      {tracked?.stage === 'queued' ? null : confirming && !blocked ? (
        <div className="flex flex-col gap-3 rounded-button border border-border2 bg-surface2 p-4">
          <p className="m-0 text-base font-semibold">
            Dispense {dose} of {liquid}?
          </p>
          <p className="m-0 text-sm text-pretty text-dim">
            Your iFLO is asleep, so it will dispense once when it next checks in{nextClock ? `, around ${nextClock}` : ''}. Make sure
            the drain line is connected.
          </p>
          {queue.isError && <Notice tone="bad" role="alert">{errorMessage(queue.error)}</Notice>}
          <div className="flex flex-wrap gap-2">
            <Button
              variant="primary"
              disabled={queue.isPending}
              onClick={() => queue.mutate(undefined, { onSuccess: () => setConfirming(false) })}
            >
              Yes, dispense
            </Button>
            <Button variant="ghost" className="text-fg" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <p className="m-0 min-w-0 flex-[1_1_12rem] text-sm text-dim">{blocked ?? `One dose of ${dose} at the next check-in.`}</p>
          <Button variant="primary" disabled={blocked !== null} onClick={() => setConfirming(true)}>
            Dispense now…
          </Button>
        </div>
      )}
    </div>
  );
}
