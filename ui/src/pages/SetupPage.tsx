import { QueryBoundary } from '@/components/organisms/QueryBoundary';
import { SetupWizard } from '@/components/organisms/SetupWizard';
import { useServerInfo } from '@/hooks/useServer';

/** Route `/setup`: first-run setup (FR-16). The boot gate sends every URL here while setup is required. */
export function SetupPage() {
  const info = useServerInfo();
  return (
    <QueryBoundary query={info} what="OpenFLO">
      {(data) => <SetupWizard info={data} />}
    </QueryBoundary>
  );
}
