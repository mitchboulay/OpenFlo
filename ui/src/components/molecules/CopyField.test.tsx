import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { COPIED_MS, CopyField } from './CopyField';

afterEach(() => vi.useRealTimers());

describe('CopyField', () => {
  it('copies the value and says "Copied" for 2 s', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<CopyField label="New token" value="ofl_secret" />);
    expect(screen.getByLabelText('New token')).toHaveTextContent('ofl_secret');

    await user.click(screen.getByRole('button', { name: 'Copy' }));
    expect(await navigator.clipboard.readText()).toBe('ofl_secret');
    expect(screen.getByRole('button', { name: 'Copied' })).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Copied to the clipboard.');

    act(() => vi.advanceTimersByTime(COPIED_MS));
    expect(screen.getByRole('button', { name: 'Copy' })).toBeInTheDocument();
  });

  it('says so when the clipboard refuses', async () => {
    const user = userEvent.setup();
    vi.spyOn(navigator.clipboard, 'writeText').mockRejectedValueOnce(new Error('denied'));
    render(<CopyField label="New token" value="ofl_secret" />);
    await user.click(screen.getByRole('button', { name: 'Copy' }));
    expect(await screen.findByText(/Couldn’t copy/)).toBeInTheDocument();
  });
});
