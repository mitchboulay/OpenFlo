import { useState } from 'react';
import type { ExampleSet } from '@/types/examples';
import { Switch } from './Switch';

function Interactive({ initial, label }: { initial: boolean; label: string }) {
  const [checked, setChecked] = useState(initial);
  return <Switch checked={checked} onChange={setChecked} label={label} />;
}

const examples: ExampleSet = {
  title: 'Switch',
  examples: [
    { name: 'Off', render: () => <Interactive initial={false} label="Schedules" /> },
    { name: 'On', render: () => <Interactive initial label="Dispensing" /> },
    {
      name: 'Disabled',
      render: () => <Switch checked={false} onChange={() => undefined} label="Adjust for bottle level" disabled />,
    },
  ],
};

export default examples;
