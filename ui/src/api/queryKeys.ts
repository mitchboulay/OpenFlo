import type { HistoryKind } from './types';

/** TanStack Query keys. Prefixes nest so one invalidation refreshes everything under it. */
export const queryKeys = {
  serverInfo: ['server-info'] as const,
  setup: ['setup'] as const,
  addressCheck: ['address-check'] as const,
  me: ['me'] as const,
  tokens: ['tokens'] as const,
  homes: ['homes'] as const,
  homeDevices: (homeId: number) => ['homes', homeId, 'devices'] as const,
  unclaimed: ['devices', 'unclaimed'] as const,
  device: (deviceId: string) => ['device', deviceId] as const,
  schedule: (deviceId: string) => ['device', deviceId, 'schedule'] as const,
  battery: (deviceId: string) => ['device', deviceId, 'battery'] as const,
  history: (deviceId: string, kind: HistoryKind) => ['device', deviceId, 'history', kind] as const,
  profiles: (homeId: number | null) => ['liquid-profiles', homeId] as const,
  provisioning: (sessionId: number) => ['provisioning', sessionId] as const,
};

/** Device status changes on its own (syncs), so detail views poll; paused while the tab is hidden. */
export const DEVICE_POLL_MS = 10_000;

/** The wizard's live progress (FR-4): the device moves on its own, so the session is polled fast. */
export const PROVISIONING_POLL_MS = 2_000;
