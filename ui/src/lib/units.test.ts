import { describe, expect, it } from 'vitest';
import { defaultUnitForLocale, formatVolume, formatVolumeRange, fromDisplay, toDisplay } from './units';

describe('volume units', () => {
  it('formats one way everywhere: whole mL, oz to 0.1 below 10', () => {
    expect(formatVolume(177, 'ml')).toBe('177 mL');
    expect(formatVolume(177.4, 'ml')).toBe('177 mL');
    expect(formatVolume(177, 'oz')).toBe('6.0 oz');
    expect(formatVolume(816, 'oz')).toBe('28 oz');
    expect(formatVolumeRange(28, 816, 'ml')).toBe('28–816 mL');
    expect(formatVolumeRange(28, 816, 'oz')).toBe('0.9–28 oz');
  });

  it('converts between display units and mL', () => {
    expect(toDisplay(177, 'oz')).toBe(6);
    expect(fromDisplay(6, 'oz')).toBeCloseTo(177.44, 2);
    expect(fromDisplay(150, 'ml')).toBe(150);
  });

  it('defaults en-US to oz and everything else to mL', () => {
    expect(defaultUnitForLocale('en-US')).toBe('oz');
    expect(defaultUnitForLocale('en-GB')).toBe('ml');
    expect(defaultUnitForLocale('fr-CA')).toBe('ml');
    expect(defaultUnitForLocale(undefined)).toBe('ml');
  });
});
