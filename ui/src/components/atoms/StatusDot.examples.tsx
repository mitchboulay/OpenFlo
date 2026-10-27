import type { ExampleSet } from '@/types/examples';
import { StatusDot } from './StatusDot';

const examples: ExampleSet = {
  title: 'StatusDot',
  examples: [
    { name: 'ok', render: () => <StatusDot tone="ok" label="Everything's fine" /> },
    { name: 'warn', render: () => <StatusDot tone="warn" label="Bottle low" /> },
    { name: 'bad', render: () => <StatusDot tone="bad" label="Offline" /> },
    { name: 'neutral', render: () => <StatusDot tone="neutral" label="Never checked in" /> },
  ],
};

export default examples;
