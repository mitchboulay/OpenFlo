import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { DayPicker } from './DayPicker';

describe('DayPicker', () => {
  it('names each day, Sunday first, and marks the selected ones', () => {
    render(<DayPicker mask={0b100_0001} onChange={() => undefined} />);
    const days = screen.getAllByRole('button');
    expect(days.map((day) => day.getAttribute('aria-label'))).toEqual([
      'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday',
    ]);
    expect(screen.getByRole('button', { name: 'Sunday' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Monday' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Friday' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('toggles one day’s bit in the mask', async () => {
    const onChange = vi.fn();
    render(<DayPicker mask={0b100_0000} onChange={onChange} />);
    await userEvent.click(screen.getByRole('button', { name: 'Wednesday' }));
    expect(onChange).toHaveBeenLastCalledWith(0b100_0100);
    await userEvent.click(screen.getByRole('button', { name: 'Sunday' }));
    expect(onChange).toHaveBeenLastCalledWith(0);
  });
});
