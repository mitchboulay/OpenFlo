import type { ExampleSet } from '@/types/examples';
import { Sparkline } from './Sparkline';

const examples: ExampleSet = {
  title: 'Sparkline',
  examples: [
    { name: 'ok', render: () => <Sparkline values={[88, 87, 87, 86, 85, 85, 84, 83, 82]} label="Battery from 88% to 82%" /> },
    { name: 'bad', render: () => <Sparkline values={[31, 27, 22, 18, 14, 9]} tone="bad" label="Battery from 31% to 9%" /> },
  ],
};

export default examples;
