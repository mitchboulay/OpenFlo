import { useState, type FormEvent } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/atoms/Button';
import { Input } from '@/components/atoms/Input';
import { Notice } from '@/components/atoms/Notice';
import { Field } from '@/components/molecules/Field';
import { Sheet } from '@/components/templates/Sheet';
import { api } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { DeviceDetail, Profile } from '@/api/types';
import { useDeviceAction } from '@/hooks/useDevice';
import { dosingBody, liquidChange } from '@/hooks/useDosing';
import { useUnits } from '@/hooks/useUnits';
import { errorMessage } from '@/lib/errors';
import { fromDisplay, toDisplay, UNIT_LABEL } from '@/lib/units';

export interface NewLiquidSheetProps {
  open: boolean;
  device: DeviceDetail;
  /** The liquids already offered; the standard one seeds the defaults. */
  profiles: readonly Profile[];
  onClose: () => void;
}

const MAX_NAME = 40;

function positive(text: string): number | null {
  const value = Number(text.replace(',', '.'));
  return Number.isFinite(value) && value > 0 ? value : null;
}

/** Adds a home liquid and switches this device to it. Calibrating it afterwards makes the volumes exact. */
export function NewLiquidSheet({ open, device, profiles, onClose }: NewLiquidSheetProps) {
  return (
    <Sheet open={open} onClose={onClose} title="New liquid">
      {open && <NewLiquidForm device={device} profiles={profiles} onDone={onClose} />}
    </Sheet>
  );
}

function NewLiquidForm({ device, profiles, onDone }: { device: DeviceDetail; profiles: readonly Profile[]; onDone: () => void }) {
  const { unit } = useUnits();
  // Until it is calibrated, a new liquid is assumed to flow like the standard cartridge.
  const base = profiles.find((profile) => profile.system && profile.slug === 'standard') ?? device.dosing.profile;
  const [name, setName] = useState('');
  const [capacity, setCapacity] = useState(String(toDisplay(base.capacity_ml, unit)));
  const [dose, setDose] = useState(String(toDisplay(base.default_dose_ml, unit)));
  const queryClient = useQueryClient();
  const create = useDeviceAction(device.device_id, async (body: { name: string; capacityMl: number; doseMl: number }) => {
    if (device.home_id === null) throw new Error('This device is not in a home.');
    const profile = await api.createProfile(device.home_id, {
      name: body.name,
      capacity_ml: body.capacityMl,
      default_dose_ml: body.doseMl,
      flow_full_ml_s: base.flow_full_ml_s,
    });
    await queryClient.invalidateQueries({ queryKey: queryKeys.profiles(device.home_id) });
    return api.setDosing(device.device_id, dosingBody(device.dosing, liquidChange(device.dosing, profile)));
  });
  const capacityMl = positive(capacity);
  const doseMl = positive(dose);
  const valid = name.trim() !== '' && capacityMl !== null && doseMl !== null;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!valid) return;
    create.mutate(
      { name: name.trim(), capacityMl: Math.round(fromDisplay(capacityMl, unit)), doseMl: Math.round(fromDisplay(doseMl, unit)) },
      { onSuccess: onDone },
    );
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <Field label="Name">
        <Input value={name} onChange={(event) => setName(event.target.value)} maxLength={MAX_NAME} placeholder="Enzyme cleaner" autoComplete="off" required />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label={`Bottle size (${UNIT_LABEL[unit]})`}>
          <Input inputMode="decimal" value={capacity} onChange={(event) => setCapacity(event.target.value)} />
        </Field>
        <Field label={`Usual dose (${UNIT_LABEL[unit]})`}>
          <Input inputMode="decimal" value={dose} onChange={(event) => setDose(event.target.value)} />
        </Field>
      </div>
      <p className="m-0 text-sm text-pretty text-dim">Every liquid flows a little differently. After adding it, calibrate once so doses are accurate.</p>
      {create.isError && <Notice tone="bad" role="alert">{errorMessage(create.error)}</Notice>}
      <Button type="submit" variant="primary" disabled={!valid || create.isPending}>
        Add liquid
      </Button>
    </form>
  );
}
