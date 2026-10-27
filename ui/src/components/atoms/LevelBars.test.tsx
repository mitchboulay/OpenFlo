import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { LevelBars } from './LevelBars';

describe('LevelBars', () => {
  it('lights `level` of four bars in the given fill, and hides itself from screen readers', () => {
    const { container } = render(<LevelBars level={3} fillClassName="bg-warn" />);
    const group = container.firstElementChild!;
    expect(group).toHaveAttribute('aria-hidden', 'true');
    expect(group.querySelectorAll('.bg-warn')).toHaveLength(3);
    expect(group.querySelectorAll('.bg-border2')).toHaveLength(1);
  });

  it('defaults to the text color and shows no bars lit at 0', () => {
    const { container, rerender } = render(<LevelBars level={4} />);
    expect(container.querySelectorAll('.bg-fg')).toHaveLength(4);
    rerender(<LevelBars level={0} />);
    expect(container.querySelectorAll('.bg-border2')).toHaveLength(4);
  });
});
