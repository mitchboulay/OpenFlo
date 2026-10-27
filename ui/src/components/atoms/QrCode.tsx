import { useMemo } from 'react';
import { create } from 'qrcode';

export interface QrCodeProps {
  /** The encoded payload. Rendered only as modules, never as text, so a secret stays off the page. */
  value: string;
  /** Accessible name, e.g. "QR code to join Wi-Fi network iFLO device". */
  label: string;
  /** Rendered edge length in px. Defaults to 200. */
  size?: number;
}

/** One SVG path of dark modules, so a large code stays a single DOM node. */
function modulePath(value: string): { path: string; count: number } {
  const { modules } = create(value, { errorCorrectionLevel: 'M' });
  let path = '';
  for (let row = 0; row < modules.size; row += 1) {
    for (let column = 0; column < modules.size; column += 1) {
      if (modules.get(row, column)) path += `M${column} ${row}h1v1h-1z`;
    }
  }
  return { path, count: modules.size };
}

/** A QR code generated in the browser (FR-4). Dark on light in both themes, as cameras expect. */
export function QrCode({ value, label, size = 200 }: QrCodeProps) {
  const { path, count } = useMemo(() => modulePath(value), [value]);
  return (
    <svg
      role="img"
      aria-label={label}
      width={size}
      height={size}
      viewBox={`0 0 ${count} ${count}`}
      shapeRendering="crispEdges"
      className="block bg-qr-paper text-qr-ink"
    >
      <path d={path} fill="currentColor" />
    </svg>
  );
}
