import { Badge } from '@/components/atoms/Badge';
import { Icon } from '@/components/atoms/Icon';
import { formatClockTime } from '@/lib/time';

export interface PendingBadgeProps {
  /** ISO-8601 time of the device's expected next check-in; omit when unknown. */
  expectedAt?: string | null;
  /** IANA zone to show the time in (the home's zone). Defaults to the browser's. */
  timeZone?: string;
  className?: string;
}

/**
 * Marks a change the device has not picked up yet: "Waiting for device · ~4:42 PM".
 * The device can't be woken remotely, so every pending change says when it lands.
 */
export function PendingBadge({ expectedAt, timeZone, className }: PendingBadgeProps) {
  const clock = formatClockTime(expectedAt, timeZone);
  return (
    <Badge tone="warn" className={className} icon={<Icon name="clock" size={12} strokeWidth={2.2} />}>
      {clock ? `Waiting for device · ~${clock}` : 'Waiting for device'}
    </Badge>
  );
}

