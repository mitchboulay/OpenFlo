import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useDebouncedCommit } from './useDebouncedCommit';

describe('useDebouncedCommit', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('commits only the last value once input pauses, then clears on done', () => {
    const commit = vi.fn();
    const { result } = renderHook(() => useDebouncedCommit<number>(commit, 600));
    act(() => result.current[1](180));
    act(() => vi.advanceTimersByTime(300));
    act(() => result.current[1](185));
    expect(result.current[0]).toBe(185);
    act(() => vi.advanceTimersByTime(599));
    expect(commit).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(1));
    expect(commit).toHaveBeenCalledTimes(1);
    expect(commit.mock.calls[0]?.[0]).toBe(185);
    act(() => (commit.mock.calls[0]?.[1] as () => void)());
    expect(result.current[0]).toBeNull();
  });
});
