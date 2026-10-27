import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Button, buttonClassName } from './Button';

describe('Button', () => {
  it('is a non-submitting button by default', () => {
    render(<Button>Save</Button>);
    expect(screen.getByRole('button', { name: 'Save' })).toHaveAttribute('type', 'button');
  });

  it('fires onClick from pointer and keyboard', async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Save</Button>);
    const button = screen.getByRole('button', { name: 'Save' });
    await userEvent.click(button);
    button.focus();
    await userEvent.keyboard('{Enter}');
    expect(onClick).toHaveBeenCalledTimes(2);
  });

  it('lends its look to links via buttonClassName', () => {
    render(<a href="/homes/1/add" className={buttonClassName('primary')}>Add device</a>);
    expect(screen.getByRole('link', { name: 'Add device' })).toHaveClass('min-h-11', 'bg-accent', 'no-underline');
  });

  it('does not fire when disabled', async () => {
    const onClick = vi.fn();
    render(
      <Button disabled onClick={onClick}>
        Save
      </Button>,
    );
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(onClick).not.toHaveBeenCalled();
  });

  it.each([
    ['primary', 'bg-accent'],
    ['secondary', 'bg-surface'],
    ['ghost', 'bg-transparent'],
    ['danger', 'bg-bad-soft'],
  ] as const)('applies the %s variant', (variant, expectedClass) => {
    render(<Button variant={variant}>Go</Button>);
    expect(screen.getByRole('button')).toHaveClass(expectedClass, 'min-h-11', 'min-w-11');
  });
});
