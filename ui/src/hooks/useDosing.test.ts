import { describe, expect, it } from 'vitest';
import { makeDosing } from '@/test/fixtures';
import { dosingBody, liquidChange } from './useDosing';

describe('dosingBody', () => {
  it('keeps the current liquid, amount and compensation unless changed', () => {
    expect(dosingBody(makeDosing(), {})).toEqual({ profile_id: 1, dose_ml: 177, compensation_enabled: true });
    expect(dosingBody(makeDosing(), { compensation: false })).toEqual({ profile_id: 1, dose_ml: 177, compensation_enabled: false });
  });

  it('sends exactly one amount: a new one replaces the other kind', () => {
    const fixed = makeDosing({ dose_ml: null, fixed_seconds: 8 });
    expect(dosingBody(fixed, {})).toEqual({ profile_id: 1, fixed_seconds: 8, compensation_enabled: true });
    expect(dosingBody(fixed, { doseMl: 150 })).toEqual({ profile_id: 1, dose_ml: 150, compensation_enabled: true });
    expect(dosingBody(makeDosing(), { fixedSeconds: 6.5 })).toEqual({ profile_id: 1, fixed_seconds: 6.5, compensation_enabled: true });
  });

  it('switches liquid to its usual dose, or keeps a fixed time', () => {
    const vinegar = { id: 2, default_dose_ml: 120 };
    expect(dosingBody(makeDosing(), liquidChange(makeDosing(), vinegar))).toEqual({ profile_id: 2, dose_ml: 120, compensation_enabled: true });
    const fixed = makeDosing({ dose_ml: null, fixed_seconds: 8 });
    expect(dosingBody(fixed, liquidChange(fixed, vinegar))).toEqual({ profile_id: 2, fixed_seconds: 8, compensation_enabled: true });
  });
});
