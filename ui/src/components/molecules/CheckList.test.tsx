import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { checkRows, pendingRows } from '@/lib/addressCheck';
import { makeCheckResult } from '@/test/fixtures';
import { CheckList } from './CheckList';

describe('CheckList', () => {
  it('pairs every status with text and sets config words in mono', () => {
    render(<CheckList label="Address check" rows={checkRows(makeCheckResult({ tls_no_sni: 'fail', port_non_443: 'warn' }))} />);
    const list = screen.getByRole('list', { name: 'Address check' });
    const rows = within(list).getAllByRole('listitem');
    expect(rows[0]).toHaveTextContent('Found your server');
    expect(rows[0]).toHaveTextContent('OK');
    expect(rows[1]).toHaveTextContent('Problem');
    expect(within(rows[1] as HTMLElement).getByText('default_sni').tagName).toBe('CODE');
    expect(rows.at(-1)).toHaveTextContent('Warning');
  });

  it('keeps the raw detail behind a Details disclosure on non-ok rows only', async () => {
    render(<CheckList label="Address check" rows={checkRows(makeCheckResult({ leaf_rsa: 'fail' }))} />);
    expect(screen.getAllByText('Details')).toHaveLength(1);
    const raw = screen.getByText('leaf_rsa: raw failure detail');
    expect(raw).not.toBeVisible();
    await userEvent.click(screen.getByText('Details'));
    expect(raw).toBeVisible();
  });

  it('shows dim "Checking…" rows while running', () => {
    render(<CheckList label="Address check" rows={pendingRows('https://a.example.com', 'checking')} />);
    expect(screen.getAllByText('Checking…')).toHaveLength(5);
  });
});
