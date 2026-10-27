import { useCallback, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type ProvisioningAction } from '@/api/endpoints';
import { PROVISIONING_POLL_MS, queryKeys } from '@/api/queryKeys';
import type { ProvisioningCreate, ProvisioningCreated, ProvisioningStatus } from '@/api/types';
import { isOpenSession } from '@/lib/provisioning';

/**
 * Opens a session. Deliberately not a `useMutation`: the response carries the one-time token, and
 * TanStack's mutation cache would keep it after the wizard unmounts. The caller holds it in state.
 */
export function useStartProvisioning() {
  const queryClient = useQueryClient();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const start = useCallback(
    async (body: ProvisioningCreate): Promise<StartResult> => {
      setPending(true);
      setError(null);
      try {
        const created = await api.createProvisioning(body);
        // Seed the status (token-free) so the wizard moves on before the first poll.
        queryClient.setQueryData<ProvisioningStatus>(queryKeys.provisioning(created.session.id), {
          session: created.session,
          steps: [],
          next_expected_sync: null,
        });
        return { ok: true, created };
      } catch (caught) {
        setError(caught);
        return { ok: false, error: caught };
      } finally {
        setPending(false);
      }
    },
    [queryClient],
  );
  return { start, pending, error };
}

export type StartResult = { ok: true; created: ProvisioningCreated } | { ok: false; error: unknown };

/** The device a reset-kind wizard sets up again; shares the device page's cache entry. */
export function useResetTarget(deviceId: string | null) {
  return useQuery({
    queryKey: queryKeys.device(deviceId ?? ''),
    queryFn: () => api.device(deviceId as string),
    enabled: deviceId !== null,
  });
}

/** The session and its steps, polled every 2 s until it ends (FR-4 live progress). */
export function useProvisioningStatus(sessionId: number | null) {
  return useQuery({
    queryKey: queryKeys.provisioning(sessionId ?? -1),
    queryFn: () => api.provisioning(sessionId as number),
    enabled: sessionId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.session.status;
      return status && !isOpenSession(status) ? false : PROVISIONING_POLL_MS;
    },
    // The operator is on the phone's setup page meanwhile; keep following the device.
    refetchIntervalInBackground: true,
  });
}

/** Reset over the LAN, confirm a manual reset, or cancel. Either way the status is refetched. */
export function useProvisioningAction(sessionId: number | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (action: ProvisioningAction) => api.provisioningAction(sessionId as number, action),
    onSuccess: (session) =>
      queryClient.setQueryData<ProvisioningStatus>(queryKeys.provisioning(session.id), (previous) =>
        previous ? { ...previous, session } : previous,
      ),
    onSettled: () => queryClient.invalidateQueries({ queryKey: queryKeys.provisioning(sessionId ?? -1) }),
  });
}
