import { useState } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Button } from '@/components/atoms/Button';
import { Sheet } from './Sheet';

function Harness({ onClose }: { onClose?: () => void }) {
  const [open, setOpen] = useState(false);
  const close = () => {
    setOpen(false);
    onClose?.();
  };
  return (
    <>
      <Button onClick={() => setOpen(true)}>Set level</Button>
      <Sheet open={open} onClose={close} title="Bottle level" footer={<Button onClick={close}>Done</Button>}>
        <input aria-label="Level" />
      </Sheet>
    </>
  );
}

describe('Sheet', () => {
  it('renders nothing while closed', () => {
    render(<Sheet open={false} onClose={() => undefined} title="Hidden">body</Sheet>);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('is a labelled modal dialog', async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole('button', { name: 'Set level' }));
    const dialog = screen.getByRole('dialog', { name: 'Bottle level' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
  });

  it('moves focus inside and keeps Tab within the sheet', async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole('button', { name: 'Set level' }));
    const close = screen.getByRole('button', { name: 'Close' });
    const done = screen.getByRole('button', { name: 'Done' });
    expect(close).toHaveFocus();
    await userEvent.tab();
    expect(screen.getByRole('textbox', { name: 'Level' })).toHaveFocus();
    await userEvent.tab();
    expect(done).toHaveFocus();
    await userEvent.tab();
    expect(close).toHaveFocus();
    await userEvent.tab({ shift: true });
    expect(done).toHaveFocus();
  });

  it('closes on Escape and returns focus to the opener', async () => {
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    const opener = screen.getByRole('button', { name: 'Set level' });
    await userEvent.click(opener);
    await userEvent.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });

  it('closes from the close button and locks body scroll only while open', async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole('button', { name: 'Set level' }));
    expect(document.body.style.overflow).toBe('hidden');
    await userEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(document.body.style.overflow).toBe('');
  });
});
