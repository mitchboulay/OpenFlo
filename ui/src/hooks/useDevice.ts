import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/endpoints';
import { DEVICE_POLL_MS, queryKeys } from '@/api/queryKeys';
import type { HistoryKind } from '@/api/types';

/** The device detail, polled every 10 s while the tab is visible (FR-14 sync honesty). */
export function useDevice(deviceId: string) {
  return useQuery({
    queryKey: queryKeys.device(deviceId),
    queryFn: () => api.device(deviceId),
    refetchInterval: DEVICE_POLL_MS,
    refetchIntervalInBackground: false,
  });
}

/**
 * A mutation on one device. On success it refetches the device (and the home lists), so the UI
 * only ever shows what the server reports: nothing is marked applied optimistically.
 */
export function useDeviceAction<TVariables, TResult>(
  deviceId: string,
  mutationFn: (variables: TVariables) => Promise<TResult>,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.device(deviceId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.homes }),
      ]),
  });
}

/**
 * Rules and the upcoming doses. Polled with the device, because an entry flips from "Waiting for device" to
 * "On device" only when the device syncs; rule edits refresh it through `useDeviceAction`'s device prefix.
 */
export function useSchedule(deviceId: string) {
  return useQuery({
    queryKey: queryKeys.schedule(deviceId),
    queryFn: () => api.schedule(deviceId),
    refetchInterval: DEVICE_POLL_MS,
    refetchIntervalInBackground: false,
  });
}

export function useBattery(deviceId: string) {
  return useQuery({ queryKey: queryKeys.battery(deviceId), queryFn: () => api.battery(deviceId) });
}

/** One history list, newest first, paged with the API's `before_id` cursor. */
export function useDeviceHistory(deviceId: string, kind: HistoryKind) {
  return useInfiniteQuery({
    queryKey: queryKeys.history(deviceId, kind),
    queryFn: ({ pageParam }) => api.history(deviceId, kind, pageParam),
    initialPageParam: null as number | null,
    getNextPageParam: (page) => page.next_before_id,
  });
}

/** System liquids plus the home's own. */
export function useLiquidProfiles(homeId: number | null) {
  return useQuery({ queryKey: queryKeys.profiles(homeId), queryFn: () => api.profiles(homeId) });
}
