import { useState } from 'react';
import { Badge } from '@/components/atoms/Badge';
import { Button } from '@/components/atoms/Button';
import { Notice } from '@/components/atoms/Notice';
import { ConfirmButton } from '@/components/molecules/ConfirmButton';
import { ListRow } from '@/components/molecules/ListRow';
import { SectionCard } from '@/components/molecules/SectionCard';
import type { ApiToken } from '@/api/types';
import { useRevokeToken, useTokens } from '@/hooks/useAuth';
import { errorMessage } from '@/lib/errors';
import { formatRelative } from '@/lib/time';
import { NewTokenSheet } from './NewTokenSheet';
import { QueryBoundary } from './QueryBoundary';

/** Settings → API tokens (FR-15, AD-10): list, create (shown once), two-step revoke. */
export function TokensCard() {
  const tokens = useTokens();
  const revoke = useRevokeToken();
  const [creating, setCreating] = useState(false);

  const row = (token: ApiToken) => {
    const bootstrap = token.kind === 'bootstrap';
    return (
      <ListRow
        key={token.id}
        variant="history"
        title={token.name}
        subtitle={
          <>
            Last used {formatRelative(token.last_used_at) ?? 'never'} · …<span className="font-mono">{token.fingerprint}</span>
            {bootstrap && (
              <span className="block">
                Remove <code className="font-mono text-[12.5px]">OPENFLO_API_TOKEN</code> to revoke
              </span>
            )}
          </>
        }
        value={
          bootstrap ? (
            <Badge>From server config</Badge>
          ) : (
            <ConfirmButton label="Revoke" armedLabel={`Revoke ${token.name}?`} disabled={revoke.isPending} onConfirm={() => revoke.mutate(token)} />
          )
        }
      />
    );
  };

  return (
    <SectionCard title="API tokens" icon="key" description="For scripts and other apps. A token can do anything you can.">
      <QueryBoundary query={tokens} what="tokens">
        {(list) =>
          list.length ? (
            <ul aria-label="API tokens" className="m-0 list-none p-0">
              {list.map(row)}
            </ul>
          ) : (
            <p className="m-0 text-sm text-dim">No tokens yet.</p>
          )
        }
      </QueryBoundary>
      {revoke.isError && (
        <Notice tone="bad" role="alert">
          {errorMessage(revoke.error)}
        </Notice>
      )}
      <div>
        <Button onClick={() => setCreating(true)}>New token…</Button>
      </div>
      <NewTokenSheet open={creating} onClose={() => setCreating(false)} />
    </SectionCard>
  );
}
