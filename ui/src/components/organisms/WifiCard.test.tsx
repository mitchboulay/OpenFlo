import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import type { DeviceDetail } from '@/api/types';
import { DEVICE_ID, makeDevice } from '@/test/fixtures';
import { WifiCard } from './WifiCard';

function renderCard(device: DeviceDetail) {
  return render(
    <MemoryRouter>
      <WifiCard device={device} />
    </MemoryRouter>,
  );
}

describe('WifiCard', () => {
  it('shows the network, signal as bars plus words, and the address', () => {
    renderCard(makeDevice());
    const card = screen.getByRole('region', { name: 'Wi-Fi' });
    expect(within(card).getByText('OpenFLO')).toBeInTheDocument();
    expect(within(card).getByText(/Strong signal/)).toBeInTheDocument();
    expect(within(card).getByText('192.168.30.80')).toBeInTheDocument();
  });

  it('changes Wi-Fi only through set-up-again, never by telling people to press device buttons', () => {
    renderCard(makeDevice());
    const card = screen.getByRole('region', { name: 'Wi-Fi' });
    expect(within(card).getByRole('link', { name: 'Change Wi-Fi…' })).toHaveAttribute(
      'href',
      `/homes/1/add?device=${DEVICE_ID}`,
    );
    // A long press of the user button can dispense, of the reset button factory-reset (research R-1 notes).
    expect(card.textContent).not.toMatch(/press|hold/i);
  });

  it('says what is unknown instead of guessing, and offers no change for an unclaimed device', () => {
    renderCard(makeDevice({ network_name: null, signal: null, last_ip: null, status: 'unclaimed', home_id: null }));
    expect(screen.getByText('Network not reported yet')).toBeInTheDocument();
    expect(screen.getByText('Signal not reported yet')).toBeInTheDocument();
    expect(screen.queryByRole('link')).toBeNull();
  });
});
