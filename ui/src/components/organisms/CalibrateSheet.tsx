import { useState, type FormEvent } from 'react';
import { Button } from '@/components/atoms/Button';
import { Input } from '@/components/atoms/Input';
import { Notice } from '@/components/atoms/Notice';
import { Field } from '@/components/molecules/Field';
import { StepDots } from '@/components/molecules/StepDots';
import { Sheet } from '@/components/templates/Sheet';
import { api } from '@/api/endpoints';
import type { DeviceDetail, Dosing } from '@/api/types';
import { useDeviceAction } from '@/hooks/useDevice';
import { useUnits } from '@/hooks/useUnits';
import { errorCode, errorMessage } from '@/lib/errors';
import { formatFlow, formatVolume, fromDisplay, UNIT_LABEL } from '@/lib/units';

export interface CalibrateSheetProps {
  open: boolean;
  device: DeviceDetail;
  onClose: () => void;
}

const STEPS = [
  {
    title: 'Put a measuring cup under the outlet',
    body: 'Unclip the outlet tube from the drain line and hold it over a measuring cup.',
  },
  {
    title: 'Dispense one dose',
    body: 'Press the button on the device once. When it next checks in, it reports the dose, and we compare it with what came out.',
  },
  { title: 'Enter how much came out', body: 'Read the cup at eye level. Close is fine.' },
] as const;

/** Three steps into a cup, then the API's new flow (FR-7). The result is the one place besides Advanced that shows seconds. */
export function CalibrateSheet({ open, device, onClose }: CalibrateSheetProps) {
  return (
    <Sheet open={open} onClose={onClose} title={`Calibrate ${device.dosing.profile.name}`}>
      {open && <CalibrateSteps device={device} onDone={onClose} />}
    </Sheet>
  );
}

function CalibrateSteps({ device, onDone }: { device: DeviceDetail; onDone: () => void }) {
  const { unit } = useUnits();
  const [step, setStep] = useState(1);
  const [measured, setMeasured] = useState('');
  const [result, setResult] = useState<Dosing | null>(null);
  const calibrate = useDeviceAction(device.device_id, (measuredMl: number) => api.calibrate(device.device_id, measuredMl));
  const value = Number(measured.replace(',', '.'));
  const valid = Number.isFinite(value) && value > 0;

  if (result) {
    return (
      <div className="flex flex-col gap-4">
        <Notice tone="ok" role="status">
          Calibrated. {result.profile.name} measures {formatFlow(result.flow_ml_s, unit)}.
        </Notice>
        <p className="m-0 text-pretty">
          {result.dose_ml === null
            ? `The valve opens for ${result.computed_seconds.toFixed(1)} s per dose.`
            : `For ${formatVolume(result.dose_ml, unit)}, the valve now opens for ${result.computed_seconds.toFixed(1)} s.`}
        </p>
        <Button variant="primary" onClick={onDone}>
          Done
        </Button>
      </div>
    );
  }

  const current = STEPS[step - 1] ?? STEPS[0];
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (step < STEPS.length) return setStep(step + 1);
    if (valid) calibrate.mutate(fromDisplay(value, unit), { onSuccess: setResult });
  };
  const noDose = errorCode(calibrate.error) === 'NO_RECENT_DISPENSE';

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <StepDots current={step} total={STEPS.length} />
      <div className="flex flex-col gap-1.5">
        <p className="m-0 text-[22px] leading-tight font-semibold tracking-tight">{current.title}</p>
        <p className="m-0 text-pretty text-dim">{current.body}</p>
      </div>
      {step === STEPS.length && (
        <Field label={`Measured (${UNIT_LABEL[unit]})`}>
          <Input inputMode="decimal" autoComplete="off" placeholder="0" value={measured} onChange={(event) => setMeasured(event.target.value)} />
        </Field>
      )}
      {noDose && (
        <Notice tone="warn" role="alert">
          We haven’t seen a dose from this device since its dosing last changed. Run one dose into the cup first: press the
          device’s button once, then twist the bottle so it checks in and reports it. Then enter the amount again.
        </Notice>
      )}
      {calibrate.isError && !noDose && <Notice tone="bad" role="alert">{errorMessage(calibrate.error)}</Notice>}
      <div className="flex gap-2">
        {step > 1 && (
          <Button onClick={() => setStep(step - 1)} className="min-h-[50px]">
            Back
          </Button>
        )}
        <Button type="submit" variant="primary" className="min-h-[50px] flex-1" disabled={(step === STEPS.length && !valid) || calibrate.isPending}>
          {step === 1 ? 'Next' : step === 2 ? 'It dispensed' : 'Save calibration'}
        </Button>
      </div>
    </form>
  );
}
