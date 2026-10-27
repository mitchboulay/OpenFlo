import type { ExampleSet } from '@/types/examples';
import { Button } from './Button';

const examples: ExampleSet = {
  title: 'Button',
  examples: [
    { name: 'Primary', render: () => <Button variant="primary">Dispense now…</Button> },
    { name: 'Secondary', render: () => <Button>Not mine</Button> },
    { name: 'Ghost', render: () => <Button variant="ghost">Change liquid…</Button> },
    { name: 'Danger', render: () => <Button variant="danger">Retire device</Button> },
    {
      name: 'Disabled',
      render: () => (
        <Button variant="primary" disabled>
          Add to this home
        </Button>
      ),
    },
  ],
};

export default examples;
