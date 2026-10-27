import { Navigate, useParams, useSearchParams } from 'react-router';
import { ProvisionWizard } from '@/components/organisms/ProvisionWizard';
import { QueryBoundary } from '@/components/organisms/QueryBoundary';
import { useHomes } from '@/hooks/useHomes';

/** Route `/homes/:homeId/add/:sessionId?` (`?device=` for a reset): the add-device wizard (FR-4). */
export function AddDevicePage() {
  const params = useParams();
  const [search] = useSearchParams();
  const homeId = Number(params.homeId);
  const sessionId = params.sessionId === undefined ? null : Number(params.sessionId);
  const homes = useHomes();
  const home = homes.data?.find((candidate) => candidate.id === homeId);

  if (!Number.isInteger(homeId) || (sessionId !== null && !Number.isInteger(sessionId)) || (homes.isSuccess && !home)) {
    return <Navigate to="/" replace />;
  }

  return (
    <QueryBoundary query={homes} what="homes">
      {() => home && <ProvisionWizard home={home} sessionId={sessionId} targetDeviceId={search.get('device')} />}
    </QueryBoundary>
  );
}

export default AddDevicePage;
