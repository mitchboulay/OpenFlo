import { useState } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { Tabs, tabPanelProps } from './Tabs';

const TABS = [
  { value: 'a', label: 'Dispenses' },
  { value: 'b', label: 'Events' },
  { value: 'c', label: 'Check-ins' },
] as const;

function Harness() {
  const [tab, setTab] = useState<'a' | 'b' | 'c'>('a');
  return (
    <>
      <Tabs label="History" tabs={TABS} selected={tab} onSelect={setTab} idPrefix="t" />
      <div {...tabPanelProps('t', tab)}>panel {tab}</div>
    </>
  );
}

describe('Tabs', () => {
  it('selects on click and labels the panel by the selected tab', async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole('tab', { name: 'Events' }));
    expect(screen.getByRole('tab', { name: 'Events' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tabpanel', { name: 'Events' })).toHaveTextContent('panel b');
  });

  it('moves with arrow keys and wraps', async () => {
    render(<Harness />);
    screen.getByRole('tab', { name: 'Dispenses' }).focus();
    await userEvent.keyboard('{ArrowLeft}');
    expect(screen.getByRole('tab', { name: 'Check-ins' })).toHaveFocus();
    expect(screen.getByRole('tab', { name: 'Check-ins' })).toHaveAttribute('aria-selected', 'true');
    await userEvent.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: 'Dispenses' })).toHaveFocus();
  });
});
