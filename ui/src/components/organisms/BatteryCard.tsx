import { Notice } from '@/components/atoms/Notice';
import { Sparkline } from '@/components/atoms/Sparkline';
import { SectionCard } from '@/components/molecules/SectionCard';
import type { DeviceDetail } from '@/api/types';
import { useBattery } from '@/hooks/useDevice';
import { cn } from '@/lib/cn';
import { LOW_BATTERY_PERCENT } from '@/lib/deviceStatus';

export interface BatteryCardProps {
  device: DeviceDetail;
}

/** Battery now, its 30-day trend and the API's projection to 20 % (FR-11). */
export function BatteryCard({ device }: BatteryCardProps) {
  const battery = useBattery(device.device_id);
  const level = device.battery_level;
  const low = level !== null && level < LOW_BATTERY_PERCENT;
  const points = battery.data?.points ?? [];
  const projection = battery.data?.projection_days_to_20 ?? null;
  const first = points[0];
  const last = points[points.length - 1];

  return (
    <SectionCard
      id="battery"
      title="Battery"
      icon="battery"
      collapsible
      aside={
        <span className={cn('text-[28px] font-semibold tracking-[-0.03em] tabular-nums', low ? 'text-bad' : 'text-ok')}>
          {level === null ? '—' : `${level}%`}
        </span>
      }
    >
      {battery.isError && <Notice tone="bad">Couldn’t load the battery history.</Notice>}
      {first && last && points.length >= 2 && (
        <div className="flex flex-col gap-1">
          <Sparkline
            values={points.map((point) => point.level)}
            tone={low ? 'bad' : 'ok'}
            label={`Battery over the last 30 days, from ${first.level}% to ${last.level}%`}
          />
          <div aria-hidden="true" className="flex justify-between text-xs text-faint">
            <span>30 days ago</span>
            <span>Today</span>
          </div>
        </div>
      )}
      {projection === null ? (
        <Notice>Not enough data yet. Check back in a few days for an estimate.</Notice>
      ) : (
        <p className="m-0 text-pretty">
          {low && 'Battery low. '}≈ {Math.round(projection)} {Math.round(projection) === 1 ? 'day' : 'days'} until the batteries need
          replacing (20 %) at this check-in rate.
        </p>
      )}
    </SectionCard>
  );
}
