import type { ExampleSet } from '@/types/examples';
import { StepDots } from './StepDots';

const examples: ExampleSet = {
  title: 'StepDots',
  examples: [
    { name: 'step 1 of 3', render: () => <StepDots current={1} total={3} /> },
    { name: 'step 3 of 3', render: () => <StepDots current={3} total={3} /> },
  ],
};

export default examples;
