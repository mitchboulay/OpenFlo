import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Menu } from './Menu';

function setup() {
  const pause = vi.fn();
  const retire = vi.fn();
  render(
    <Menu
      label="Device actions"
      items={[
        { label: 'Pause dispensing', onSelect: pause },
        { label: 'Retire device…', tone: 'danger', onSelect: retire },
      ]}
    />,
  );
  return { pause, retire, trigger: screen.getByRole('button', { name: 'Device actions' }) };
}

describe('Menu', () => {
  it('opens, focuses the first item and runs the chosen one', async () => {
    const { pause, trigger } = setup();
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    await userEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('menuitem', { name: 'Pause dispensing' })).toHaveFocus();
    await userEvent.click(screen.getByRole('menuitem', { name: 'Pause dispensing' }));
    expect(pause).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('menu')).toBeNull();
    expect(trigger).toHaveFocus();
  });

  it('moves with arrow keys and closes on Escape', async () => {
    const { trigger } = setup();
    await userEvent.click(trigger);
    await userEvent.keyboard('{ArrowDown}');
    expect(screen.getByRole('menuitem', { name: 'Retire device…' })).toHaveFocus();
    await userEvent.keyboard('{ArrowDown}');
    expect(screen.getByRole('menuitem', { name: 'Pause dispensing' })).toHaveFocus();
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('menu')).toBeNull();
    expect(trigger).toHaveFocus();
  });

  it('closes on an outside click', async () => {
    const { trigger } = setup();
    await userEvent.click(trigger);
    await userEvent.click(document.body);
    expect(screen.queryByRole('menu')).toBeNull();
  });
});
