import { Button } from '@/components/atoms/Button';
import { Notice } from '@/components/atoms/Notice';
import { Sheet } from '@/components/templates/Sheet';
import { api } from '@/api/endpoints';
import type { DeviceDetail, RuleCreate } from '@/api/types';
import { useDeviceAction } from '@/hooks/useDevice';
import { useUnits } from '@/hooks/useUnits';
import { errorMessage } from '@/lib/errors';
import { DEFAULT_RULE, ruleLabel } from '@/lib/schedule';
import { formatVolume } from '@/lib/units';

export interface ScheduleIntroSheetProps {
  open: boolean;
  device: DeviceDetail;
  /** The device's rules; with none, turning on adds the gentle default (Sunday 9:00 AM). */
  rules: readonly RuleCreate[];
  timeZone: string;
  onClose: () => void;
}

/**
 * The deliberate confirm before the device dispenses on its own ("Safe by default"): what will run and when,
 * then one button that turns schedules on.
 */
export function ScheduleIntroSheet({ open, device, rules, timeZone, onClose }: ScheduleIntroSheetProps) {
  const { unit } = useUnits();
  const shown = rules.length > 0 ? rules : [DEFAULT_RULE];
  const turnOn = useDeviceAction(device.device_id, () =>
    Promise.all([
      api.updateControls(device.device_id, { schedules_enabled: true }),
      rules.length === 0 ? api.createRule(device.device_id, DEFAULT_RULE) : null,
    ]),
  );

  return (
    <Sheet open={open} onClose={onClose} title="Turn on schedules">
      <div className="flex flex-col gap-4">
        <p className="m-0 text-[17px] font-medium text-pretty">Your iFLO will dispense on its own at these times.</p>
        <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
          {shown.map((rule, index) => (
            <li key={index} className="rounded-control bg-surface2 px-3.5 py-3 font-medium">
              {ruleLabel(rule, timeZone)}
            </li>
          ))}
        </ul>
        <p className="m-0 text-sm text-pretty text-dim">
          {device.dosing.dose_ml !== null && `Each dose is ${formatVolume(device.dosing.dose_ml, unit)}. `}
          You can change times anytime. They reach the device at its next check-in.
        </p>
        {turnOn.isError && <Notice tone="bad" role="alert">{errorMessage(turnOn.error)}</Notice>}
        <div className="flex flex-col gap-1.5">
          <Button variant="primary" className="min-h-[50px]" disabled={turnOn.isPending} onClick={() => turnOn.mutate(undefined, { onSuccess: onClose })}>
            Turn on schedules
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Not now
          </Button>
        </div>
      </div>
    </Sheet>
  );
}
