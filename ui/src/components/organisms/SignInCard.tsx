import { useNavigate } from 'react-router';
import { Button } from '@/components/atoms/Button';
import { Notice } from '@/components/atoms/Notice';
import { ListRow } from '@/components/molecules/ListRow';
import { SectionCard } from '@/components/molecules/SectionCard';
import type { ServerInfo } from '@/api/types';
import { useLogout, useMe } from '@/hooks/useAuth';
import { issuerHost } from '@/lib/addressCheck';
import { errorMessage } from '@/lib/errors';
import { SIGN_IN_DOCS_URL, SIGN_IN_PATH } from '@/lib/links';

export interface SignInCardProps {
  auth: ServerInfo['auth'];
}

function methodLabel(auth: ServerInfo['auth']): string {
  switch (auth.mode) {
    case 'basic':
      return 'Username and password';
    case 'oidc':
      return issuerHost(auth.oidc_issuer);
    case 'proxy':
      return 'Reverse proxy';
    case 'none':
      return 'Off';
  }
}

const PERSON_PREFIXES = new Set(['user', 'oidc', 'proxy']);

/**
 * `/me` `actor` for people: "user:admin" → "admin", "oidc:alice" → "alice", "proxy:bob" → "bob".
 * Sign-in off is "Local operator"; anything else (e.g. the bootstrap token's "bootstrap") shows as is.
 */
export function actorLabel(actor: string): string {
  if (actor === 'operator:local') return 'Local operator';
  const colon = actor.indexOf(':');
  return colon > 0 && PERSON_PREFIXES.has(actor.slice(0, colon)) ? actor.slice(colon + 1) : actor;
}

/** Settings → Sign-in (read-only, FR-15): how this server signs people in, who you are, Sign out. */
export function SignInCard({ auth }: SignInCardProps) {
  const navigate = useNavigate();
  const me = useMe();
  const logout = useLogout();
  return (
    <SectionCard title="Sign-in" icon="lock">
      <ul className="m-0 list-none p-0">
        <ListRow title="Method" value={methodLabel(auth)} />
        {me.data && <ListRow title="Signed in as" value={me.data.method === 'token' ? `${actorLabel(me.data.actor)} · API token` : actorLabel(me.data.actor)} />}
      </ul>
      {auth.mode === 'none' && (
        <Notice tone="warn">
          Sign-in is off.{' '}
          <a href={SIGN_IN_DOCS_URL} target="_blank" rel="noreferrer" className="font-semibold text-accent-text">
            How to turn on sign-in
          </a>
        </Notice>
      )}
      {logout.isError && (
        <Notice tone="bad" role="alert">
          {errorMessage(logout.error)}
        </Notice>
      )}
      {me.data?.method === 'session' && (
        <div>
          <Button
            variant="ghost"
            disabled={logout.isPending}
            onClick={() => logout.mutate(undefined, { onSuccess: () => navigate(SIGN_IN_PATH, { replace: true }) })}
          >
            Sign out
          </Button>
        </div>
      )}
    </SectionCard>
  );
}
