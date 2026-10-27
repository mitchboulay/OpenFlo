import type { components } from './schema';

/** Named aliases for the generated `/api/v1` schemas (the only source of API types). */
type Schemas = components['schemas'];

export type HomeSummary = Schemas['HomeSummary'];
export type Home = Schemas['Home'];
export type HomeCreate = Schemas['HomeCreate'];
export type HomeUpdate = Schemas['HomeUpdate'];
export type DeviceSummary = Schemas['DeviceSummary'];
export type DeviceDetail = Schemas['DeviceDetail'];
export type DeviceUpdate = Schemas['DeviceUpdate'];
export type UnclaimedDevice = Schemas['UnclaimedDevice'];
export type Controls = Schemas['Controls'];
export type ControlsUpdate = Schemas['ControlsUpdate'];
export type WakePreset = NonNullable<Controls['wake_preset']>;
export type PendingChange = Schemas['PendingChange'];
export type DispenseRequest = Schemas['DispenseRequest'];
export type Flag = Schemas['Flag'];
export type Profile = Schemas['Profile'];
export type ProfileCreate = Schemas['ProfileCreate'];
export type Dosing = Schemas['Dosing'];
export type DosingUpdate = Schemas['DosingUpdate'];
export type Bottle = Schemas['Bottle'];
export type BottleGuidance = Bottle['guidance'];
export type Battery = Schemas['Battery'];
export type History = Schemas['History'];
export type HistoryKind = History['kind'];
export type DispenseItem = Schemas['DispenseItem'];
export type EventItem = Schemas['EventItem'];
export type SyncItem = Schemas['SyncItem'];
export type Schedule = Schemas['Schedule'];
export type ScheduleRule = Schemas['Rule'];
export type ScheduleEntry = Schemas['Entry'];
export type RuleCreate = Schemas['RuleCreate'];
export type RuleKind = ScheduleRule['kind'];
export type ClaimRequest = Schemas['ClaimRequest'];
export type ProvisioningCreate = Schemas['ProvisioningCreate'];
/** Carries the one-time token: keep it in component state only, never in a query cache or storage. */
export type ProvisioningCreated = Schemas['ProvisioningCreated'];
export type ProvisioningStatus = Schemas['ProvisioningStatus'];
export type ProvisioningSession = Schemas['Session'];
export type SessionStatus = ProvisioningSession['status'];
export type ServerInfo = Schemas['ServerInfo'];
export type AuthMode = ServerInfo['auth']['mode'];
export type SetupStatus = Schemas['SetupStatus'];
export type AddressCheckResult = Schemas['AddressCheckResult'];
export type AddressCheckItem = Schemas['AddressCheckItem'];
export type CheckName = AddressCheckItem['check'];
export type CheckStatus = AddressCheckItem['status'];
export type AdminCreate = Schemas['AdminCreate'];
export type SetupComplete = Schemas['SetupComplete'];
export type ServerAddress = Schemas['ServerAddress'];
export type LoginRequest = Schemas['LoginRequest'];
export type Me = Schemas['Me'];
export type ApiToken = Schemas['Token'];
export type TokenCreate = Schemas['TokenCreate'];
/** Carries the plaintext API token: keep it in component state only, never in a query cache or storage. */
export type TokenCreated = Schemas['TokenCreated'];
