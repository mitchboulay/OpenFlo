import { ListRow } from '@/components/molecules/ListRow';
import { SectionCard } from '@/components/molecules/SectionCard';
import type { DeviceDetail } from '@/api/types';
import { formatDate, formatDateTime } from '@/lib/time';

export interface InfoCardProps {
  device: DeviceDetail;
  timeZone: string;
}

const MISSING = '—';
const HARDWARE = { valve: 'Valve', motor: 'Motor' } as const;

/** Read-only device facts (FR-3); the network lives in the Wi-Fi card. Unknown values show "—". */
export function InfoCard({ device, timeZone }: InfoCardProps) {
  const rows: { label: string; value: string | null; mono?: boolean }[] = [
    { label: 'Model', value: `iFLO${device.hardware_type ? ` · ${HARDWARE[device.hardware_type]}` : ''}` },
    { label: 'Serial number', value: device.device_id, mono: true },
    { label: 'Firmware', value: device.firmware_version },
    { label: 'Board version', value: device.pcb_version },
    { label: 'MAC address', value: device.mac, mono: true },
    { label: 'External power', value: device.ext_power === null ? null : device.ext_power ? 'Connected' : 'Not connected' },
    { label: 'Installed', value: formatDate(device.installed_at, timeZone) },
    { label: 'First seen', value: formatDateTime(device.first_seen, timeZone) },
    { label: 'Last seen', value: formatDateTime(device.last_seen, timeZone) },
  ];
  return (
    <SectionCard id="info" title="Device info" icon="info" collapsible>
      <ul className="m-0 list-none p-0">
        {rows.map((row) => (
          <ListRow key={row.label} title={row.label} value={row.value ?? MISSING} mono={row.mono === true && row.value !== null} />
        ))}
      </ul>
    </SectionCard>
  );
}
