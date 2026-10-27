import type { ExampleSet } from '@/types/examples';
import { Select } from './Select';

const examples: ExampleSet = {
  title: 'Select',
  examples: [
    {
      name: 'time zone',
      render: () => (
        <Select aria-label="Time zone" defaultValue="America/New_York">
          <option value="America/New_York">America/New York</option>
          <option value="America/Chicago">America/Chicago</option>
        </Select>
      ),
    },
  ],
};

export default examples;
