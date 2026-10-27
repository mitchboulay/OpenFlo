import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { QrCard } from './QrCard';

describe('QrCard', () => {
  it('shows the caption and the readable stand-in, not the payload', () => {
    render(
      <QrCard
        value="http://192.168.4.1/index.html?ott=feedfacefeedfacefeedface"
        label="QR code to open the setup page"
        caption="Setup page"
        displayValue="http://192.168.4.1"
        action={<button type="button">Copy link</button>}
      />,
    );
    expect(screen.getByRole('img', { name: 'QR code to open the setup page' })).toBeInTheDocument();
    expect(screen.getByText('Setup page')).toBeInTheDocument();
    expect(screen.getByText('http://192.168.4.1')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Copy link' })).toBeInTheDocument();
    expect(document.body.innerHTML).not.toContain('feedface');
  });
});
