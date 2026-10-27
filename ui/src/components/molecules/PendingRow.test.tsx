import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { PendingRow } from './PendingRow';

describe('PendingRow', () => {
  it('names the change and says when the device picks it up', () => {
    render(
      <ul>
        <PendingRow label="Dose change" detail="177 mL" expectedAt="2026-10-26T20:42:00Z" timeZone="America/New_York" />
      </ul>,
    );
    const row = screen.getByRole('listitem');
    expect(row).toHaveTextContent('Dose change 177 mL');
    expect(row).toHaveTextContent('Waiting for device · ~4:42 PM');
  });

  it('omits the time when the next check-in is unknown', () => {
    render(
      <ul>
        <PendingRow label="Retire" expectedAt={null} />
      </ul>,
    );
    expect(screen.getByText('Waiting for device')).toBeInTheDocument();
  });
});
