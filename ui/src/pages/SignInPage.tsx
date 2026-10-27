import { Navigate, useSearchParams } from 'react-router';
import { QueryBoundary } from '@/components/organisms/QueryBoundary';
import { SignInForm } from '@/components/organisms/SignInForm';
import { useForgetSession } from '@/hooks/useAuth';
import { useServerInfo } from '@/hooks/useServer';
import { safeNext } from '@/lib/links';

/** Route `/sign-in?next=`: where any 401 lands (FR-15). With sign-in off there is nothing to do here. */
export function SignInPage() {
  useForgetSession();
  const info = useServerInfo();
  const [search] = useSearchParams();
  const next = safeNext(search.get('next'));
  return (
    <QueryBoundary query={info} what="OpenFLO">
      {(data) =>
        data.auth.mode === 'none' ? <Navigate to={next} replace /> : <SignInForm info={data} next={next} returnError={search.get('error')} />
      }
    </QueryBoundary>
  );
}
