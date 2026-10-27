import type { ExampleSet } from '@/types/examples';
import { ListRow } from './ListRow';

const examples: ExampleSet = {
  title: 'ListRow',
  examples: [
    {
      name: 'info',
      render: () => (
        <ul className="m-0 list-none p-0">
          <ListRow title="Firmware" value="3.0.64" />
          <ListRow title="Serial number" value="D8256700000A0001" mono />
          <ListRow title="MAC address" value="—" />
        </ul>
      ),
    },
    {
      name: 'history',
      render: () => (
        <ul className="m-0 list-none p-0">
          <ListRow variant="history" title="Dispensed on request" subtitle="SE 8" value="Sun, Oct 25 · 9:00 AM" />
          <ListRow variant="history" title="Sun, Oct 25 · 9:00 AM" subtitle="Dose" value="≈ 177 mL" />
        </ul>
      ),
    },
  ],
};

export default examples;
