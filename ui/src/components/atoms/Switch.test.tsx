import { useState } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Switch } from './Switch';

function ControlledSwitch({ initial = false }: { initial?: boolean }) {
  const [checked, setChecked] = useState(initial);
  return <Switch checked={checked} onChange={setChecked} label="Dispensing" />;
}

describe('Switch', () => {
  it('exposes role="switch" with its label and aria-checked state', () => {
    render(<Switch checked onChange={() => undefined} label="Dispensing" />);
    const toggle = screen.getByRole('switch', { name: 'Dispensing' });
    expect(toggle).toHaveAttribute('aria-checked', 'true');
  });

  it('toggles on click', async () => {
    render(<ControlledSwitch />);
    const toggle = screen.getByRole('switch', { name: 'Dispensing' });
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-checked', 'true');
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-checked', 'false');
  });

  it('toggles with Space and Enter', async () => {
    render(<ControlledSwitch />);
    const toggle = screen.getByRole('switch', { name: 'Dispensing' });
    toggle.focus();
    await userEvent.keyboard(' ');
    expect(toggle).toHaveAttribute('aria-checked', 'true');
    await userEvent.keyboard('{Enter}');
    expect(toggle).toHaveAttribute('aria-checked', 'false');
  });

  it('reports the requested state without changing itself (controlled)', async () => {
    const onChange = vi.fn();
    render(<Switch checked={false} onChange={onChange} label="Schedules" />);
    const toggle = screen.getByRole('switch', { name: 'Schedules' });
    await userEvent.click(toggle);
    expect(onChange).toHaveBeenCalledWith(true);
    expect(toggle).toHaveAttribute('aria-checked', 'false');
  });

  it('ignores input when disabled', async () => {
    const onChange = vi.fn();
    render(<Switch checked={false} onChange={onChange} label="Schedules" disabled />);
    await userEvent.click(screen.getByRole('switch'));
    expect(onChange).not.toHaveBeenCalled();
  });
});
