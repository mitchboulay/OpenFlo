import { Link } from 'react-router';
import { buttonClassName } from '@/components/atoms/Button';
import { LevelBars } from '@/components/atoms/LevelBars';
import { SectionCard } from '@/components/molecules/SectionCard';
import type { DeviceDetail } from '@/api/types';
import { moveNetworkPath } from '@/lib/provisioning';

export interface WifiCardProps {
  device: DeviceDetail;
}

/** `connectionLevel` from the firmware, 0–100 (observed 64–100), as bars and words. */
function signalOf(level: number | null): { bars: number; words: string } | null {
  if (level === null) return null;
  if (level >= 75) return { bars: 4, words: 'Strong signal' };
  if (level >= 50) return { bars: 3, words: 'Good signal' };
  if (level >= 25) return { bars: 2, words: 'Fair signal' };
  return { bars: 1, words: 'Weak signal' };
}

/**
 * FR-12: the network the device last reported and how strong it is. Changing networks means setting the device up
 * again (the reset-kind wizard): the firmware's own Wi-Fi-edit entry by button is not traced, and the device's
 * buttons are unsafe to guess at (a long press of the user button can dispense; of the reset button, factory-reset).
 */
export function WifiCard({ device }: WifiCardProps) {
  const signal = signalOf(device.signal);
  const movePath = moveNetworkPath(device);

  return (
    <SectionCard id="wifi" title="Wi-Fi" icon="wifi" collapsible>
      <div className="flex items-center gap-3.5">
        <LevelBars level={signal?.bars ?? 0} />
        <div className="min-w-0 flex-1">
          <p className="m-0 font-semibold [overflow-wrap:anywhere]">{device.network_name ?? 'Network not reported yet'}</p>
          <p className="m-0 text-sm text-dim">
            {signal?.words ?? 'Signal not reported yet'}
            {device.last_ip && (
              <>
                {' · '}
                <span className="font-mono text-[13px]">{device.last_ip}</span>
              </>
            )}
          </p>
        </div>
      </div>
      <p className="m-0 text-sm text-dim">
        To change networks, set the device up again on the new one. It keeps its name, settings and history here.
      </p>
      {movePath && (
        <div>
          <Link to={movePath} className={buttonClassName('secondary')}>
            Change Wi-Fi…
          </Link>
        </div>
      )}
    </SectionCard>
  );
}
