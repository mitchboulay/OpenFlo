import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router';
import { Button } from '@/components/atoms/Button';
import { Notice } from '@/components/atoms/Notice';
import { NameLocationFields } from '@/components/molecules/NameLocationFields';
import { Sheet } from '@/components/templates/Sheet';
import type { HomeSummary, UnclaimedDevice } from '@/api/types';
import { useClaimDevice } from '@/hooks/useHomes';
import { errorMessage } from '@/lib/errors';

export interface ClaimSheetProps {
  /** The device being claimed; null keeps the sheet closed. */
  device: UnclaimedDevice | null;
  home: HomeSummary;
  onClose: () => void;
}

/** Claim an unclaimed device into this home (FR-5). It starts with dispensing off, and the copy says so. */
export function ClaimSheet({ device, home, onClose }: ClaimSheetProps) {
  return (
    <Sheet open={device !== null} onClose={onClose} title="Add to this home">
      {device && <ClaimForm key={device.device_id} device={device} home={home} />}
    </Sheet>
  );
}

function ClaimForm({ device, home }: { device: UnclaimedDevice; home: HomeSummary }) {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [location, setLocation] = useState('');
  const claim = useClaimDevice();
  const trimmed = name.trim();

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!trimmed) return;
    claim.mutate(
      { deviceId: device.device_id, body: { home_id: home.id, name: trimmed, location: location.trim() || null } },
      { onSuccess: (claimed) => navigate(`/devices/${encodeURIComponent(claimed.device_id)}`) },
    );
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <p className="m-0 text-dim">
        <span className="font-mono text-[13px] text-fg">{device.device_id}</span> is already connected. Give it a name
        and say where it is.
      </p>
      <NameLocationFields
        name={name}
        location={location}
        onNameChange={setName}
        onLocationChange={setLocation}
        error={claim.isError ? errorMessage(claim.error) : null}
      />
      <Notice>Dispensing starts off. Turn it on from the device page once the bottle is in.</Notice>
      <Button type="submit" variant="primary" disabled={!trimmed || claim.isPending}>
        Add to {home.name}
      </Button>
    </form>
  );
}
