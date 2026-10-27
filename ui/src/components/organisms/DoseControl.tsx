import { Notice } from '@/components/atoms/Notice';
import { ChoiceChips } from '@/components/molecules/ChoiceChips';
import { Stepper } from '@/components/molecules/Stepper';
import { ApiError } from '@/api/client';
import type { DeviceDetail } from '@/api/types';
import { useDebouncedCommit } from '@/hooks/useDebouncedCommit';
import { useSetDosing } from '@/hooks/useDosing';
import { useUnits } from '@/hooks/useUnits';
import { errorCode, errorMessage } from '@/lib/errors';
import { formatVolume, formatVolumeRange, fromDisplay, otherUnit, toDisplay, UNIT_LABEL, VOLUME_STEP } from '@/lib/units';

export interface DoseControlProps {
  device: DeviceDetail;
}

type PresetKey = 'light' | 'standard' | 'strong';

function outOfRange(error: unknown): { min: number; max: number } | null {
  if (errorCode(error) !== 'DOSE_OUT_OF_RANGE' || !(error instanceof ApiError)) return null;
  const detail = error.detail as { min_ml?: unknown; max_ml?: unknown } | undefined;
  return typeof detail?.min_ml === 'number' && typeof detail.max_ml === 'number' ? { min: detail.min_ml, max: detail.max_ml } : null;
}

/** The dose: a big volume with a stepper, Light · Standard · Strong presets, and the API's limits (FR-7). */
export function DoseControl({ device }: DoseControlProps) {
  const dosing = device.dosing;
  const { unit } = useUnits();
  const setDosing = useSetDosing(device.device_id, dosing);
  const [draftMl, setDraftMl] = useDebouncedCommit<number>((doseMl, done) =>
    setDosing.mutate({ doseMl: Math.round(doseMl) }, { onSettled: done }),
  );

  if (dosing.fixed_seconds !== null || dosing.dose_ml === null) {
    return (
      <Notice>
        Each dose opens the valve for a fixed time instead of a volume. Change it under Advanced.
      </Notice>
    );
  }

  const shownMl = draftMl ?? dosing.dose_ml;
  const shown = toDisplay(shownMl, unit);
  const atMin = shownMl <= dosing.min_ml;
  const atMax = shownMl >= dosing.max_ml;
  const step = (direction: 1 | -1) => {
    const grid = VOLUME_STEP[unit];
    const next = (direction > 0 ? Math.floor(shown / grid) + 1 : Math.ceil(shown / grid) - 1) * grid;
    setDraftMl(Math.min(Math.max(fromDisplay(next, unit), dosing.min_ml), dosing.max_ml));
  };

  const { light_ml: light, standard_ml: standard, strong_ml: strong } = dosing.presets;
  const presets: { value: PresetKey; label: string; detail: string; ml: number }[] = [
    { value: 'light', label: 'Light', detail: formatVolume(light, unit), ml: light },
    { value: 'standard', label: 'Standard', detail: formatVolume(standard, unit), ml: standard },
    { value: 'strong', label: 'Strong', detail: formatVolume(strong, unit), ml: strong },
  ];
  const selected = presets.find((preset) => preset.ml === Math.round(shownMl))?.value ?? null;
  const range = outOfRange(setDosing.error);

  return (
    <div className="flex flex-col items-center gap-3.5 rounded-[18px] bg-surface2 px-3 pt-5 pb-4">
      <h3 className="m-0 self-start text-[13px] font-semibold text-dim">Dose</h3>
      <Stepper
        label="Dose"
        value={unit === 'oz' && shown < 10 ? shown.toFixed(1) : String(shown)}
        unit={UNIT_LABEL[unit]}
        atMin={atMin}
        atMax={atMax}
        onDecrement={() => step(-1)}
        onIncrement={() => step(1)}
      />
      <div className="text-center text-sm text-dim">
        <p className="m-0">≈ {formatVolume(shownMl, otherUnit(unit))}</p>
        {(atMin || atMax) && <p className="m-0 mt-1 font-medium text-warn">This liquid can dose {formatVolumeRange(dosing.min_ml, dosing.max_ml, unit)}</p>}
      </div>
      <ChoiceChips
        label="Dose presets"
        className="justify-center"
        options={presets}
        selected={selected}
        onSelect={(key) => {
          const preset = presets.find((item) => item.value === key);
          if (preset) setDraftMl(preset.ml);
        }}
      />
      {dosing.capped_ml_when_low !== null && (
        <Notice tone="warn" className="w-full">
          When the bottle is nearly empty, the device can dispense at most about {formatVolume(dosing.capped_ml_when_low, unit)} per dose.
        </Notice>
      )}
      {range && (
        <Notice tone="bad" role="alert" className="w-full">
          That dose is outside what this liquid can do. It can dose {formatVolumeRange(range.min, range.max, unit)}.
        </Notice>
      )}
      {setDosing.isError && !range && (
        <Notice tone="bad" role="alert" className="w-full">
          {errorMessage(setDosing.error)}
        </Notice>
      )}
    </div>
  );
}
