import { useState } from 'react';
import { Button } from '@/components/atoms/Button';
import { Notice } from '@/components/atoms/Notice';
import { BottleGauge } from '@/components/molecules/BottleGauge';
import { ChoiceChips } from '@/components/molecules/ChoiceChips';
import { Stepper } from '@/components/molecules/Stepper';
import { Sheet } from '@/components/templates/Sheet';
import { api } from '@/api/endpoints';
import type { DeviceDetail } from '@/api/types';
import { useDeviceAction } from '@/hooks/useDevice';
import { useUnits } from '@/hooks/useUnits';
import { errorMessage } from '@/lib/errors';
import { formatVolume, fromDisplay, toDisplay, UNIT_LABEL, type VolumeUnit } from '@/lib/units';

export interface LevelSheetProps {
  open: boolean;
  device: DeviceDetail;
  onClose: () => void;
}

const STEP: Record<VolumeUnit, number> = { ml: 25, oz: 1 };
const PICKS = [
  { value: 0, label: 'Empty' },
  { value: 0.25, label: '¼' },
  { value: 0.5, label: '½' },
  { value: 0.75, label: '¾' },
  { value: 1, label: 'Full' },
] as const;

/** "Roughly how much is in the bottle?" Sets the open bottle's level, or starts one at that level. */
export function LevelSheet({ open, device, onClose }: LevelSheetProps) {
  return (
    <Sheet open={open} onClose={onClose} title="Set bottle level">
      {open && <LevelForm device={device} onDone={onClose} />}
    </Sheet>
  );
}

function LevelForm({ device, onDone }: { device: DeviceDetail; onDone: () => void }) {
  const { unit } = useUnits();
  const capacity = device.bottle?.capacity_ml ?? device.dosing.profile.capacity_ml;
  const [ml, setMl] = useState(Math.round(device.bottle?.est_remaining_ml ?? capacity / 2));
  const save = useDeviceAction(device.device_id, (fillMl: number) =>
    device.bottle ? api.adjustFill(device.device_id, fillMl) : api.newBottle(device.device_id, fillMl),
  );
  const shown = toDisplay(ml, unit);
  const step = (direction: 1 | -1) => {
    const next = Math.round(fromDisplay(shown + direction * STEP[unit], unit));
    setMl(Math.min(Math.max(next, 0), capacity));
  };

  return (
    <div className="flex flex-col gap-4">
      <p className="m-0 text-sm text-dim">Roughly how much is in the bottle? A guess is fine.</p>
      <Stepper
        size="md"
        label="Bottle level"
        value={String(shown)}
        unit={UNIT_LABEL[unit]}
        atMin={ml <= 0}
        atMax={ml >= capacity}
        onDecrement={() => step(-1)}
        onIncrement={() => step(1)}
      />
      <BottleGauge fraction={ml / capacity} tone="neutral" label={`${formatVolume(ml, unit)} of ${formatVolume(capacity, unit)}`} className="h-3" />
      <ChoiceChips
        label="Quick levels"
        className="grid grid-cols-5"
        options={PICKS}
        selected={PICKS.find((pick) => Math.round(capacity * pick.value) === ml)?.value ?? null}
        onSelect={(fraction) => setMl(Math.round(capacity * fraction))}
      />
      {save.isError && <Notice tone="bad" role="alert">{errorMessage(save.error)}</Notice>}
      <Button variant="primary" className="min-h-[50px]" disabled={save.isPending} onClick={() => save.mutate(ml, { onSuccess: onDone })}>
        Save level
      </Button>
    </div>
  );
}
