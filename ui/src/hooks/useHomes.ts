import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/endpoints';
import { DEVICE_POLL_MS, queryKeys } from '@/api/queryKeys';
import type { ClaimRequest } from '@/api/types';

/** The editable fields of a home. */
export interface HomeFields {
  name: string;
  timezone: string;
}

export function useHomes() {
  return useQuery({ queryKey: queryKeys.homes, queryFn: api.homes });
}

/** The home's devices, polled like the device page so cards show fresh sync state. */
export function useHomeDevices(homeId: number) {
  return useQuery({
    queryKey: queryKeys.homeDevices(homeId),
    queryFn: () => api.homeDevices(homeId),
    refetchInterval: DEVICE_POLL_MS,
    refetchIntervalInBackground: false,
  });
}

export function useUnclaimedDevices() {
  return useQuery({
    queryKey: queryKeys.unclaimed,
    queryFn: api.unclaimed,
    refetchInterval: DEVICE_POLL_MS,
    refetchIntervalInBackground: false,
  });
}

/** Creates a home (`homeId` null) or updates one; refreshes the home list. */
export function useSaveHome() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ homeId, body }: { homeId: number | null; body: HomeFields }) =>
      homeId === null ? api.createHome(body) : api.updateHome(homeId, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.homes }),
  });
}

/** Claims an unclaimed device into a home (FR-5); it starts with dispensing off. */
export function useClaimDevice() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ deviceId, body }: { deviceId: string; body: ClaimRequest }) => api.claim(deviceId, body),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.unclaimed }),
        queryClient.invalidateQueries({ queryKey: queryKeys.homes }),
      ]),
  });
}

export function useDeleteHome() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.deleteHome,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.homes }),
  });
}
