import { http, HttpResponse } from 'msw';
import type { ClaimRequest, ProvisioningCreate, ProvisioningSession, ProvisioningStatus, UnclaimedDevice } from '@/api/types';
import { DEVICE_ID, HOME, hoursFromNow, makeDevice, makeServerInfo } from '@/test/fixtures';

/** The one-time token this fake hands out, so tests can prove it is never persisted. */
export const FAKE_TOKEN = '5eed5eed5eed5eed5eed5eed';
export const NEW_DEVICE_ID = 'A1B2C3D4E5F60718';
export const UNCLAIMED: UnclaimedDevice = {
  device_id: 'AA00BB11CC22DD33',
  last_ip: '192.168.30.81',
  first_seen: hoursFromNow(-2),
  last_seen: hoursFromNow(-1),
};

export interface FakeBackendOptions {
  /** False answers `POST /provisioning` with 409 ADDRESS_UNVERIFIED. */
  addressVerified?: boolean;
  /** `lan`: the server may reset the target; `manual`: hold the button. */
  resetMode?: 'lan' | 'manual';
  /** The LAN reset is attempted but the device doesn't answer. */
  lanResetFails?: boolean;
}

const V1 = '*/api/v1';
const ADVANCE: Partial<Record<ProvisioningSession['status'], ProvisioningSession['status']>> = {
  awaiting_softap: 'awaiting_join',
  awaiting_join: 'completed',
};

const error = (status: number, code: string, message: string, detail?: unknown) =>
  HttpResponse.json({ code, message, detail }, { status });

/**
 * An in-memory `/api/v1` for the add-device wizard and claims (B2.3 contract). Drives the Vitest
 * integration tests and the msw-backed dev server; `advance()`/`expire()` stand in for the device.
 */
export function createFakeProvisioningBackend(options: FakeBackendOptions = {}) {
  const { addressVerified = true, resetMode = 'manual', lanResetFails = false } = options;
  let session: ProvisioningSession | null = null;
  let steps: ProvisioningStatus['steps'] = [];
  let unclaimed = [UNCLAIMED];
  const requests: string[] = [];

  const update = (changes: Partial<ProvisioningSession>, step?: string) => {
    if (!session) return;
    session = { ...session, ...changes };
    steps = [...steps, { step: step ?? session.status, at: new Date().toISOString(), detail: {} }];
  };
  const isOpen = () => session !== null && ['awaiting_reset', 'awaiting_softap', 'awaiting_join'].includes(session.status);
  const status = (): ProvisioningStatus | null =>
    session && { session, steps, next_expected_sync: session.kind === 'reset' ? hoursFromNow(1.5) : null };

  const handlers = [
    http.get(`${V1}/server-info`, () => HttpResponse.json(makeServerInfo())),
    http.get(`${V1}/homes`, () => HttpResponse.json([HOME])),
    http.get(`${V1}/homes/1/devices`, () => HttpResponse.json([])),
    http.get(`${V1}/devices/unclaimed`, () => HttpResponse.json(unclaimed)),
    http.get(`${V1}/devices/:deviceId`, ({ params }) =>
      HttpResponse.json(makeDevice({ device_id: String(params.deviceId), name: 'Attic unit', location: 'Air handler, attic' })),
    ),
    http.post(`${V1}/devices/:deviceId/claim`, async ({ params, request }) => {
      const body = (await request.json()) as ClaimRequest;
      requests.push(`claim ${String(params.deviceId)} ${JSON.stringify(body)}`);
      if (!unclaimed.some((device) => device.device_id === params.deviceId)) return error(409, 'NOT_UNCLAIMED', 'already claimed');
      unclaimed = unclaimed.filter((device) => device.device_id !== params.deviceId);
      return HttpResponse.json(makeDevice({ device_id: String(params.deviceId), name: body.name, location: body.location ?? null }));
    }),
    http.post(`${V1}/provisioning`, async ({ request }) => {
      const body = (await request.json()) as ProvisioningCreate;
      requests.push(`create ${body.kind}`);
      if (!addressVerified) return error(409, 'ADDRESS_UNVERIFIED', 'check the server address in Settings', { failed: ['tls_no_sni'] });
      if (isOpen()) return error(409, 'WIZARD_OPEN', 'this home already has an open provisioning wizard', { session_id: session?.id });
      const now = new Date();
      session = {
        id: (session?.id ?? 6) + 1, home_id: body.home_id, kind: body.kind, target_device_id: body.target_device_id ?? null,
        device_name: body.device_name, location: body.location ?? null,
        status: body.kind === 'reset' ? 'awaiting_reset' : 'awaiting_softap', bound_device_id: null,
        reset_mode: body.kind === 'reset' ? resetMode : null, reset_result: null, created_at: now.toISOString(),
        expires_at: new Date(now.getTime() + 20 * 60_000).toISOString(), completed_at: null,
      };
      steps = [{ step: session.status, at: now.toISOString(), detail: { kind: body.kind } }];
      return HttpResponse.json(
        {
          session,
          token: FAKE_TOKEN,
          pairing_url: `http://192.168.4.1/index.html?ott=${FAKE_TOKEN}&apiUrl=https://openflo.example.com&deviceType=0`,
          wifi_qr: 'WIFI:T:WPA;S:iFLO device;P:13106423;;',
        },
        { status: 201 },
      );
    }),
    http.get(`${V1}/provisioning/:sessionId`, ({ params }) => {
      const current = status();
      return current && current.session.id === Number(params.sessionId)
        ? HttpResponse.json(current)
        : error(404, 'NOT_FOUND', 'no such session');
    }),
    http.post(`${V1}/provisioning/:sessionId/:action`, ({ params }) => {
      const action = String(params.action);
      requests.push(action);
      if (!session || !isOpen()) return error(409, 'SESSION_STATE', 'session is not open');
      if (action === 'cancel') update({ status: 'cancelled' });
      else if (action === 'manual-reset') update({ status: 'awaiting_softap' }, 'manual_reset');
      else if (lanResetFails) update({ reset_result: 'failed: timeout', reset_mode: 'manual' }, 'reset_failed');
      else update({ status: 'awaiting_softap', reset_result: 'ok: 200' }, 'reset_sent');
      return HttpResponse.json(session);
    }),
  ];

  return {
    handlers,
    /** Requests that changed state, in order (e.g. "create new", "manual-reset", "cancel"). */
    requests,
    /** The device moves one stage: found on the network, then registered. */
    advance() {
      const next = session && ADVANCE[session.status];
      if (!session || !next) return;
      update(next === 'completed'
        ? { status: next, bound_device_id: session.target_device_id ?? NEW_DEVICE_ID, completed_at: new Date().toISOString() }
        : { status: next });
    },
    expire() {
      if (isOpen()) update({ status: 'expired' });
    },
    /** Pretend another tab opened a session in this home. */
    openElsewhere(kind: ProvisioningSession['kind'] = 'new') {
      const created = { home_id: HOME.id, kind, target_device_id: kind === 'reset' ? DEVICE_ID : null, device_name: 'Basement unit' };
      const now = new Date().toISOString();
      session = {
        ...created, id: 41, location: null, status: 'awaiting_softap', bound_device_id: null, reset_mode: null,
        reset_result: null, created_at: now, expires_at: hoursFromNow(0.3), completed_at: null,
      };
      steps = [{ step: 'awaiting_softap', at: now, detail: {} }];
    },
  };
}
