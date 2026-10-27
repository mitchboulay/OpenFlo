import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Button } from '@/components/atoms/Button';
import { WizardShell } from './WizardShell';

describe('WizardShell', () => {
  it('shows progress, the step, its actions and Cancel, and focuses the title', async () => {
    const onCancel = vi.fn();
    render(
      <WizardShell progress={{ current: 2, total: 5 }} onCancel={onCancel} visual={{ icon: 'wifi', tone: 'accent' }} title="Join the device’s Wi-Fi" body="Scan with your phone.">
        <p>content</p>
      </WizardShell>,
    );
    expect(screen.getByText('Step 2 of 5')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: 'Join the device’s Wi-Fi' })).toHaveFocus();
    expect(screen.getByText('Scan with your phone.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it('leaves out progress and Cancel on end states', () => {
    render(<WizardShell title="Attic unit is ready." actions={<Button variant="primary">Go to Attic unit</Button>} />);
    expect(screen.queryByText(/Step \d of/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Go to Attic unit' })).toBeInTheDocument();
  });
});
