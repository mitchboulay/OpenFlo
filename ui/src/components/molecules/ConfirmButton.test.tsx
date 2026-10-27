import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CONFIRM_WINDOW_MS, ConfirmButton } from './ConfirmButton';

function setup(onConfirm = vi.fn(), disabled = false) {
  const utils = render(
    <ConfirmButton
      label="Dispense now…"
      armedLabel="Tap again to dispense"
      onConfirm={onConfirm}
      disabled={disabled}
    />,
  );
  return { ...utils, onConfirm };
}

// fireEvent instead of userEvent: fake timers must control the 5 s window exactly.
describe('ConfirmButton', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('arms on the first click without confirming', () => {
    const { onConfirm } = setup();
    fireEvent.click(screen.getByRole('button', { name: 'Dispense now…' }));
    expect(screen.getByRole('button', { name: 'Tap again to dispense' })).toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('confirms on a second click within the window, then resets', () => {
    const { onConfirm } = setup();
    fireEvent.click(screen.getByRole('button'));
    act(() => vi.advanceTimersByTime(CONFIRM_WINDOW_MS - 1));
    fireEvent.click(screen.getByRole('button', { name: 'Tap again to dispense' }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: 'Dispense now…' })).toBeInTheDocument();
  });

  it('resets after 5 s, so a late second click only re-arms', () => {
    const { onConfirm } = setup();
    fireEvent.click(screen.getByRole('button'));
    act(() => vi.advanceTimersByTime(CONFIRM_WINDOW_MS));
    expect(screen.getByRole('button', { name: 'Dispense now…' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button'));
    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Tap again to dispense' })).toBeInTheDocument();
  });

  it('announces the armed state to screen readers', () => {
    setup();
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByText('Tap again to dispense', { selector: '[aria-live]' })).toBeInTheDocument();
  });

  it('never confirms while disabled', () => {
    const { onConfirm } = setup(vi.fn(), true);
    const button = screen.getByRole('button', { name: 'Dispense now…' });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
