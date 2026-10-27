import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { StatusDot } from './StatusDot';

describe('StatusDot', () => {
  it.each([
    ['ok', 'Online', 'text-ok'],
    ['warn', 'Bottle low', 'text-warn'],
    ['bad', 'Offline', 'text-bad'],
    ['neutral', 'Never seen', 'text-dim'],
  ] as const)('renders the %s tone with its visible label', (tone, label, toneClass) => {
    render(<StatusDot tone={tone} label={label} />);
    const text = screen.getByText(label);
    expect(text).toBeVisible();
    expect(text).toHaveClass(toneClass);
  });

  it('hides the decorative dot from assistive tech', () => {
    const { container } = render(<StatusDot tone="ok" label="Online" />);
    expect(container.querySelector('[aria-hidden="true"]')).not.toBeNull();
    expect(container.textContent).toBe('Online');
  });
});
