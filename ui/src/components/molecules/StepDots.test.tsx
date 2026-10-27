import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { StepDots } from './StepDots';

describe('StepDots', () => {
  it('says which step this is and fills that many segments', () => {
    const { container } = render(<StepDots current={2} total={3} />);
    expect(screen.getByText('Step 2 of 3')).toBeInTheDocument();
    expect(container.querySelectorAll('.bg-accent')).toHaveLength(2);
    expect(container.querySelectorAll('.bg-border2')).toHaveLength(1);
  });
});
