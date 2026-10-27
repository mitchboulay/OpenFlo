import { Navigate, useParams } from 'react-router';
import { DeviceList } from '@/components/organisms/DeviceList';
import { QueryBoundary } from '@/components/organisms/QueryBoundary';
import { AppShell } from '@/components/templates/AppShell';
import { useHomeDevices, useHomes, useUnclaimedDevices } from '@/hooks/useHomes';

/** Route `/homes/:homeId`: the home's devices and unclaimed devices (FR-2, FR-5). */
export function HomePage() {
  const homeId = Number(useParams().homeId);
  const homes = useHomes();
  const devices = useHomeDevices(homeId);
  const unclaimed = useUnclaimedDevices();
  const home = homes.data?.find((candidate) => candidate.id === homeId);

  if (!Number.isInteger(homeId) || (homes.isSuccess && !home)) return <Navigate to="/" replace />;

  return (
    <AppShell back={{ to: '/', label: 'Homes' }} contentWidth="wide">
      <QueryBoundary query={devices} what="devices">
        {(list) => home && <DeviceList home={home} devices={list} unclaimed={unclaimed.data ?? []} />}
      </QueryBoundary>
    </AppShell>
  );
}
