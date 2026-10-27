import { api } from '@/api/endpoints';
import type { Dosing, DosingUpdate, Profile } from '@/api/types';
import { useDeviceAction } from './useDevice';

/** One dosing change: a new liquid, amount and/or compensation. Unset fields keep their current value. */
export interface DosingChange {
  profileId?: number;
  doseMl?: number;
  fixedSeconds?: number;
  compensation?: boolean;
}

/**
 * The full `PUT /dosing` body for `change` on top of `current`. The API takes exactly one of
 * `dose_ml` and `fixed_seconds`, so a change of amount replaces the other.
 */
export function dosingBody(current: Dosing, change: DosingChange): DosingUpdate {
  const amount =
    change.doseMl !== undefined
      ? { dose_ml: change.doseMl }
      : change.fixedSeconds !== undefined
        ? { fixed_seconds: change.fixedSeconds }
        : current.fixed_seconds !== null
          ? { fixed_seconds: current.fixed_seconds }
          : { dose_ml: current.dose_ml };
  return {
    profile_id: change.profileId ?? current.profile.id,
    ...amount,
    compensation_enabled: change.compensation ?? current.compensation_enabled,
  };
}

/** Switching liquid: a volume dose starts at the new liquid's usual dose; a fixed time stays as it is. */
export function liquidChange(current: Dosing, profile: Pick<Profile, 'id' | 'default_dose_ml'>): DosingChange {
  return current.fixed_seconds === null ? { profileId: profile.id, doseMl: profile.default_dose_ml } : { profileId: profile.id };
}

/** Sends a dosing change; the device page refetches, so every number shown is the API's. */
export function useSetDosing(deviceId: string, current: Dosing) {
  return useDeviceAction(deviceId, (change: DosingChange) => api.setDosing(deviceId, dosingBody(current, change)));
}
