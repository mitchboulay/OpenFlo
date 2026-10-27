import type {
  AddressCheckResult,
  ApiToken,
  AuthMode,
  CheckName,
  CheckStatus,
  DeviceDetail,
  Dosing,
  HomeSummary,
  ServerInfo,
} from '@/api/types';

export const SERVER_ADDRESS = 'https://openflo.example.com';

export function makeServerInfo(mode: AuthMode = 'basic', overrides: Partial<ServerInfo> = {}): ServerInfo {
  return {
    name: 'OpenFLO',
    version: '0.4.0',
    api_version: '1',
    instance_id: 'inst-1',
    setup_state: 'ready',
    auth: {
      mode,
      methods: [mode === 'basic' ? 'password' : mode, 'token'],
      oidc_issuer: mode === 'oidc' ? 'https://auth.example.com/application/o/openflo/' : null,
      oidc_client_id: mode === 'oidc' ? 'openflo' : null,
    },
    server_address: SERVER_ADDRESS,
    ...overrides,
  };
}

const RAW_DETAIL: Record<CheckStatus, string> = { ok: 'fine', warn: 'raw warning detail', fail: 'raw failure detail' };

/** A check result; every check is ok unless named in `statuses`. */
export function makeCheckResult(
  statuses: Partial<Record<CheckName, CheckStatus>> = {},
  address = SERVER_ADDRESS,
): AddressCheckResult {
  const names: CheckName[] = ['dns', 'tls_no_sni', 'chain_firmware_bundle', 'leaf_rsa', 'healthcheck_reachable', 'port_non_443'];
  return {
    address,
    at: new Date(Date.now() - 5 * 60_000).toISOString(),
    checks: names.map((check) => {
      const status = statuses[check] ?? 'ok';
      return { check, status, detail: `${check}: ${RAW_DETAIL[status]}` };
    }),
  };
}

export function makeToken(overrides: Partial<ApiToken> = {}): ApiToken {
  return {
    id: 1,
    name: 'Home Assistant',
    kind: 'personal',
    created_at: '2026-10-20T12:00:00Z',
    expires_at: null,
    last_used_at: null,
    fingerprint: 'a1b2c3d4',
    ...overrides,
  };
}

export const DEVICE_ID = 'D8256700000A0001';
const HOUR_MS = 3_600_000;

/** An ISO instant `hours` from now (negative = in the past). */
export function hoursFromNow(hours: number): string {
  return new Date(Date.now() + hours * HOUR_MS).toISOString();
}

export const HOME: HomeSummary = {
  id: 1,
  name: 'Lab',
  timezone: 'America/New_York',
  created_at: '2026-10-26T20:00:00Z',
  device_count: 1,
  attention_count: 0,
  summary: 'ok',
};

export function makeDosing(overrides: Partial<Dosing> = {}): Dosing {
  return {
    profile: {
      id: 1,
      home_id: null,
      slug: 'standard',
      name: 'Standard',
      system: true,
      flow_full_ml_s: 27.2,
      capacity_ml: 1065,
      default_dose_ml: 177,
      calibrated: true,
    },
    dose_ml: 177,
    fixed_seconds: null,
    computed_seconds: 6.5,
    compensation_enabled: true,
    flow_scale: 1,
    capped_ml_when_low: null,
    warning: null,
    min_ml: 28,
    max_ml: 816,
    flow_ml_s: 27.2,
    calibrated: true,
    presets: { light_ml: 118, standard_ml: 177, strong_ml: 236 },
    ...overrides,
  };
}

/** A healthy, active device that last synced an hour ago and is due in five hours. */
export function makeDevice(overrides: Partial<DeviceDetail> = {}): DeviceDetail {
  return {
    device_id: DEVICE_ID,
    home_id: 1,
    name: 'Lab iFLO',
    location: 'Air handler, attic',
    status: 'active',
    retire_requested_at: null,
    installed_at: '2026-10-26T20:36:40Z',
    mac: '68:67:25:00:00:01',
    last_ip: '192.168.30.80',
    hardware_type: 'valve',
    pcb_version: '6.3.0',
    firmware_version: '3.0.64',
    network_name: 'OpenFLO',
    signal: 91,
    battery_level: 82,
    ext_power: false,
    first_seen: '2026-10-26T20:36:34Z',
    last_seen: hoursFromNow(-1),
    last_sync: hoursFromNow(-1),
    next_expected_sync: hoursFromNow(5),
    next_dose_at: null,
    pending: [],
    flags: [],
    controls: {
      dispensing_enabled: true,
      wake_preset: 'balanced',
      schedules_enabled: false,
      sync_interval_seconds: 21_600,
      shift_time_seconds: 900,
      updated_at: hoursFromNow(-2),
    },
    dosing: makeDosing(),
    bottle: {
      id: 1,
      capacity_ml: 1065,
      initial_fill_ml: 1065,
      started_at: '2026-10-26T20:00:00Z',
      est_remaining_ml: 708,
      est_doses_left: 4,
      est_days_left: null,
      guidance: 'ok',
    },
    remote_dispense: { pending: null, last_delivered: null },
    ...overrides,
  };
}
