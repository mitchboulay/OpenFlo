import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { QrCode } from './QrCode';

describe('QrCode', () => {
  it('draws the payload as modules under an accessible name, never as text', () => {
    const secret = 'http://192.168.4.1/index.html?ott=0123456789abcdef01234567';
    const { container } = render(<QrCode value={secret} label="QR code to open the setup page" />);
    const image = screen.getByRole('img', { name: 'QR code to open the setup page' });
    expect(image.querySelector('path')?.getAttribute('d')).toMatch(/^M\d+ \d+h1v1h-1z/);
    expect(container.innerHTML).not.toContain('0123456789abcdef01234567');
  });

  it('grows with the payload', () => {
    const { container, rerender } = render(<QrCode value="WIFI:T:WPA;S:x;P:y;;" label="Wi-Fi" />);
    const small = container.querySelector('svg')?.getAttribute('viewBox');
    rerender(<QrCode value={'x'.repeat(200)} label="Wi-Fi" />);
    expect(container.querySelector('svg')?.getAttribute('viewBox')).not.toBe(small);
  });
});
