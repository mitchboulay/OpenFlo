import type { ExampleSet } from '@/types/examples';
import { StatusPill } from './StatusPill';

const examples: ExampleSet = {
  title: 'StatusPill',
  examples: [
    { name: 'ok', render: () => <StatusPill tone="ok" label="OK" /> },
    { name: 'warn', render: () => <StatusPill tone="warn" label="Needs attention" /> },
    { name: 'offline', render: () => <StatusPill tone="bad" label="Offline" /> },
    { name: 'neutral', render: () => <StatusPill tone="neutral" label="Paused" /> },
  ],
};

export default examples;
