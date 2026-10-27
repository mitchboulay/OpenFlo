import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Stepper } from './Stepper';

describe('Stepper', () => {
  it('shows the value and steps both ways', async () => {
    const onDecrement = vi.fn();
    const onIncrement = vi.fn();
    render(<Stepper label="Dose" value="177" unit="mL" onDecrement={onDecrement} onIncrement={onIncrement} />);
    expect(screen.getByRole('status', { name: 'Dose' })).toHaveTextContent('177mL');
    await userEvent.click(screen.getByRole('button', { name: 'Less dose' }));
    await userEvent.click(screen.getByRole('button', { name: 'More dose' }));
    expect(onDecrement).toHaveBeenCalledTimes(1);
    expect(onIncrement).toHaveBeenCalledTimes(1);
  });

  it('disables the button at each bound', () => {
    const { rerender } = render(<Stepper label="Dose" value="28" unit="mL" atMin onDecrement={vi.fn()} onIncrement={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Less dose' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'More dose' })).toBeEnabled();
    rerender(<Stepper label="Dose" value="816" unit="mL" atMax onDecrement={vi.fn()} onIncrement={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'More dose' })).toBeDisabled();
  });
});
