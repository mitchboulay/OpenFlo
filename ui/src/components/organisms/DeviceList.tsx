import { useState } from 'react';
import { Link } from 'react-router';
import { Button, buttonClassName } from '@/components/atoms/Button';
import { Icon } from '@/components/atoms/Icon';
import type { DeviceSummary, HomeSummary, UnclaimedDevice } from '@/api/types';
import { ClaimSheet } from './ClaimSheet';
import { DeviceCard } from './DeviceCard';
import { HomeSheet } from './HomeSheet';
import { UnclaimedDeviceCard } from './UnclaimedDeviceCard';

export interface DeviceListProps {
  home: HomeSummary;
  devices: readonly DeviceSummary[];
  unclaimed: readonly UnclaimedDevice[];
}

function summaryLine(home: HomeSummary, devices: readonly DeviceSummary[]): string {
  const count = `${devices.length} ${devices.length === 1 ? 'device' : 'devices'}`;
  if (home.summary === 'attention') return `${home.attention_count} ${home.attention_count === 1 ? 'needs' : 'need'} attention · ${count}`;
  return devices.length ? `All good · ${count}` : 'No devices yet';
}

/** One home: its devices (retired ones hidden) and any unclaimed devices (FR-2, FR-5). */
export function DeviceList({ home, devices, unclaimed }: DeviceListProps) {
  const [editing, setEditing] = useState(false);
  const [claiming, setClaiming] = useState<UnclaimedDevice | null>(null);
  const active = devices.filter((device) => device.status !== 'retired');

  return (
    <>
      <header className="flex flex-wrap items-end justify-between gap-4 pt-4">
        <div className="min-w-0">
          <h1 className="m-0 text-[28px] font-bold tracking-tight">{home.name}</h1>
          <p className="m-0 mt-0.5 text-dim">{summaryLine(home, active)}</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => setEditing(true)}>
            <Icon name="edit" size={16} />
            Edit home
          </Button>
          <Link to={`/homes/${home.id}/add`} className={buttonClassName('primary')}>
            <Icon name="plus" size={16} />
            Add device
          </Link>
        </div>
      </header>
      {unclaimed.map((device) => (
        <UnclaimedDeviceCard key={device.device_id} device={device} timeZone={home.timezone} onClaim={() => setClaiming(device)} />
      ))}
      {active.length > 0 ? (
        <ul className="m-0 grid list-none grid-cols-1 gap-3.5 p-0 sm:grid-cols-2 lg:grid-cols-3">
          {active.map((device) => (
            <li key={device.device_id} className="flex flex-col [&>a]:flex-1">
              <DeviceCard device={device} timeZone={home.timezone} />
            </li>
          ))}
        </ul>
      ) : (
        <p className="m-0 rounded-[18px] border border-dashed border-border2 px-5 py-10 text-center text-dim">No devices in this home yet.</p>
      )}
      <HomeSheet open={editing} home={home} onClose={() => setEditing(false)} />
      <ClaimSheet device={claiming} home={home} onClose={() => setClaiming(null)} />
    </>
  );
}
