import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import { AppShell } from './AppShell';

describe('AppShell', () => {
  it('renders content in main with only the Settings link by default', () => {
    render(
      <MemoryRouter>
        <AppShell>
          <p>content</p>
        </AppShell>
      </MemoryRouter>,
    );
    expect(screen.getByRole('main')).toHaveTextContent('content');
    expect(screen.getByRole('main')).toHaveClass('max-w-narrow');
    expect(screen.getAllByRole('link')).toHaveLength(1);
    expect(screen.getByRole('link', { name: 'Settings' })).toHaveAttribute('href', '/settings');
  });

  it('renders the back link and the wide width', () => {
    render(
      <MemoryRouter>
        <AppShell back={{ to: '/homes/1', label: 'Cabin' }} contentWidth="wide">
          <p>device</p>
        </AppShell>
      </MemoryRouter>,
    );
    expect(screen.getByRole('link', { name: 'Cabin' })).toHaveAttribute('href', '/homes/1');
    expect(screen.getByRole('main')).toHaveClass('max-w-wide');
  });
});
