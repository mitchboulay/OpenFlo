import type { ExampleSet } from '@/types/examples';
import { Input } from './Input';

const examples: ExampleSet = {
  title: 'Input',
  examples: [
    { name: 'text', render: () => <Input aria-label="Name" placeholder="Main house" /> },
    { name: 'decimal', render: () => <Input aria-label="Measured" type="text" inputMode="decimal" defaultValue="181" /> },
    { name: 'invalid', render: () => <Input aria-label="Name" aria-invalid defaultValue="" /> },
  ],
};

export default examples;
