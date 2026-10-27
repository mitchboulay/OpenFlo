import { useState, type FormEvent } from 'react';
import { Button } from '@/components/atoms/Button';
import { NameLocationFields } from '@/components/molecules/NameLocationFields';
import { Sheet } from '@/components/templates/Sheet';
import { api } from '@/api/endpoints';
import type { DeviceDetail } from '@/api/types';
import { useDeviceAction } from '@/hooks/useDevice';
import { errorMessage } from '@/lib/errors';

export interface DeviceSheetProps {
  open: boolean;
  device: DeviceDetail;
  onClose: () => void;
}

/** Edit a device's name and location (FR-2). These are server-side labels: nothing waits for the device. */
export function DeviceSheet({ open, device, onClose }: DeviceSheetProps) {
  return (
    <Sheet open={open} onClose={onClose} title="Edit device">
      {open && <DeviceForm device={device} onDone={onClose} />}
    </Sheet>
  );
}

function DeviceForm({ device, onDone }: { device: DeviceDetail; onDone: () => void }) {
  const [name, setName] = useState(device.name ?? '');
  const [location, setLocation] = useState(device.location ?? '');
  const save = useDeviceAction(device.device_id, (body: { name: string; location: string | null }) =>
    api.updateDevice(device.device_id, body),
  );
  const trimmed = name.trim();

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!trimmed) return;
    save.mutate({ name: trimmed, location: location.trim() || null }, { onSuccess: onDone });
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <NameLocationFields
        name={name}
        location={location}
        onNameChange={setName}
        onLocationChange={setLocation}
        error={save.isError ? errorMessage(save.error) : null}
      />
      <Button type="submit" variant="primary" disabled={!trimmed || save.isPending}>
        Save
      </Button>
    </form>
  );
}
