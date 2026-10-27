import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { StatusPill } from './StatusPill';

describe('StatusPill', () => {
  it('always shows its text, in the tone colors', () => {
    render(<StatusPill tone="warn" label="Needs attention" />);
    expect(screen.getByText('Needs attention')).toHaveClass('bg-warn-soft', 'text-warn');
  });

  it('draws offline as a hollow dot, so it reads without color', () => {
    const { container } = render(<StatusPill tone="bad" label="Offline" />);
    expect(container.querySelector('.border-bad')).not.toBeNull();
  });
});
