import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Input } from '@/components/atoms/Input';
import { Field } from './Field';

describe('Field', () => {
  it('labels its control and describes it with the hint', () => {
    render(
      <Field label="Location" hint="Where it is.">
        <Input />
      </Field>,
    );
    const input = screen.getByRole('textbox', { name: 'Location' });
    expect(input).toHaveAccessibleDescription('Where it is.');
    expect(input).toHaveAttribute('aria-invalid', 'false');
  });

  it('marks the control invalid and announces the error', () => {
    render(
      <Field label="Name" error="Already taken.">
        <Input />
      </Field>,
    );
    expect(screen.getByRole('textbox', { name: 'Name' })).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByRole('alert')).toHaveTextContent('Already taken.');
  });
});
