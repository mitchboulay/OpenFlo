import { describe, expect, it } from 'vitest';
import type { ProvisioningSession } from '@/api/types';
import { pairingOrigin, progressSteps, screenFor, wifiNetworkName } from './provisioning';

function session(status: ProvisioningSession['status']): ProvisioningSession {
  return {
    id: 7, home_id: 1, kind: 'new', target_device_id: null, device_name: 'Attic unit', location: null, status,
    bound_device_id: null, reset_mode: null, reset_result: null, created_at: '2026-10-26T12:00:00Z',
    expires_at: '2026-10-26T12:20:00Z', completed_at: null,
  };
}

describe('provisioning', () => {
  it('lets the server status pick the screen and the phone step split only awaiting_softap', () => {
    expect(screenFor(null, 'join')).toBe('details');
    expect(screenFor(session('awaiting_reset'), 'open')).toBe('reset');
    expect(screenFor(session('awaiting_softap'), 'join')).toBe('join');
    expect(screenFor(session('awaiting_softap'), 'open')).toBe('open');
    expect(screenFor(session('awaiting_softap'), 'waiting')).toBe('progress');
    expect(screenFor(session('awaiting_join'), 'join')).toBe('progress');
    expect(screenFor(session('completed'), 'join')).toBe('done');
    expect(screenFor(session('expired'), 'join')).toBe('expired');
    expect(screenFor(session('failed'), 'join')).toBe('expired');
    expect(screenFor(session('cancelled'), 'join')).toBe('cancelled');
  });

  it('derives live progress from the status', () => {
    expect(progressSteps('reset', 'awaiting_softap').map((step) => step.state)).toEqual(['done', 'active', 'pending']);
    expect(progressSteps('new', 'awaiting_join').map((step) => step.state)).toEqual(['done', 'active']);
    expect(progressSteps('new', 'completed').map((step) => step.state)).toEqual(['done', 'done']);
  });

  it('reads the network name from a WIFI: payload', () => {
    expect(wifiNetworkName('WIFI:T:WPA;S:iFLO device;P:13106423;;')).toBe('iFLO device');
    expect(wifiNetworkName('WIFI:S:a\\;b;T:WPA;;')).toBe('a;b');
    expect(wifiNetworkName('not wifi')).toBeNull();
  });

  it('shows the pairing address without the token', () => {
    expect(pairingOrigin('http://192.168.4.1/index.html?ott=abc&apiUrl=https://x&deviceType=0')).toBe('http://192.168.4.1');
  });
});
