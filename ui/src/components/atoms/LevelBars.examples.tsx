import type { ExampleSet } from '@/types/examples';
import { LevelBars } from './LevelBars';

const examples: ExampleSet = {
  title: 'LevelBars',
  examples: [
    { name: 'strong signal (4)', render: () => <LevelBars level={4} /> },
    { name: 'fair signal (2)', render: () => <LevelBars level={2} /> },
    { name: 'higher battery use (3, warn)', render: () => <LevelBars level={3} fillClassName="bg-warn" /> },
    { name: 'very high battery use (4, bad)', render: () => <LevelBars level={4} fillClassName="bg-bad" /> },
  ],
};

export default examples;
