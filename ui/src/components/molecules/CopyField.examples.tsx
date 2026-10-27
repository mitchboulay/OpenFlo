import type { ExampleSet } from '@/types/examples';
import { CopyField } from './CopyField';

const examples: ExampleSet = {
  title: 'CopyField',
  examples: [
    { name: 'token', render: () => <CopyField label="New token" value="ofl_example_not_a_real_token_0123456789abcdef" /> },
  ],
};

export default examples;
