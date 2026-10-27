import { ApiError, CLIENT_ERROR_CODES } from '@/api/client';

/** Friendly copy for API error codes the UI can hit. Anything else shows the server's message. */
const MESSAGES: Readonly<Record<string, string>> = {
  HOME_EXISTS: 'You already have a home with that name.',
  HOME_HAS_DEVICES: 'Move or retire this home’s devices before deleting it.',
  DISPENSING_LOCKED: 'Dispensing is paused. Resume it from the device menu first.',
  IDENTITY_FLAGGED: 'Review the device warning first. Remote dispensing is on hold until you do.',
  NO_OPEN_BOTTLE: 'There’s no bottle recorded yet. Tap “I put in a new bottle” first.',
  FILL_OUT_OF_RANGE: 'That’s more than the bottle holds.',
  CALIBRATION_IMPLAUSIBLE: 'That amount is too far from what we expected. Measure the cup again.',
  ADDRESS_UNVERIFIED: 'Your devices can’t reach this server’s address yet. Fix it in Settings, then add the device.',
  WIZARD_OPEN: 'A setup is already in progress in this home.',
  DEVICE_NOT_ACTIVE: 'Only an active device can be set up again.',
  SESSION_STATE: 'This setup has moved on. Refreshing…',
  LAN_RESET_UNAVAILABLE: 'The server can’t reach the device right now. Twist the bottle to wake it and try again, or hold its reset button.',
  NOT_UNCLAIMED: 'Someone already added this device.',
  DB_BUSY: 'Busy, try again.',
  SETUP_INCOMPLETE: 'A setup step isn’t finished yet. Go back and finish it.',
  ADDRESS_INVALID: 'Enter the full address, starting with https://',
  [CLIENT_ERROR_CODES.network]: 'Couldn’t reach your OpenFLO server.',
  [CLIENT_ERROR_CODES.timeout]: 'The server took too long to respond.',
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return MESSAGES[error.code] ?? error.message;
  return 'Something went wrong. Try again.';
}

export function errorCode(error: unknown): string | null {
  return error instanceof ApiError ? error.code : null;
}
