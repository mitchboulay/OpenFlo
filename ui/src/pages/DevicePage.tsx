import { useNavigate, useParams } from 'react-router';
import { BatteryCard } from '@/components/organisms/BatteryCard';
import { CheckinCard } from '@/components/organisms/CheckinCard';
import { DeviceHeader } from '@/components/organisms/DeviceHeader';
import { DosingCard } from '@/components/organisms/DosingCard';
import { HistoryCard } from '@/components/organisms/HistoryCard';
import { IdentityFlagCard } from '@/components/organisms/IdentityFlagCard';
import { InfoCard } from '@/components/organisms/InfoCard';
import { QueryBoundary } from '@/components/organisms/QueryBoundary';
import { ScheduleEditor } from '@/components/organisms/ScheduleEditor';
import { WifiCard } from '@/components/organisms/WifiCard';
import { AppShell } from '@/components/templates/AppShell';
import { DeviceLayout } from '@/components/templates/DeviceLayout';
import { useDevice } from '@/hooks/useDevice';
import { useHomes } from '@/hooks/useHomes';

const SECTIONS = [
  { id: 'dosing', label: 'Dosing' },
  { id: 'schedule', label: 'Schedule' },
  { id: 'device', label: 'Device' },
] as const;

/** Route `/devices/:deviceId`: one device, polled every 10 s while visible. */
export function DevicePage() {
  const deviceId = useParams().deviceId ?? '';
  const navigate = useNavigate();
  const device = useDevice(deviceId);
  const homes = useHomes();
  const home = homes.data?.find((candidate) => candidate.id === device.data?.home_id);
  const timeZone = home?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone;
  const back = home ? { to: `/homes/${home.id}`, label: home.name } : { to: '/', label: 'Homes' };

  return (
    <AppShell back={back} contentWidth="wide">
      <QueryBoundary query={device} what="this device">
        {(detail) => (
          <DeviceLayout
            header={
              <>
                <DeviceHeader device={detail} timeZone={timeZone} onRetired={() => navigate(back.to)} />
                {detail.flags
                  .filter((flag) => flag.acked_at === null)
                  .map((flag) => (
                    <IdentityFlagCard key={flag.id} deviceId={detail.device_id} flag={flag} timeZone={timeZone} />
                  ))}
              </>
            }
            sections={SECTIONS}
            primary={
              <>
                <DosingCard device={detail} />
                <ScheduleEditor device={detail} timeZone={timeZone} />
              </>
            }
            secondary={
              <>
                <CheckinCard device={detail} />
                <BatteryCard device={detail} />
                <WifiCard device={detail} />
                <InfoCard device={detail} timeZone={timeZone} />
                <HistoryCard deviceId={detail.device_id} timeZone={timeZone} />
              </>
            }
          />
        )}
      </QueryBoundary>
    </AppShell>
  );
}
