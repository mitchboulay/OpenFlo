import { useState } from 'react';
import { Button } from '@/components/atoms/Button';
import { Notice } from '@/components/atoms/Notice';
import { ChoiceChips } from '@/components/molecules/ChoiceChips';
import type { DeviceDetail } from '@/api/types';
import { useLiquidProfiles } from '@/hooks/useDevice';
import { liquidChange, useSetDosing } from '@/hooks/useDosing';
import { useUnits } from '@/hooks/useUnits';
import { errorMessage } from '@/lib/errors';
import { formatFlow } from '@/lib/units';
import { CalibrateSheet } from './CalibrateSheet';
import { NewLiquidSheet } from './NewLiquidSheet';

export interface LiquidPickerProps {
  device: DeviceDetail;
}

const NOT_CALIBRATED = 'Not calibrated yet';

/** The liquid and its calibration (critique-v2 #4): "Not calibrated yet · Calibrate" or "Measured … · Recalibrate". */
export function LiquidPicker({ device }: LiquidPickerProps) {
  const [sheet, setSheet] = useState<'new' | 'calibrate' | null>(null);
  const dosing = device.dosing;
  const { unit } = useUnits();
  const profiles = useLiquidProfiles(device.home_id);
  const setDosing = useSetDosing(device.device_id, dosing);
  const list = profiles.data ?? [dosing.profile];

  const options = list.map((profile) => {
    const calibrated = profile.id === dosing.profile.id ? dosing.calibrated : profile.calibrated;
    return { value: profile.id, label: profile.name, detail: calibrated ? undefined : NOT_CALIBRATED, detailTone: 'warn' as const };
  });

  const choose = (profileId: number) => {
    const profile = list.find((item) => item.id === profileId);
    if (!profile || profile.id === dosing.profile.id) return;
    setDosing.mutate(liquidChange(dosing, profile));
  };

  return (
    <div className="flex flex-col gap-2.5">
      <h3 className="m-0 text-[13px] font-semibold text-dim">Liquid</h3>
      <ChoiceChips
        label="Liquid"
        options={options}
        selected={dosing.profile.id}
        onSelect={choose}
        disabled={setDosing.isPending}
        trailing={
          <button
            type="button"
            onClick={() => setSheet('new')}
            className="min-h-11 cursor-pointer rounded-control border border-dashed border-border2 px-3.5 text-sm font-medium text-dim hover:text-fg"
          >
            New liquid…
          </button>
        }
      />
      <div className="flex flex-wrap items-center gap-x-2 text-sm">
        <span className={dosing.calibrated ? 'text-dim' : 'text-warn'}>
          {dosing.calibrated ? `Measured ${formatFlow(dosing.flow_ml_s, unit)}` : NOT_CALIBRATED}
        </span>
        <span aria-hidden="true" className="text-faint">
          ·
        </span>
        <Button variant="ghost" className="px-2" onClick={() => setSheet('calibrate')}>
          {dosing.calibrated ? 'Recalibrate' : 'Calibrate'}
        </Button>
      </div>
      {setDosing.isError && <Notice tone="bad" role="alert">{errorMessage(setDosing.error)}</Notice>}
      <NewLiquidSheet open={sheet === 'new'} device={device} profiles={list} onClose={() => setSheet(null)} />
      <CalibrateSheet open={sheet === 'calibrate'} device={device} onClose={() => setSheet(null)} />
    </div>
  );
}
