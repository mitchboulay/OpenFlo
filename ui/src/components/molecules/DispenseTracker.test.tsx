import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { DispenseTracker } from './DispenseTracker';

describe('DispenseTracker', () => {
  it('marks stages up to the current one as done', () => {
    render(<DispenseTracker stage="sent" title="Sent to device" note="Your iFLO has the request." />);
    const steps = screen.getAllByRole('listitem');
    expect(within(steps[0]!).getByText(/\(done\)/)).toBeInTheDocument();
    expect(steps[1]).toHaveAttribute('aria-current', 'step');
    expect(within(steps[1]!).getByText(/\(done\)/)).toBeInTheDocument();
    expect(within(steps[2]!).getByText(/\(not yet\)/)).toBeInTheDocument();
  });

  it('shows the title, note and action', () => {
    render(<DispenseTracker stage="queued" title="Queued for next check-in" note="Waiting for device" action={<button type="button">Cancel request</button>} />);
    expect(screen.getByText('Queued for next check-in')).toBeInTheDocument();
    expect(screen.getByText('Waiting for device')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancel request' })).toBeInTheDocument();
  });
});
