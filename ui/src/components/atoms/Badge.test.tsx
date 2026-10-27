import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Badge } from './Badge';

describe('Badge', () => {
  it('defaults to the neutral tone', () => {
    render(<Badge>Default</Badge>);
    expect(screen.getByText('Default')).toHaveClass('bg-surface2', 'text-dim');
  });

  it.each([
    ['ok', 'bg-ok-soft'],
    ['warn', 'bg-warn-soft'],
    ['bad', 'bg-bad-soft'],
    ['accent', 'bg-accent-soft'],
  ] as const)('applies the %s tone', (tone, toneClass) => {
    render(<Badge tone={tone}>Label</Badge>);
    expect(screen.getByText('Label')).toHaveClass(toneClass);
  });

  it('renders the icon decoratively', () => {
    render(<Badge icon={<svg data-testid="icon" />}>Waiting</Badge>);
    expect(screen.getByTestId('icon').parentElement).toHaveAttribute('aria-hidden', 'true');
    expect(screen.getByText('Waiting')).toBeVisible();
  });
});
