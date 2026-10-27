import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { UNITS_STORAGE_KEY, useUnits } from './useUnits';

afterEach(() => window.localStorage.clear());

describe('useUnits', () => {
  it('defaults from the browser locale', () => {
    vi.spyOn(navigator, 'language', 'get').mockReturnValue('de-DE');
    expect(renderHook(() => useUnits()).result.current.unit).toBe('ml');
    vi.spyOn(navigator, 'language', 'get').mockReturnValue('en-US');
    expect(renderHook(() => useUnits()).result.current.unit).toBe('oz');
  });

  it('keeps an override in localStorage and updates every user', () => {
    vi.spyOn(navigator, 'language', 'get').mockReturnValue('en-US');
    const first = renderHook(() => useUnits());
    const second = renderHook(() => useUnits());
    act(() => first.result.current.setUnit('ml'));
    expect(window.localStorage.getItem(UNITS_STORAGE_KEY)).toBe('ml');
    expect(first.result.current.unit).toBe('ml');
    expect(second.result.current.unit).toBe('ml');
  });

  it('falls back to the locale when storage is unavailable', () => {
    vi.spyOn(navigator, 'language', 'get').mockReturnValue('en-US');
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    const { result } = renderHook(() => useUnits());
    act(() => result.current.setUnit('ml'));
    expect(result.current.unit).toBe('oz');
  });
});
