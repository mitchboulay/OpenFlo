import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { Select } from './Select';

describe('Select', () => {
  it('is a native combobox that changes value', async () => {
    render(
      <Select aria-label="Time zone" defaultValue="UTC">
        <option value="UTC">UTC</option>
        <option value="America/Chicago">America/Chicago</option>
      </Select>,
    );
    const select = screen.getByRole('combobox', { name: 'Time zone' });
    await userEvent.selectOptions(select, 'America/Chicago');
    expect(select).toHaveValue('America/Chicago');
  });
});
