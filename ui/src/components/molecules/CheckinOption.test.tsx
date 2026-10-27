import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { CheckinOption } from './CheckinOption';

describe('CheckinOption', () => {
  it('is a radio carrying its state, trade-off and spoken battery cost', () => {
    render(<CheckinOption name="Balanced" line="Checks in every 6 hours." cost={2} costLabel="Low battery use" recommended selected onSelect={() => undefined} />);
    const radio = screen.getByRole('radio', { name: /Balanced/ });
    expect(radio).toHaveAttribute('aria-checked', 'true');
    expect(radio).toHaveTextContent('Recommended');
    expect(radio).toHaveTextContent('Low battery use');
  });

  it('reports a pick, and ignores it while disabled', async () => {
    const onSelect = vi.fn();
    const { rerender } = render(
      <CheckinOption name="Responsive" line="Hourly." cost={3} costLabel="Higher battery use" selected={false} onSelect={onSelect} />,
    );
    await userEvent.click(screen.getByRole('radio'));
    expect(onSelect).toHaveBeenCalledTimes(1);
    rerender(<CheckinOption name="Responsive" line="Hourly." cost={3} costLabel="Higher battery use" selected={false} onSelect={onSelect} disabled />);
    await userEvent.click(screen.getByRole('radio'));
    expect(onSelect).toHaveBeenCalledTimes(1);
  });
});
