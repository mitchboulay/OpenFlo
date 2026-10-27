import { useState } from 'react';
import { Button } from '@/components/atoms/Button';
import { Notice } from '@/components/atoms/Notice';
import { BottleGauge } from '@/components/molecules/BottleGauge';
import { api } from '@/api/endpoints';
import type { Bottle, DeviceDetail } from '@/api/types';
import { useDeviceAction } from '@/hooks/useDevice';
import { useUnits } from '@/hooks/useUnits';
import { cn } from '@/lib/cn';
import { GUIDANCE } from '@/lib/deviceStatus';
import { errorMessage } from '@/lib/errors';
import { formatVolume, type VolumeUnit } from '@/lib/units';
import { LevelSheet } from './LevelSheet';

export interface BottleLevelProps {
  device: DeviceDetail;
}

const TEXT = { ok: 'text-ok', warn: 'text-warn', bad: 'text-bad', neutral: 'text-dim' } as const;

/** Positions of each dose along the bottle, so "≈ 3 doses" is visible (display only). */
function doseTicks(bottle: Bottle, doseMl: number | null): number[] {
  if (!doseMl || doseMl <= 0) return [];
  const count = Math.floor(bottle.capacity_ml / doseMl);
  return Array.from({ length: count }, (_, index) => ((index + 1) * doseMl) / bottle.capacity_ml);
}

function levelLine(bottle: Bottle | null, unit: VolumeUnit): string {
  if (!bottle) return 'No bottle recorded yet.';
  if (bottle.est_remaining_ml === null) return 'We don’t know how full the bottle is yet.';
  const doses = bottle.est_doses_left ?? 0;
  const parts = [
    `About ${formatVolume(bottle.est_remaining_ml, unit)} left`,
    doses < 1 ? '≈ less than 1 dose' : `≈ ${doses} ${doses === 1 ? 'dose' : 'doses'}`,
  ];
  if (bottle.est_days_left !== null) parts.push(`≈ ${Math.floor(bottle.est_days_left)} days at your schedule`);
  return parts.join(' · ');
}

/** The bottle: level with dose ticks, refill guidance from the API, and New bottle / Set level (FR-8). */
export function BottleLevel({ device }: BottleLevelProps) {
  const [levelOpen, setLevelOpen] = useState(false);
  const { unit } = useUnits();
  const bottle = device.bottle;
  const guidance = GUIDANCE[bottle?.guidance ?? 'unknown'];
  const replace = useDeviceAction(device.device_id, () => api.newBottle(device.device_id, null));
  const fraction = bottle?.est_remaining_ml != null ? bottle.est_remaining_ml / bottle.capacity_ml : null;
  const line = levelLine(bottle, unit);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="m-0 text-[13px] font-semibold text-dim">Bottle level</h3>
        <span className={cn('inline-flex items-center gap-1.5 text-[13px] font-semibold', TEXT[guidance.tone])}>
          <span aria-hidden="true" className="size-[7px] rounded-[2px] bg-current" />
          {guidance.label}
        </span>
      </div>
      <BottleGauge fraction={fraction} ticks={bottle ? doseTicks(bottle, device.dosing.dose_ml) : []} tone={guidance.tone} label={line} />
      <p className="m-0 text-pretty">{line}</p>
      {replace.isError && <Notice tone="bad" role="alert">{errorMessage(replace.error)}</Notice>}
      <div className="flex flex-wrap gap-2">
        <Button disabled={replace.isPending} onClick={() => replace.mutate(undefined)}>
          I put in a new bottle
        </Button>
        <Button variant="ghost" onClick={() => setLevelOpen(true)}>
          Set level
        </Button>
      </div>
      <LevelSheet open={levelOpen} device={device} onClose={() => setLevelOpen(false)} />
    </div>
  );
}
