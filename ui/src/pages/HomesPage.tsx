import { HomeList } from '@/components/organisms/HomeList';
import { QueryBoundary } from '@/components/organisms/QueryBoundary';
import { AppShell } from '@/components/templates/AppShell';
import { useHomes } from '@/hooks/useHomes';

/** Route `/`: every home (FR-1). */
export function HomesPage() {
  const homes = useHomes();
  return (
    <AppShell>
      <QueryBoundary query={homes} what="homes">
        {(data) => <HomeList homes={data} />}
      </QueryBoundary>
      <p className="m-0 text-center text-[12.5px] text-faint">OpenFLO · running on your home server</p>
    </AppShell>
  );
}
