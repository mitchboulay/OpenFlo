import { createRef } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { Input } from './Input';

describe('Input', () => {
  it('passes native attributes through, including inputmode', async () => {
    render(<Input aria-label="Measured" inputMode="decimal" />);
    const input = screen.getByRole('textbox', { name: 'Measured' });
    expect(input).toHaveAttribute('inputmode', 'decimal');
    await userEvent.type(input, '181');
    expect(input).toHaveValue('181');
  });

  it('forwards its ref', () => {
    const ref = createRef<HTMLInputElement>();
    render(<Input ref={ref} aria-label="Name" />);
    expect(ref.current).toBeInstanceOf(HTMLInputElement);
  });
});
