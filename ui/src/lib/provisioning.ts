import type { DeviceDetail, ProvisioningSession, SessionStatus } from '@/api/types';
import type { StepListItem } from '@/components/molecules/StepList';

/** The wizard in reset kind for this device ("Move to a new network"); null when it can't be moved. */
export function moveNetworkPath(device: Pick<DeviceDetail, 'status' | 'home_id' | 'device_id'>): string | null {
  if (device.status !== 'active' || device.home_id === null) return null;
  return `/homes/${device.home_id}/add?device=${encodeURIComponent(device.device_id)}`;
}

/** Client-side position inside the server's `awaiting_softap`: which phone screen is showing. */
export type PhoneStep = 'join' | 'open' | 'waiting';

/** Every screen the add-device wizard can show. */
export type WizardScreen =
  | 'details'
  | 'reset'
  | 'join'
  | 'open'
  | 'progress'
  | 'done'
  | 'expired'
  | 'cancelled';

const OPEN_STATUSES: ReadonlySet<SessionStatus> = new Set(['awaiting_reset', 'awaiting_softap', 'awaiting_join']);

export function isOpenSession(status: SessionStatus): boolean {
  return OPEN_STATUSES.has(status);
}

/** The screen for a session: the server's status decides, the phone sub-step only splits `awaiting_softap`. */
export function screenFor(session: ProvisioningSession | null, phone: PhoneStep): WizardScreen {
  if (!session) return 'details';
  switch (session.status) {
    case 'awaiting_reset':
      return 'reset';
    case 'awaiting_softap':
      return phone === 'waiting' ? 'progress' : phone;
    case 'awaiting_join':
      return 'progress';
    case 'completed':
      return 'done';
    case 'cancelled':
      return 'cancelled';
    case 'expired':
    case 'failed':
      return 'expired';
  }
}

/** The numbered screens (step dots), in order; end states other than `done` carry no number. */
export function numberedScreens(kind: ProvisioningSession['kind']): WizardScreen[] {
  return kind === 'reset' ? ['details', 'reset', 'join', 'open', 'progress', 'done'] : ['details', 'join', 'open', 'progress', 'done'];
}

/**
 * Live progress from the session status (FR-4: waiting for reset → waiting for hotspot → device found →
 * registering → done). The server cannot see the phone, so "found" is the first thing it can confirm.
 */
export function progressSteps(kind: ProvisioningSession['kind'], status: SessionStatus): StepListItem[] {
  const order: SessionStatus[] = ['awaiting_reset', 'awaiting_softap', 'awaiting_join', 'completed'];
  const at = order.indexOf(status);
  const state = (stage: number): StepListItem['state'] => (at > stage ? 'done' : at === stage ? 'active' : 'pending');
  const steps: StepListItem[] = [
    { label: 'Found on your network', state: state(1) },
    { label: 'Registered', state: state(2) },
  ];
  return kind === 'reset' ? [{ label: 'Reset', state: state(0) }, ...steps] : steps;
}

/** The network name inside a `WIFI:` QR payload (`S:` field, with `\;`-style escapes undone). */
export function wifiNetworkName(wifiQr: string): string | null {
  const match = /(?:^WIFI:|;)S:((?:\\.|[^;\\])*)/.exec(wifiQr);
  return match?.[1] ? match[1].replace(/\\(.)/g, '$1') : null;
}

/** The pairing link's address without its query, so the one-time token never reaches the page text. */
export function pairingOrigin(pairingUrl: string): string {
  try {
    return new URL(pairingUrl).origin;
  } catch {
    return 'the setup page';
  }
}
