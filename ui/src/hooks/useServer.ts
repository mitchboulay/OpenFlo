import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';
import { ApiError } from '@/api/client';
import { api } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { AddressCheckResult, ServerInfo } from '@/api/types';

/** Boot data (FR-17): setup state, sign-in mode, address, version. Changes only through this app. */
export function useServerInfo() {
  return useQuery({ queryKey: queryKeys.serverInfo, queryFn: api.serverInfo, staleTime: Infinity });
}

/** Patches the cached server info after this app changed it (setup state, address); no refetch needed. */
export function patchServerInfo(queryClient: QueryClient, patch: Partial<ServerInfo>): void {
  queryClient.setQueryData<ServerInfo>(queryKeys.serverInfo, (info) => info && { ...info, ...patch });
}

/** The wizard's step states (FR-16). */
export function useSetupStatus() {
  return useQuery({ queryKey: queryKeys.setup, queryFn: api.setup });
}

/**
 * `setup_required → ready`. The caller patches the server info itself, in the same tick as it
 * navigates away from `/setup`, so the boot gate never redirects first.
 */
export function useCompleteSetup() {
  return useMutation({ mutationFn: api.completeSetup });
}

/** The last stored address check; null before the first one (404 `NOT_CHECKED`). */
export function useAddressCheck() {
  return useQuery({
    queryKey: queryKeys.addressCheck,
    queryFn: async (): Promise<AddressCheckResult | null> => {
      try {
        return await api.lastAddressCheck();
      } catch (error) {
        if (error instanceof ApiError && error.code === 'NOT_CHECKED') return null;
        throw error;
      }
    },
  });
}

/** Runs the six checks now; the result replaces the stored one. */
export function useRunAddressCheck() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.runAddressCheck,
    onSuccess: (result) => {
      queryClient.setQueryData(queryKeys.addressCheck, result);
      void queryClient.invalidateQueries({ queryKey: queryKeys.setup });
    },
  });
}

/** Saves the server address (normalized by the API) and clears the check made for the old one. */
export function useSaveServerAddress() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.saveServerAddress,
    onSuccess: ({ server_address }) => {
      patchServerInfo(queryClient, { server_address });
      void queryClient.invalidateQueries({ queryKey: queryKeys.setup });
    },
  });
}
