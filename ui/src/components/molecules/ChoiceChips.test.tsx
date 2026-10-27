import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ChoiceChips } from './ChoiceChips';

const OPTIONS = [
  { value: 'light', label: 'Light', detail: '118 mL' },
  { value: 'standard', label: 'Standard', detail: '177 mL' },
] as const;

describe('ChoiceChips', () => {
  it('marks the selected chip pressed and shows details', () => {
    render(<ChoiceChips label="Dose presets" options={OPTIONS} selected="standard" onSelect={vi.fn()} />);
    expect(screen.getByRole('group', { name: 'Dose presets' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Standard 177 mL' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Light 118 mL' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('reports picks unless disabled', async () => {
    const onSelect = vi.fn();
    const { rerender } = render(<ChoiceChips label="Dose presets" options={OPTIONS} selected={null} onSelect={onSelect} />);
    await userEvent.click(screen.getByRole('button', { name: /Light/ }));
    expect(onSelect).toHaveBeenCalledWith('light');
    rerender(<ChoiceChips label="Dose presets" options={OPTIONS} selected={null} onSelect={onSelect} disabled />);
    await userEvent.click(screen.getByRole('button', { name: /Light/ }));
    expect(onSelect).toHaveBeenCalledTimes(1);
  });
});
