import type { EventItem } from '@/api/types';

/**
 * Plain names for firmware 3.0.64 events. `send-events` items carry `{status, code, timestamp}`:
 * status 0 resolves through the firmware's SE_* table, status 1 through EE_* (backend
 * `services/telemetry.py`). Only codes confirmed in research are named; the rest show their code.
 */
const SE_NAMES: Readonly<Record<number, string>> = {
  1: 'Dispensed a dose',
  2: 'Dispensed a dose',
  3: 'Dispensed a double dose',
  8: 'Dispensed on request', // SE_REMOTE_DISPENSE_OK
};

const EE_NAMES: Readonly<Record<number, string>> = {
  5: 'New bottle put in',
  6: 'Bottle removed',
};

/** Request kinds stored as event batches that are not `send-events`. */
const REQUEST_NAMES: Readonly<Record<string, string>> = {
  'get-fw': 'Checked for a firmware update',
  healthcheck: 'Checked the connection',
  'get-bottle': 'Checked the bottle',
};

export interface DeviceEventEntry {
  /** Stable React key. */
  key: string;
  name: string;
  /** Firmware code, e.g. "SE 8", shown as secondary text. */
  code: string | null;
  /** Device time (ISO) when reported, else the server receive time. */
  at: string;
}

interface RawEvent {
  status: number;
  code: number;
  timestamp: number | null;
}

function rawEvents(payload: unknown): RawEvent[] {
  if (typeof payload !== 'object' || payload === null) return [];
  const data = (payload as { data?: unknown }).data;
  if (!Array.isArray(data)) return [];
  return data.flatMap((item: unknown) => {
    if (typeof item !== 'object' || item === null) return [];
    const { status, code, timestamp } = item as Record<string, unknown>;
    if (typeof status !== 'number' || typeof code !== 'number') return [];
    return [{ status, code, timestamp: typeof timestamp === 'number' ? timestamp : null }];
  });
}

export function eventName(status: number, code: number): string {
  const table = status === 0 ? SE_NAMES : status === 1 ? EE_NAMES : {};
  return table[code] ?? 'Device event';
}

/** One event batch → its rows (a `send-events` batch may hold several events). */
export function describeEventBatch(item: EventItem): DeviceEventEntry[] {
  if (item.kind !== 'send-events') {
    return [{ key: `${item.id}`, name: REQUEST_NAMES[item.kind] ?? item.kind, code: null, at: item.received_at }];
  }
  const events = rawEvents(item.payload);
  if (events.length === 0) {
    return [{ key: `${item.id}`, name: 'Reported events', code: null, at: item.received_at }];
  }
  return events.map((event, index) => ({
    key: `${item.id}-${index}`,
    name: eventName(event.status, event.code),
    code: `${event.status === 0 ? 'SE' : event.status === 1 ? 'EE' : `status ${event.status}`} ${event.code}`,
    at: event.timestamp === null ? item.received_at : new Date(event.timestamp * 1000).toISOString(),
  }));
}

/** A dispense history row's kind, from its SE code. */
export function dispenseKind(code: number, doseCount: number): string {
  if (code === 8) return 'On request';
  return doseCount > 1 ? 'Double dose' : 'Dose';
}
