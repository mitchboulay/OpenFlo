import type { ExampleSet } from '@/types/examples';
import { PendingBadge } from './PendingBadge';

const examples: ExampleSet = {
  title: 'PendingBadge',
  examples: [
    {
      name: 'With expected check-in (in 20 min)',
      render: () => <PendingBadge expectedAt={new Date(Date.now() + 20 * 60_000).toISOString()} />,
    },
    { name: 'Unknown check-in time', render: () => <PendingBadge /> },
  ],
};

export default examples;
