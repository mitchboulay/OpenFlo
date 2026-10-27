import type { ExampleSet } from '@/types/examples';
import { Badge } from './Badge';

const examples: ExampleSet = {
  title: 'Badge',
  examples: [
    { name: 'neutral', render: () => <Badge>Not calibrated yet</Badge> },
    { name: 'accent', render: () => <Badge tone="accent">Default</Badge> },
    { name: 'ok', render: () => <Badge tone="ok">Applied</Badge> },
    { name: 'warn', render: () => <Badge tone="warn">Bottle low</Badge> },
    { name: 'bad', render: () => <Badge tone="bad">Identity changed</Badge> },
  ],
};

export default examples;
