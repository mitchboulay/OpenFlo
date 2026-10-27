import { PendingBadge } from './PendingBadge';

export interface PendingRowProps {
  /** What is waiting, e.g. "Dose change". */
  label: string;
  /** Optional detail after the label. */
  detail?: string;
  /** Expected next check-in (ISO), passed to the badge. */
  expectedAt: string | null;
  timeZone?: string;
}

/** One named change the device hasn't picked up: "Dose change   [Waiting for device · ~4:42 PM]". */
export function PendingRow({ label, detail, expectedAt, timeZone }: PendingRowProps) {
  return (
    <li className="flex flex-wrap items-center gap-2.5 border-t border-border px-3.5 py-3 first:border-t-0">
      <span className="min-w-0 flex-[1_1_10rem]">
        <span className="font-medium">{label}</span>
        {detail && <span className="text-dim"> {detail}</span>}
      </span>
      <PendingBadge expectedAt={expectedAt} timeZone={timeZone} />
    </li>
  );
}
