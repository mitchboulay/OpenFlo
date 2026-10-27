import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { PendingBadge } from './PendingBadge';

describe('PendingBadge', () => {
  it('names the expected check-in time in the given zone', () => {
    render(<PendingBadge expectedAt="2026-10-26T20:42:00Z" timeZone="America/New_York" />);
    // 12- or 24-hour depending on the runner's locale; 20:42Z is 4:42 PM in New York.
    expect(screen.getByText(/^Waiting for device · ~(4:42\sPM|16:42)$/)).toBeVisible();
  });

  it.each([undefined, null, 'not-a-date'])('falls back to plain text when the time is %s', (expectedAt) => {
    render(<PendingBadge expectedAt={expectedAt} />);
    expect(screen.getByText('Waiting for device')).toBeVisible();
  });
});
