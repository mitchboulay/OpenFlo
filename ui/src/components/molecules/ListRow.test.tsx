import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ListRow } from './ListRow';

describe('ListRow', () => {
  it('shows a label and its value', () => {
    render(
      <ul>
        <ListRow title="Serial number" value="D8256700000A0001" mono />
      </ul>,
    );
    expect(screen.getByRole('listitem')).toHaveTextContent('Serial numberD8256700000A0001');
    expect(screen.getByText('D8256700000A0001')).toHaveClass('font-mono');
  });

  it('shows a history subtitle', () => {
    render(
      <ul>
        <ListRow variant="history" title="Dispensed on request" subtitle="SE 8" value="9:00 AM" />
      </ul>,
    );
    expect(screen.getByText('SE 8')).toBeInTheDocument();
    expect(screen.getByText('Dispensed on request')).toHaveClass('font-medium');
  });
});
