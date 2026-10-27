import { delay, http, HttpResponse } from 'msw';
import type { AddressCheckResult, ApiToken, AuthMode, CheckName, CheckStatus, Me, SetupStatus } from '@/api/types';
import { HOME, makeCheckResult, makeServerInfo, makeToken, SERVER_ADDRESS } from './fixtures';

export const ADMIN = { username: 'admin', password: 'correct horse battery' };
/** The plaintext this fake hands out for a new API token, so tests can prove it is never retained. */
export const FAKE_API_TOKEN = 'ofl_7e57t0ken7e57t0ken7e57';

export interface FakeAuthOptions {
  mode?: AuthMode;
  setupRequired?: boolean;
  /** Basic: an admin already exists (setup resumed). */
  adminExists?: boolean;
  /** OIDC: the identity provider's discovery answers. */
  oidcReachable?: boolean;
  /** Basic/OIDC: a session cookie is already set. */
  signedIn?: boolean;
  address?: string | null;
  /** The statuses the next address checks return; `error` makes the request itself fail. */
  checks?: Partial<Record<CheckName, CheckStatus>> | 'error';
  /** The stored check, as `GET …/check` returns it. */
  lastCheck?: AddressCheckResult | null;
  tokens?: ApiToken[];
  /** Answer sign-in with 429 RATE_LIMITED. */
  rateLimited?: boolean;
  /** Hold every address check until `releaseCheck()`, so a test can see the "Checking…" state without racing it. */
  holdCheck?: boolean;
}

const V1 = '*/api/v1';
const error = (status: number, code: string, message: string, detail?: unknown) =>
  HttpResponse.json({ code, message, detail }, { status });

/** An in-memory `/api/v1` for setup, sign-in and Settings (B2.1/B2.2 contract), for Vitest + msw. */
export function createFakeAuthBackend(options: FakeAuthOptions = {}) {
  let releaseCheck = () => {};
  const checkGate = options.holdCheck ? new Promise<void>((resolve) => (releaseCheck = resolve)) : null;
  const mode = options.mode ?? 'basic';
  const state = {
    setupState: options.setupRequired ? ('setup_required' as const) : ('ready' as const),
    admin: options.adminExists ?? !options.setupRequired,
    signedIn: options.signedIn ?? false,
    address: options.address === undefined ? SERVER_ADDRESS : options.address,
    lastCheck: options.lastCheck ?? null,
    tokens: options.tokens ?? [],
    requests: [] as string[],
  };
  const authed = () => mode === 'none' || state.signedIn;
  const guard = () => (state.setupState === 'setup_required' ? error(409, 'SETUP_REQUIRED', 'finish setup') : authed() ? null : error(401, 'AUTH_REQUIRED', 'sign in'));
  const verdict = (): SetupStatus['steps']['address_check'] => {
    if (!state.lastCheck || state.lastCheck.address !== state.address) return 'pending';
    const statuses = state.lastCheck.checks.map((item) => item.status);
    return statuses.includes('fail') ? 'fail' : statuses.includes('warn') ? 'warn' : 'ok';
  };
  const me = (): Me => ({ actor: mode === 'none' ? 'operator:local' : `user:${ADMIN.username}`, auth_mode: mode, method: mode === 'none' ? 'none' : 'session' });

  const handlers = [
    http.get(`${V1}/server-info`, () =>
      HttpResponse.json(makeServerInfo(mode, { setup_state: state.setupState, server_address: state.address })),
    ),
    http.get(`${V1}/setup`, () =>
      HttpResponse.json<SetupStatus>({
        setup_state: state.setupState,
        steps: {
          auth: mode === 'basic' ? (state.admin ? 'done' : 'pending') : mode === 'oidc' && options.oidcReachable === false ? 'pending' : 'done',
          server_address: state.address ? 'done' : 'pending',
          address_check: verdict(),
        },
      }),
    ),
    http.post(`${V1}/setup/admin`, async ({ request }) => {
      const body = (await request.json()) as { username: string; password: string };
      state.requests.push('create admin');
      if (state.admin) return error(409, 'ALREADY_SET', 'an admin exists');
      if (body.password.length < 12) return error(422, 'WEAK_PASSWORD', 'at least 12 characters');
      state.admin = true;
      state.signedIn = true; // the API signs the new admin in
      return new HttpResponse(null, { status: 204 });
    }),
    http.put(`${V1}/settings/server-address`, async ({ request }) => {
      state.address = ((await request.json()) as { server_address: string }).server_address;
      state.requests.push(`save ${state.address}`);
      return HttpResponse.json({ server_address: state.address });
    }),
    http.get(`${V1}/settings/server-address/check`, () =>
      state.lastCheck ? HttpResponse.json(state.lastCheck) : error(404, 'NOT_CHECKED', 'not checked yet'),
    ),
    http.post(`${V1}/settings/server-address/check`, async () => {
      state.requests.push('check');
      await (checkGate ?? delay(30));
      if (options.checks === 'error') return HttpResponse.error();
      state.lastCheck = { ...makeCheckResult(options.checks, state.address ?? SERVER_ADDRESS), at: new Date().toISOString() };
      return HttpResponse.json(state.lastCheck);
    }),
    http.post(`${V1}/setup/complete`, () => {
      state.requests.push('complete');
      state.setupState = 'ready';
      return HttpResponse.json({ setup_state: 'ready' });
    }),
    http.post(`${V1}/auth/login`, async ({ request }) => {
      const body = (await request.json()) as { username: string; password: string };
      state.requests.push('login');
      if (options.rateLimited) return error(429, 'RATE_LIMITED', 'too many attempts', { retry_after_seconds: 42 });
      if (body.username !== ADMIN.username || body.password !== ADMIN.password) return error(401, 'INVALID_CREDENTIALS', 'wrong username or password');
      state.signedIn = true;
      return new HttpResponse(null, { status: 204 });
    }),
    http.post(`${V1}/auth/logout`, () => {
      state.requests.push('logout');
      state.signedIn = false;
      return new HttpResponse(null, { status: 204 });
    }),
    http.get(`${V1}/me`, () => guard() ?? HttpResponse.json(me())),
    http.get(`${V1}/homes`, () => guard() ?? HttpResponse.json([HOME])),
    http.get(`${V1}/tokens`, () => guard() ?? HttpResponse.json(state.tokens)),
    http.post(`${V1}/tokens`, async ({ request }) => {
      const { name } = (await request.json()) as { name: string };
      const token = makeToken({ id: state.tokens.length + 100, name, fingerprint: 'f00dfeed' });
      state.tokens = [token, ...state.tokens];
      state.requests.push(`create token ${name}`);
      return HttpResponse.json({ ...token, token: FAKE_API_TOKEN }, { status: 201 });
    }),
    http.delete(`${V1}/tokens/:tokenId`, ({ params }) => {
      state.tokens = state.tokens.filter((token) => token.id !== Number(params.tokenId));
      state.requests.push(`revoke ${String(params.tokenId)}`);
      return new HttpResponse(null, { status: 204 });
    }),
  ];

  return { handlers, state, releaseCheck: () => releaseCheck() };
}
