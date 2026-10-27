import { useState } from 'react';
import { Button } from '@/components/atoms/Button';
import { Notice } from '@/components/atoms/Notice';
import { CheckinOption, type CheckinOptionProps } from '@/components/molecules/CheckinOption';
import { SectionCard } from '@/components/molecules/SectionCard';
import { api } from '@/api/endpoints';
import type { DeviceDetail, WakePreset } from '@/api/types';
import { useDeviceAction } from '@/hooks/useDevice';
import { errorMessage } from '@/lib/errors';

export interface CheckinCardProps {
  device: DeviceDetail;
}

type PresetCopy = Pick<CheckinOptionProps, 'name' | 'line' | 'cost' | 'costLabel'> & { recommended?: boolean };

/** FR-10 presets. The seconds behind them live in the API (AD-7); the UI never sends raw intervals. */
const PRESETS: Record<WakePreset, PresetCopy> = {
  battery_saver: { name: 'Battery saver', line: 'Checks in daily. Changes can take up to a day.', cost: 1, costLabel: 'Lowest battery use' },
  balanced: { name: 'Balanced', line: 'Checks in every 6 hours.', cost: 2, costLabel: 'Low battery use', recommended: true },
  responsive: { name: 'Responsive', line: 'Checks in hourly. Uses more battery.', cost: 3, costLabel: 'Higher battery use' },
  testing: { name: 'Testing', line: 'Every 15 minutes. Drains the battery. Use briefly.', cost: 4, costLabel: 'Very high battery use' },
};

const EVERYDAY: readonly WakePreset[] = ['battery_saver', 'balanced', 'responsive'];

function customLine(seconds: number | null): string {
  if (!seconds) return 'It uses its own check-in time.';
  const hours = seconds / 3600;
  const every = hours >= 1 ? `${Math.round(hours)} hours` : `${Math.round(seconds / 60)} minutes`;
  return `It uses a custom check-in time: every ${every}.`;
}

/** How often the device wakes (FR-10). "Testing" sits under Advanced (critique-v2 #6). */
export function CheckinCard({ device }: CheckinCardProps) {
  const current = device.controls.wake_preset;
  const [advanced, setAdvanced] = useState(current === 'testing');
  const choose = useDeviceAction(device.device_id, (preset: WakePreset) =>
    api.updateControls(device.device_id, { wake_preset: preset }),
  );
  const visible = advanced ? [...EVERYDAY, 'testing' as const] : EVERYDAY;
  const disabled = device.status === 'retired' || choose.isPending;

  return (
    <SectionCard id="checkin" title="Check-in" icon="clock" description="How often your iFLO wakes up to pick up changes." collapsible>
      {current === null && <Notice>{customLine(device.controls.sync_interval_seconds)} Pick an option to change it.</Notice>}
      <div role="radiogroup" aria-label="Check-in" className="flex flex-col gap-2">
        {visible.map((preset) => (
          <CheckinOption
            key={preset}
            {...PRESETS[preset]}
            selected={preset === current}
            disabled={disabled}
            onSelect={() => preset !== current && choose.mutate(preset)}
          />
        ))}
      </div>
      {choose.isError && <Notice tone="bad" role="alert">{errorMessage(choose.error)}</Notice>}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="m-0 text-[13px] text-dim">Bars show battery use.</p>
        {current !== 'testing' && (
          <Button variant="ghost" aria-expanded={advanced} onClick={() => setAdvanced(!advanced)}>
            {advanced ? 'Hide advanced' : 'Advanced'}
          </Button>
        )}
      </div>
    </SectionCard>
  );
}
