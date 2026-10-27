import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Sparkline } from './Sparkline';

describe('Sparkline', () => {
  it('draws one point per value, oldest on the left, with an accessible label', () => {
    render(<Sparkline values={[90, 85, 80]} label="Battery from 90% to 80%" />);
    const chart = screen.getByRole('img', { name: 'Battery from 90% to 80%' });
    const points = chart.querySelector('polyline')?.getAttribute('points')?.split(' ') ?? [];
    expect(points).toHaveLength(3);
    const [first, last] = [points[0]?.split(',').map(Number), points[2]?.split(',').map(Number)];
    expect(first?.[0]).toBe(0);
    expect(last?.[0]).toBe(300);
    // Higher values sit higher (smaller y).
    expect(first?.[1]).toBeLessThan(last?.[1] ?? 0);
  });

  it('draws nothing with fewer than two values', () => {
    const { container } = render(<Sparkline values={[90]} label="Battery" />);
    expect(container).toBeEmptyDOMElement();
  });
});
