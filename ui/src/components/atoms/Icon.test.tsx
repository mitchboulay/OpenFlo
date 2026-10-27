import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Icon, ICON_NAMES } from './Icon';

describe('Icon', () => {
  it.each(ICON_NAMES)('%s renders a decorative path', (name) => {
    const { container } = render(<Icon name={name} />);
    const svg = container.querySelector('svg');
    expect(svg).toHaveAttribute('aria-hidden', 'true');
    expect(svg?.querySelector('path')?.getAttribute('d')).toBeTruthy();
  });

  it('sizes from the prop', () => {
    const { container } = render(<Icon name="clock" size={12} />);
    expect(container.querySelector('svg')).toHaveAttribute('width', '12');
  });
});
