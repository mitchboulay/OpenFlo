import type { ExampleSet } from '@/types/examples';
import { BottleGauge } from './BottleGauge';

const TICKS = [1, 2, 3, 4, 5].map((n) => (n * 177) / 1065);

const examples: ExampleSet = {
  title: 'BottleGauge',
  examples: [
    { name: 'ok, with dose ticks', render: () => <BottleGauge fraction={0.66} ticks={TICKS} tone="ok" label="About 700 mL left" /> },
    { name: 'refill soon', render: () => <BottleGauge fraction={0.2} ticks={TICKS} tone="warn" label="About 210 mL left" /> },
    { name: 'unknown level', render: () => <BottleGauge fraction={null} tone="warn" label="Level unknown" /> },
  ],
};

export default examples;
