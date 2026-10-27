import type { ReactNode } from 'react';
import { QrCode } from '@/components/atoms/QrCode';

export interface QrCardProps {
  /** The encoded payload; shown only as the code. */
  value: string;
  /** The code's accessible name. */
  label: string;
  /** What the code is, e.g. "Network". */
  caption: string;
  /** A readable stand-in for the payload, e.g. the network name. Never the payload when it holds a secret. */
  displayValue: string;
  /** Optional action under the caption, e.g. "Copy link". */
  action?: ReactNode;
}

/** A QR code on its light card with a caption: the phone steps of the add-device wizard. */
export function QrCard({ value, label, caption, displayValue, action }: QrCardProps) {
  return (
    <figure className="m-0 flex flex-col items-center gap-3.5">
      <div className="rounded-card border border-border bg-qr-paper p-[18px] shadow-raise">
        <QrCode value={value} label={label} />
      </div>
      <figcaption className="text-center text-sm text-dim">
        {caption}
        <br />
        <span className="font-mono text-fg [overflow-wrap:anywhere]">{displayValue}</span>
      </figcaption>
      {action}
    </figure>
  );
}
