import { useCallback, useSyncExternalStore } from 'react';
import { defaultUnitForLocale, type VolumeUnit } from '@/lib/units';

export const UNITS_STORAGE_KEY = 'openflo.units';
const CHANGE_EVENT = 'openflo:units';

function readOverride(): VolumeUnit | null {
  try {
    const stored = window.localStorage.getItem(UNITS_STORAGE_KEY);
    return stored === 'ml' || stored === 'oz' ? stored : null;
  } catch {
    return null; // storage blocked (private mode, policy): fall back to the locale default
  }
}

function currentUnit(): VolumeUnit {
  return readOverride() ?? defaultUnitForLocale(navigator.language);
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener(CHANGE_EVENT, onChange);
  window.addEventListener('storage', onChange);
  return () => {
    window.removeEventListener(CHANGE_EVENT, onChange);
    window.removeEventListener('storage', onChange);
  };
}

/**
 * The app-wide volume unit (critique-v2 #5): the locale default (en-US → oz, else mL) unless the
 * user picked one in Settings, which is kept in localStorage. Every mounted user updates together.
 */
export function useUnits(): { unit: VolumeUnit; setUnit: (unit: VolumeUnit) => void } {
  const unit = useSyncExternalStore(subscribe, currentUnit);
  const setUnit = useCallback((next: VolumeUnit) => {
    try {
      window.localStorage.setItem(UNITS_STORAGE_KEY, next);
    } catch {
      return; // not persisted; the locale default stays in effect
    }
    window.dispatchEvent(new Event(CHANGE_EVENT));
  }, []);
  return { unit, setUnit };
}
