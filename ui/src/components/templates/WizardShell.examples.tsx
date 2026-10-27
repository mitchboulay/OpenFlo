import { Button } from '@/components/atoms/Button';
import type { ExampleSet } from '@/types/examples';
import { WizardShell } from './WizardShell';

const examples: ExampleSet = {
  title: 'WizardShell',
  examples: [
    {
      name: 'a step (full screen; shown here inside the gallery)',
      render: () => (
        <WizardShell
          progress={{ current: 1, total: 5 }}
          onCancel={() => undefined}
          visual={{ icon: 'drop', tone: 'accent' }}
          title="Name it"
          body="So you can tell your devices apart."
          actions={<Button variant="primary">Continue</Button>}
        />
      ),
    },
  ],
};

export default examples;
