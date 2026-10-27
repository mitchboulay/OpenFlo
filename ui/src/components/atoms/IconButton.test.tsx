import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Icon } from './Icon';
import { IconButton } from './IconButton';

describe('IconButton', () => {
  it('is named by its label, not its icon', () => {
    render(
      <IconButton label="Edit home">
        <Icon name="edit" />
      </IconButton>,
    );
    const button = screen.getByRole('button', { name: 'Edit home' });
    expect(button).toHaveAttribute('type', 'button');
    expect(button.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
  });

  it('clicks unless disabled', async () => {
    const onClick = vi.fn();
    const { rerender } = render(<IconButton label="Close" onClick={onClick} />);
    await userEvent.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledTimes(1);
    rerender(<IconButton label="Close" onClick={onClick} disabled />);
    await userEvent.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
