import { Button } from '@/components/atoms/Button';
import { Icon } from '@/components/atoms/Icon';
import type { UnclaimedDevice } from '@/api/types';
import { formatWhen } from '@/lib/time';

export interface UnclaimedDeviceCardProps {
  device: UnclaimedDevice;
  timeZone: string;
  /** Opens the claim sheet. */
  onClaim: () => void;
}

/** A device that checks in without being registered (FR-5), with "Add to home…". */
export function UnclaimedDeviceCard({ device, timeZone, onClaim }: UnclaimedDeviceCardProps) {
  return (
    <article className="flex flex-wrap items-center gap-4 rounded-[18px] border-[1.5px] border-dashed border-border2 bg-accent-soft p-[18px]">
      <span className="flex size-11 flex-none items-center justify-center rounded-control border border-border bg-surface text-accent-text">
        <Icon name="wifi" strokeWidth={1.8} />
      </span>
      <div className="min-w-0 flex-1">
        <h2 className="m-0 text-base font-semibold">New iFLO found</h2>
        <p className="m-0 text-sm text-dim [overflow-wrap:anywhere]">
          <span className="font-mono text-[13px]">{device.device_id}</span> checked in
          {device.last_ip && (
            <>
              {' '}from <span className="font-mono text-[13px]">{device.last_ip}</span>
            </>
          )}
          {' '}at {formatWhen(device.last_seen, timeZone)}. It isn’t part of any home yet.
        </p>
      </div>
      <Button variant="primary" onClick={onClaim} className="max-sm:w-full">
        Add to home…
      </Button>
    </article>
  );
}
