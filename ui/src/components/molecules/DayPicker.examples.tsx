import { useState } from 'react';
import type { ExampleSet } from '@/types/examples';
import { DayPicker } from './DayPicker';

function Live({ initial }: { initial: number }) {
  const [mask, setMask] = useState(initial);
  return <DayPicker mask={mask} onChange={setMask} />;
}

const examples: ExampleSet = {
  title: 'DayPicker',
  examples: [
    { name: 'Sunday', render: () => <Live initial={0b100_0000} /> },
    { name: 'weekdays', render: () => <Live initial={0b001_1111} /> },
    { name: 'none (invalid for a weekly rule)', render: () => <Live initial={0} /> },
  ],
};

export default examples;
