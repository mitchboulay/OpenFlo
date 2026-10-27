import type { ExampleSet } from '@/types/examples';
import { Stepper } from './Stepper';

const noop = () => undefined;

const examples: ExampleSet = {
  title: 'Stepper',
  examples: [
    { name: 'dose', render: () => <Stepper label="Dose" value="177" unit="mL" onDecrement={noop} onIncrement={noop} /> },
    { name: 'at the upper bound', render: () => <Stepper label="Dose" value="816" unit="mL" atMax onDecrement={noop} onIncrement={noop} /> },
    { name: 'sheet size', render: () => <Stepper size="md" label="Bottle level" value="525" unit="mL" onDecrement={noop} onIncrement={noop} /> },
  ],
};

export default examples;
