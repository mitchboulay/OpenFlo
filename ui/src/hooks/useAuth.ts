import { useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { ApiToken } from '@/api/types';
import { useAction } from './useAction';

/** Who this browser is signed in as, and how. */
export function useMe() {
  return useQuery({ queryKey: queryKeys.me, queryFn: api.me });
}

/** Basic sign-in. Not a mutation: the password must not linger in the mutation cache. */
export function useLogin() {
  return useAction(api.login);
}

/** Basic mode's first admin (setup step 1). Same rule as sign-in for the password. */
export function useCreateAdmin() {
  return useAction(api.createAdmin);
}

/**
 * Ends the session. The cached responses that belonged to it are dropped by the sign-in page, not here:
 * clearing while the current page is still mounted refetches its queries, and their 401s raced the
 * navigation to sign-in (landing on `/sign-in?next=…` instead).
 */
export function useLogout() {
  return useMutation({ mutationFn: api.logout });
}

/** On the sign-in page there is no session: forget every cached response except the public server info. */
export function useForgetSession(): void {
  const queryClient = useQueryClient();
  useEffect(() => {
    queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== queryKeys.serverInfo[0] });
    queryClient.getMutationCache().clear();
  }, [queryClient]);
}

export function useTokens() {
  return useQuery({ queryKey: queryKeys.tokens, queryFn: api.tokens });
}

/** Creates a token. Not a mutation: the response holds the plaintext token, kept by the caller only. */
export function useCreateToken() {
  return useAction(api.createToken);
}

export function useRevokeToken() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (token: ApiToken) => api.revokeToken(token.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.tokens }),
  });
}
