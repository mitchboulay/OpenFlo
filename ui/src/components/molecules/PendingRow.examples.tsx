import type { ExampleSet } from '@/types/examples';
import { PendingRow } from './PendingRow';

const examples: ExampleSet = {
  title: 'PendingRow',
  examples: [
    {
      name: 'list',
      render: () => (
        <ul className="m-0 list-none overflow-hidden rounded-button border border-border p-0">
          <PendingRow label="Dose change" expectedAt="2026-10-26T20:42:00Z" timeZone="America/New_York" />
          <PendingRow label="Dispense now" detail="177 mL" expectedAt={null} />
        </ul>
      ),
    },
  ],
};

export default examples;
