import type { ExampleSet } from '@/types/examples';
import { StepList } from './StepList';

const examples: ExampleSet = {
  title: 'StepList',
  examples: [
    {
      name: 'in progress',
      render: () => (
        <StepList
          label="Setup progress"
          steps={[
            { label: 'Reset', state: 'done' },
            { label: 'Found on your network', state: 'active' },
            { label: 'Registered', state: 'pending' },
          ]}
        />
      ),
    },
    {
      name: 'all done',
      render: () => (
        <StepList
          label="Setup progress"
          steps={[
            { label: 'Found on your network', state: 'done' },
            { label: 'Registered', state: 'done' },
          ]}
        />
      ),
    },
  ],
};

export default examples;
