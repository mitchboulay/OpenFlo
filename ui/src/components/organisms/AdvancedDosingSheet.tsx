import type { ReactNode } from 'react';
import { Notice } from '@/components/atoms/Notice';
import { Switch } from '@/components/atoms/Switch';
import { Stepper } from '@/components/molecules/Stepper';
import { Sheet } from '@/components/templates/Sheet';
import type { DeviceDetail } from '@/api/types';
import { useDebouncedCommit } from '@/hooks/useDebouncedCommit';
import { useSetDosing } from '@/hooks/useDosing';
import { errorMessage } from '@/lib/errors';

export interface AdvancedDosingSheetProps {
  open: boolean;
  device: DeviceDetail;
  onClose: () => void;
}

const MIN_SECONDS = 1;
const MAX_SECONDS = 30;
const SECONDS_STEP = 0.5;

function SettingRow({ title, body, control }: { title: string; body: string; control: ReactNode }) {
  return (
    <div className="flex items-start gap-3.5">
      <div className="min-w-0 flex-1">
        <p className="m-0 font-medium">{title}</p>
        <p className="m-0 text-sm text-dim">{body}</p>
      </div>
      {control}
    </div>
  );
}

/** Fixed seconds, bottle-level compensation, and the API's computed valve time (FR-7 Advanced). */
export function AdvancedDosingSheet({ open, device, onClose }: AdvancedDosingSheetProps) {
  const dosing = device.dosing;
  const setDosing = useSetDosing(device.device_id, dosing);
  const [draft, setDraft] = useDebouncedCommit<number>((fixedSeconds, done) =>
    setDosing.mutate({ fixedSeconds }, { onSettled: done }),
  );
  const fixed = dosing.fixed_seconds !== null;
  const seconds = draft ?? dosing.fixed_seconds ?? dosing.computed_seconds;
  const step = (direction: 1 | -1) =>
    setDraft(Math.min(Math.max(Math.round((seconds + direction * SECONDS_STEP) * 2) / 2, MIN_SECONDS), MAX_SECONDS));

  return (
    <Sheet open={open} onClose={onClose} title="Advanced dosing">
      <div className="flex flex-col gap-5">
        <p className="m-0 rounded-button bg-surface2 px-4 py-3 text-center">
          Valve opens for <output className="font-semibold tabular-nums" data-testid="computed-seconds">{dosing.computed_seconds.toFixed(1)}</output> s per
          dose
        </p>
        <SettingRow
          title="Use a fixed time instead of volume"
          body="The valve opens for the same number of seconds every time."
          control={
            <Switch
              label="Use a fixed time"
              checked={fixed}
              disabled={setDosing.isPending}
              onChange={(next) =>
                setDosing.mutate(next ? { fixedSeconds: dosing.computed_seconds } : { doseMl: dosing.presets.standard_ml })
              }
            />
          }
        />
        {fixed && (
          <Stepper
            size="md"
            label="Fixed time"
            value={seconds.toFixed(1)}
            unit="s"
            atMin={seconds <= MIN_SECONDS}
            atMax={seconds >= MAX_SECONDS}
            onDecrement={() => step(-1)}
            onIncrement={() => step(1)}
          />
        )}
        <SettingRow
          title="Adjust for bottle level"
          body={
            fixed
              ? 'Not used with a fixed time.'
              : 'Flow slows as the bottle empties, so the valve stays open a little longer.'
          }
          control={
            <Switch
              label="Adjust for bottle level"
              checked={dosing.compensation_enabled}
              disabled={fixed || setDosing.isPending}
              onChange={(next) => setDosing.mutate({ compensation: next })}
            />
          }
        />
        {setDosing.isError && <Notice tone="bad" role="alert">{errorMessage(setDosing.error)}</Notice>}
      </div>
    </Sheet>
  );
}
