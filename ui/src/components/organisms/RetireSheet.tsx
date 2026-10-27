import { Button } from '@/components/atoms/Button';
import { Notice } from '@/components/atoms/Notice';
import { ConfirmButton } from '@/components/molecules/ConfirmButton';
import { Sheet } from '@/components/templates/Sheet';
import { api } from '@/api/endpoints';
import type { DeviceDetail } from '@/api/types';
import { useDeviceAction } from '@/hooks/useDevice';
import { errorMessage } from '@/lib/errors';
import { formatClockTime } from '@/lib/time';

export interface RetireSheetProps {
  open: boolean;
  device: DeviceDetail;
  timeZone: string;
  onClose: () => void;
  /** Called once the API reports the device retired (200). */
  onRetired: () => void;
}

/**
 * Two-phase retire (FR-2): the server pauses schedules and retires the device once it has fetched an
 * empty schedule. While that is pending the sheet says so, and offers "Retire anyway" with its warning.
 */
export function RetireSheet({ open, device, timeZone, onClose, onRetired }: RetireSheetProps) {
  const retire = useDeviceAction(device.device_id, (force: boolean) => api.retire(device.device_id, force));
  const pending = device.retire_requested_at !== null && device.status !== 'retired';
  const next = formatClockTime(device.next_expected_sync, timeZone, true);

  const run = (force: boolean) =>
    retire.mutate(force, {
      onSuccess: (result) => {
        if (result.status === 'retired') onRetired();
      },
    });

  return (
    <Sheet open={open} onClose={onClose} title={`Retire ${device.name ?? 'device'}`}>
      <div className="flex flex-col gap-4">
        {pending ? (
          <>
            <p className="m-0 text-pretty">
              Waiting for the device to clear its schedule. It finishes retiring after its next check-in
              {next ? `, around ${next}` : ''}.
            </p>
            <Notice tone="warn">
              If it never checks in again, you can retire it anyway. It may keep dispensing on its own schedule until its
              bottle is removed.
            </Notice>
            <ConfirmButton label="Retire anyway" armedLabel="Tap again to retire anyway" disabled={retire.isPending} onConfirm={() => run(true)} />
          </>
        ) : (
          <>
            <p className="m-0 text-pretty">
              Retiring stops its schedules and removes it from this home. Its history is kept. To use it again you’ll set it up
              from the start.
            </p>
            <ConfirmButton label="Retire device" armedLabel="Tap again to retire" disabled={retire.isPending} onConfirm={() => run(false)} />
          </>
        )}
        {retire.isError && <Notice tone="bad" role="alert">{errorMessage(retire.error)}</Notice>}
        <Button variant="ghost" onClick={onClose}>
          {pending ? 'Close' : 'Keep it'}
        </Button>
      </div>
    </Sheet>
  );
}
