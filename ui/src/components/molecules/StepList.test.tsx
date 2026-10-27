import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { StepList } from './StepList';

describe('StepList', () => {
  it('pairs every state with text and marks the current step', () => {
    render(
      <StepList
        label="Setup progress"
        steps={[
          { label: 'Reset', state: 'done' },
          { label: 'Device found', state: 'active' },
          { label: 'Registered', state: 'pending' },
        ]}
      />,
    );
    const rows = within(screen.getByRole('list', { name: 'Setup progress' })).getAllByRole('listitem');
    expect(rows.map((row) => row.textContent)).toEqual(['ResetDone', 'Device foundNow', 'RegisteredNot yet']);
    expect(rows[1]).toHaveAttribute('aria-current', 'step');
    expect(rows[0]).not.toHaveAttribute('aria-current');
  });
});
