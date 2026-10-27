import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useLocation, useNavigate } from 'react-router';
import { ApiError } from '@/api/client';
import { SETUP_PATH, SIGN_IN_PATH, signInPath } from '@/lib/links';
import { patchServerInfo } from './useServer';

/**
 * Boot routing (v3): any 401 from a query or mutation goes to sign-in with `?next=`, and a
 * `SETUP_REQUIRED` marks setup as required so the gate shows the wizard. Mount once, at the root.
 */
export function useAuthRedirects(): void {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const here = useRef(location);
  here.current = location;

  useEffect(() => {
    const onError = (error: unknown) => {
      if (!(error instanceof ApiError)) return;
      if (error.code === 'SETUP_REQUIRED') {
        patchServerInfo(queryClient, { setup_state: 'setup_required' });
        return;
      }
      const { pathname, search } = here.current;
      if (error.status === 401 && pathname !== SIGN_IN_PATH && pathname !== SETUP_PATH) {
        navigate(signInPath(pathname + search), { replace: true });
      }
    };
    const stopQueries = queryClient.getQueryCache().subscribe((event) => {
      if (event.type === 'updated' && event.action.type === 'error') onError(event.action.error);
    });
    const stopMutations = queryClient.getMutationCache().subscribe((event) => {
      if (event.type === 'updated' && event.action.type === 'error') onError(event.action.error);
    });
    return () => {
      stopQueries();
      stopMutations();
    };
  }, [queryClient, navigate]);
}
