import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { SectionCard } from './SectionCard';

describe('SectionCard', () => {
  it('renders a titled region with its body', () => {
    render(
      <SectionCard id="schedule" title="Schedule" icon="calendar">
        <p>Nothing coming up.</p>
      </SectionCard>,
    );
    const region = screen.getByRole('region', { name: 'Schedule' });
    expect(region).toHaveAttribute('id', 'schedule');
    expect(screen.getByRole('heading', { name: 'Schedule' })).toBeInTheDocument();
    expect(screen.getByText('Nothing coming up.')).toBeVisible();
  });

  it('folds behind a disclosure button when collapsible (below lg)', async () => {
    render(
      <SectionCard title="Battery" icon="battery" collapsible>
        <p>Body</p>
      </SectionCard>,
    );
    const toggle = screen.getByRole('button', { name: 'Battery' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    const body = document.getElementById(toggle.getAttribute('aria-controls') ?? '');
    expect(body).toHaveClass('hidden', 'lg:flex');
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(body).not.toHaveClass('hidden');
  });
});
