import type { ExampleSet } from '@/types/examples';
import { Notice } from './Notice';

const examples: ExampleSet = {
  title: 'Notice',
  examples: [
    { name: 'neutral', render: () => <Notice>Not enough data yet. Check back in a few days for an estimate.</Notice> },
    { name: 'warn', render: () => <Notice tone="warn">This liquid can dose 28–816 mL.</Notice> },
    {
      name: 'bad',
      render: () => (
        <Notice tone="bad" role="alert">
          Couldn’t reach your OpenFLO server.
        </Notice>
      ),
    },
    { name: 'ok', render: () => <Notice tone="ok">Calibration saved.</Notice> },
  ],
};

export default examples;
