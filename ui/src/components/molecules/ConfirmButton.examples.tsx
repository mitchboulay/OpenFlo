import { useState } from 'react';
import type { ExampleSet } from '@/types/examples';
import { ConfirmButton } from './ConfirmButton';

function CountingConfirm() {
  const [confirmations, setConfirmations] = useState(0);
  return (
    <div className="flex flex-wrap items-center gap-3">
      <ConfirmButton
        variant="primary"
        label="Dispense now…"
        armedLabel="Tap again to dispense"
        onConfirm={() => setConfirmations((count) => count + 1)}
      />
      <span className="text-dim">Confirmed {confirmations}×</span>
    </div>
  );
}

const examples: ExampleSet = {
  title: 'ConfirmButton',
  examples: [
    { name: 'Primary (counts confirmations)', render: () => <CountingConfirm /> },
    {
      name: 'Danger',
      render: () => <ConfirmButton label="Retire device" armedLabel="Tap again to retire" onConfirm={() => undefined} />,
    },
  ],
};

export default examples;
