import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { Field } from './Field';
import { PasswordInput } from './PasswordInput';

describe('PasswordInput', () => {
  it('hides the value until "Show password", and keeps Field wiring on the input', async () => {
    render(
      <Field label="Password" hint="At least 12 characters.">
        <PasswordInput autoComplete="new-password" defaultValue="correct horse" />
      </Field>,
    );
    const input = screen.getByLabelText('Password');
    expect(input).toHaveAttribute('type', 'password');
    expect(input).toHaveAttribute('autocomplete', 'new-password');
    expect(input).toHaveAccessibleDescription('At least 12 characters.');

    await userEvent.click(screen.getByRole('button', { name: 'Show password' }));
    expect(input).toHaveAttribute('type', 'text');
    await userEvent.click(screen.getByRole('button', { name: 'Hide password' }));
    expect(input).toHaveAttribute('type', 'password');
  });
});
