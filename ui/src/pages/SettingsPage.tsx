import { AboutCard } from '@/components/organisms/AboutCard';
import { QueryBoundary } from '@/components/organisms/QueryBoundary';
import { ServerAddressCard } from '@/components/organisms/ServerAddressCard';
import { SignInCard } from '@/components/organisms/SignInCard';
import { TokensCard } from '@/components/organisms/TokensCard';
import { UnitsCard } from '@/components/organisms/UnitsCard';
import { AppShell } from '@/components/templates/AppShell';
import { useServerInfo } from '@/hooks/useServer';

/** Route `/settings` (FR-16, v3 §14): one column of preference groups, at every width. */
export function SettingsPage() {
  const info = useServerInfo();
  return (
    <AppShell back={{ to: '/', label: 'Homes' }}>
      <h1 className="m-0 text-[28px] font-bold tracking-tight">Settings</h1>
      <QueryBoundary query={info} what="settings">
        {(data) => (
          <>
            <ServerAddressCard address={data.server_address} />
            <UnitsCard />
            <SignInCard auth={data.auth} />
            <TokensCard />
            <AboutCard version={data.version} />
          </>
        )}
      </QueryBoundary>
    </AppShell>
  );
}
