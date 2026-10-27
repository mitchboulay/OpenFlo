import { apiRequest } from './client';
import type {
  AddressCheckResult,
  AdminCreate,
  ApiToken,
  Battery,
  ClaimRequest,
  Bottle,
  ControlsUpdate,
  Controls,
  DeviceDetail,
  DeviceSummary,
  DeviceUpdate,
  DispenseRequest,
  Dosing,
  DosingUpdate,
  Flag,
  History,
  HistoryKind,
  Home,
  HomeCreate,
  HomeSummary,
  HomeUpdate,
  LoginRequest,
  Me,
  Profile,
  ProfileCreate,
  ProvisioningCreate,
  ProvisioningCreated,
  ProvisioningSession,
  ProvisioningStatus,
  RuleCreate,
  Schedule,
  ScheduleRule,
  ServerAddress,
  ServerInfo,
  SetupComplete,
  SetupStatus,
  TokenCreate,
  TokenCreated,
  UnclaimedDevice,
} from './types';

const V1 = '/api/v1';

/** `reset` sends the factory reset over the LAN; `manual-reset` records that the button was held. */
export type ProvisioningAction = 'reset' | 'manual-reset' | 'cancel';
const id = encodeURIComponent;

/** Typed `/api/v1` calls, one per endpoint the UI uses. Paths and shapes follow `schema.d.ts`. */
export const api = {
  // Cacheable for other clients (60 s); the SPA boots from it, so it always revalidates.
  serverInfo: () => apiRequest<ServerInfo>(`${V1}/server-info`, { cache: 'no-cache' }),
  setup: () => apiRequest<SetupStatus>(`${V1}/setup`),
  createAdmin: (body: AdminCreate) => apiRequest<void>(`${V1}/setup/admin`, { method: 'POST', body }),
  completeSetup: () => apiRequest<SetupComplete>(`${V1}/setup/complete`, { method: 'POST' }),
  saveServerAddress: (serverAddress: string) =>
    apiRequest<ServerAddress>(`${V1}/settings/server-address`, { method: 'PUT', body: { server_address: serverAddress } }),
  lastAddressCheck: () => apiRequest<AddressCheckResult>(`${V1}/settings/server-address/check`),
  // Six network checks of up to 5 s each, run concurrently; leave room for a slow resolver.
  runAddressCheck: () =>
    apiRequest<AddressCheckResult>(`${V1}/settings/server-address/check`, { method: 'POST', timeoutMs: 30_000 }),

  login: (body: LoginRequest) => apiRequest<void>(`${V1}/auth/login`, { method: 'POST', body }),
  logout: () => apiRequest<void>(`${V1}/auth/logout`, { method: 'POST' }),
  me: () => apiRequest<Me>(`${V1}/me`),
  tokens: () => apiRequest<ApiToken[]>(`${V1}/tokens`),
  createToken: (body: TokenCreate) => apiRequest<TokenCreated>(`${V1}/tokens`, { method: 'POST', body }),
  revokeToken: (tokenId: number) => apiRequest<void>(`${V1}/tokens/${tokenId}`, { method: 'DELETE' }),

  homes: () => apiRequest<HomeSummary[]>(`${V1}/homes`),
  createHome: (body: HomeCreate) => apiRequest<Home>(`${V1}/homes`, { method: 'POST', body }),
  updateHome: (homeId: number, body: HomeUpdate) =>
    apiRequest<Home>(`${V1}/homes/${homeId}`, { method: 'PATCH', body }),
  deleteHome: (homeId: number) => apiRequest<void>(`${V1}/homes/${homeId}`, { method: 'DELETE' }),
  homeDevices: (homeId: number) => apiRequest<DeviceSummary[]>(`${V1}/homes/${homeId}/devices`),
  unclaimed: () => apiRequest<UnclaimedDevice[]>(`${V1}/devices/unclaimed`),
  claim: (deviceId: string, body: ClaimRequest) =>
    apiRequest<DeviceDetail>(`${V1}/devices/${id(deviceId)}/claim`, { method: 'POST', body }),

  createProvisioning: (body: ProvisioningCreate) =>
    apiRequest<ProvisioningCreated>(`${V1}/provisioning`, { method: 'POST', body }),
  provisioning: (sessionId: number) => apiRequest<ProvisioningStatus>(`${V1}/provisioning/${sessionId}`),
  provisioningAction: (sessionId: number, action: ProvisioningAction) =>
    apiRequest<ProvisioningSession>(`${V1}/provisioning/${sessionId}/${action}`, { method: 'POST' }),

  device: (deviceId: string) => apiRequest<DeviceDetail>(`${V1}/devices/${id(deviceId)}`),
  updateDevice: (deviceId: string, body: DeviceUpdate) =>
    apiRequest<DeviceDetail>(`${V1}/devices/${id(deviceId)}`, { method: 'PATCH', body }),
  retire: (deviceId: string, force: boolean) =>
    apiRequest<DeviceDetail>(`${V1}/devices/${id(deviceId)}/retire`, { method: 'POST', body: { force } }),
  updateControls: (deviceId: string, body: ControlsUpdate) =>
    apiRequest<Controls>(`${V1}/devices/${id(deviceId)}/controls`, { method: 'PATCH', body }),
  queueDispense: (deviceId: string) =>
    apiRequest<DispenseRequest>(`${V1}/devices/${id(deviceId)}/dispense`, { method: 'POST' }),
  cancelDispense: (deviceId: string) =>
    apiRequest<DispenseRequest>(`${V1}/devices/${id(deviceId)}/dispense`, { method: 'DELETE' }),
  ackFlag: (flagId: number) => apiRequest<Flag>(`${V1}/flags/${flagId}/ack`, { method: 'POST' }),

  profiles: (homeId: number | null) =>
    apiRequest<Profile[]>(`${V1}/liquid-profiles${homeId === null ? '' : `?home_id=${homeId}`}`),
  createProfile: (homeId: number, body: ProfileCreate) =>
    apiRequest<Profile>(`${V1}/homes/${homeId}/liquid-profiles`, { method: 'POST', body }),
  setDosing: (deviceId: string, body: DosingUpdate) =>
    apiRequest<Dosing>(`${V1}/devices/${id(deviceId)}/dosing`, { method: 'PUT', body }),
  calibrate: (deviceId: string, measuredMl: number) =>
    apiRequest<Dosing>(`${V1}/devices/${id(deviceId)}/dosing/calibration`, {
      method: 'POST',
      body: { measured_ml: measuredMl },
    }),
  newBottle: (deviceId: string, fillMl: number | null) =>
    apiRequest<Bottle>(`${V1}/devices/${id(deviceId)}/bottles`, {
      method: 'POST',
      body: fillMl === null ? { fill: 'full' } : { fill: 'set', fill_ml: fillMl },
    }),
  adjustFill: (deviceId: string, fillMl: number) =>
    apiRequest<Bottle>(`${V1}/devices/${id(deviceId)}/bottles/current/adjust`, {
      method: 'POST',
      body: { fill_ml: fillMl },
    }),

  schedule: (deviceId: string) => apiRequest<Schedule>(`${V1}/devices/${id(deviceId)}/schedule`),
  createRule: (deviceId: string, body: RuleCreate) =>
    apiRequest<ScheduleRule>(`${V1}/devices/${id(deviceId)}/schedule/rules`, { method: 'POST', body }),
  /** A full replacement of the rule's shape: the body carries every field its kind takes. */
  updateRule: (ruleId: number, body: RuleCreate) =>
    apiRequest<ScheduleRule>(`${V1}/schedule/rules/${ruleId}`, { method: 'PATCH', body }),
  deleteRule: (ruleId: number) => apiRequest<void>(`${V1}/schedule/rules/${ruleId}`, { method: 'DELETE' }),

  battery: (deviceId: string) => apiRequest<Battery>(`${V1}/devices/${id(deviceId)}/battery?days=30`),
  history: (deviceId: string, kind: HistoryKind, beforeId: number | null) =>
    apiRequest<History>(
      `${V1}/devices/${id(deviceId)}/history?kind=${kind}&limit=20${beforeId === null ? '' : `&before_id=${beforeId}`}`,
    ),
};
