import type { BottleGuidance, DeviceDetail, DeviceSummary } from '@/api/types';
import type { Tone } from '@/types/tone';
import { formatWhen, zoneLabel } from './time';

/** A device counts as offline once it is this late for its expected check-in. */
export const OFFLINE_GRACE_MS = 60 * 60 * 1000;
export const LOW_BATTERY_PERCENT = 20;

/** Refill guidance (FR-8) as a label and tone. Guidance is advisory: it never blocks dispensing. */
export const GUIDANCE: Record<BottleGuidance, { label: string; tone: Tone }> = {
  ok: { label: 'OK', tone: 'ok' },
  refill_soon: { label: 'Refill soon', tone: 'warn' },
  refill_now: { label: 'Refill now', tone: 'bad' },
  unknown: { label: 'Set the level', tone: 'warn' },
};

export type DeviceCondition =
  | 'retired'
  | 'retiring'
  | 'offline'
  | 'flagged'
  | 'paused'
  | 'refill_now'
  | 'refill_soon'
  | 'level_unknown'
  | 'battery_low'
  | 'ok';

export interface DeviceState {
  condition: DeviceCondition;
  tone: Tone;
  /** Short status for the pill, e.g. "Needs attention". */
  label: string;
}

interface StatusInput {
  status: DeviceDetail['status'];
  retiring: boolean;
  nextExpectedSync: string | null;
  flagged: boolean;
  dispensingPaused: boolean;
  guidance: BottleGuidance;
  battery: number | null;
}

export function isOffline(nextExpectedSync: string | null, now: Date): boolean {
  if (!nextExpectedSync) return false;
  return now.getTime() - new Date(nextExpectedSync).getTime() > OFFLINE_GRACE_MS;
}

const LABELS: Record<DeviceCondition, { tone: Tone; label: string }> = {
  retired: { tone: 'neutral', label: 'Retired' },
  retiring: { tone: 'neutral', label: 'Retiring' },
  offline: { tone: 'bad', label: 'Offline' },
  flagged: { tone: 'warn', label: 'Needs attention' },
  paused: { tone: 'neutral', label: 'Paused' },
  refill_now: { tone: 'warn', label: 'Needs attention' },
  refill_soon: { tone: 'warn', label: 'Needs attention' },
  level_unknown: { tone: 'warn', label: 'Needs attention' },
  battery_low: { tone: 'warn', label: 'Needs attention' },
  ok: { tone: 'ok', label: 'OK' },
};

/**
 * The one condition that matters most, by priority (critique-v2): offline › bottle low ›
 * level unknown › battery low › fine. Lifecycle (retired, retiring), an open identity flag and a
 * paused lock come first because they change what the device will do at all.
 */
function conditionOf(input: StatusInput, now: Date): DeviceCondition {
  if (input.status === 'retired') return 'retired';
  if (input.retiring) return 'retiring';
  if (isOffline(input.nextExpectedSync, now)) return 'offline';
  if (input.flagged) return 'flagged';
  if (input.dispensingPaused) return 'paused';
  if (input.guidance === 'refill_now') return 'refill_now';
  if (input.guidance === 'refill_soon') return 'refill_soon';
  if (input.guidance === 'unknown') return 'level_unknown';
  if (input.battery !== null && input.battery < LOW_BATTERY_PERCENT) return 'battery_low';
  return 'ok';
}

function stateOf(input: StatusInput, now: Date): DeviceState {
  const condition = conditionOf(input, now);
  return { condition, ...LABELS[condition] };
}

export function detailState(device: DeviceDetail, now: Date = new Date()): DeviceState {
  return stateOf(
    {
      status: device.status,
      retiring: device.retire_requested_at !== null,
      nextExpectedSync: device.next_expected_sync,
      flagged: device.flags.some((flag) => flag.acked_at === null),
      dispensingPaused: !device.controls.dispensing_enabled,
      guidance: device.bottle?.guidance ?? 'unknown',
      battery: device.battery_level,
    },
    now,
  );
}

/** Cards don't carry the lock state, so a paused device shows its other conditions. */
export function summaryState(device: DeviceSummary, now: Date = new Date()): DeviceState {
  return stateOf(
    {
      status: device.status,
      retiring: false,
      nextExpectedSync: device.next_expected_sync,
      flagged: device.flagged,
      dispensingPaused: false,
      guidance: device.bottle_guidance,
      battery: device.battery_level,
    },
    now,
  );
}

/** The device header's one-sentence headline. */
export function headline(device: DeviceDetail, condition: DeviceCondition, timeZone: string, now: Date = new Date()): string {
  switch (condition) {
    case 'retired':
      return 'This device is retired. It no longer gets doses or changes.';
    case 'retiring':
      return 'Waiting for the device to clear its schedule, then it’s retired.';
    case 'offline':
      return `We haven’t heard from it since ${formatWhen(device.last_seen, timeZone, now)}. It may need new batteries or be out of Wi-Fi range.`;
    case 'flagged':
      return 'Remote dispensing and schedules are on hold until you review the warning below.';
    case 'paused':
      return 'Dispensing is paused.';
    case 'refill_now':
      return 'The bottle is almost empty. Refill it now.';
    case 'refill_soon':
      return 'The bottle is running low. Refill soon.';
    case 'level_unknown':
      return 'Set the bottle level so we can tell you when to refill.';
    case 'battery_low':
      return 'The battery is getting weak. Replace it soon.';
    case 'ok': {
      const dose = formatWhen(device.next_dose_at, timeZone, now);
      if (dose) {
        const zone = zoneLabel(timeZone, now, 'shortGeneric');
        return `Everything’s fine. Next dose ${dose}${zone ? ` ${zone}` : ''}.`;
      }
      const next = formatWhen(device.next_expected_sync, timeZone, now);
      return next ? `Everything’s fine. Next check-in around ${next}.` : 'Everything’s fine.';
    }
  }
}
