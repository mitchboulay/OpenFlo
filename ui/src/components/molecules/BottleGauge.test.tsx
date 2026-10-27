import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { BottleGauge } from './BottleGauge';

describe('BottleGauge', () => {
  it('is a meter with the fill and one tick per interior dose mark', () => {
    const { container } = render(<BottleGauge fraction={0.5} ticks={[0.25, 0.5, 0.75, 1]} tone="ok" label="About half full" />);
    const meter = screen.getByRole('meter', { name: 'About half full' });
    expect(meter).toHaveAttribute('aria-valuenow', '50');
    expect(container.querySelectorAll('.bg-surface')).toHaveLength(3);
  });

  it('shows an empty track with no value when the level is unknown', () => {
    render(<BottleGauge fraction={null} tone="warn" label="Level unknown" />);
    const meter = screen.getByRole('meter');
    expect(meter).not.toHaveAttribute('aria-valuenow');
    expect(meter).toHaveAttribute('aria-valuetext', 'Level unknown');
  });

  it('clamps out-of-range fractions', () => {
    render(<BottleGauge fraction={1.4} tone="ok" label="Full" />);
    expect(screen.getByRole('meter')).toHaveAttribute('aria-valuenow', '100');
  });
});
