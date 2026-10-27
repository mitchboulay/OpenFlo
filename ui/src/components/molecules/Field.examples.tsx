import { Input } from '@/components/atoms/Input';
import type { ExampleSet } from '@/types/examples';
import { Field } from './Field';

const examples: ExampleSet = {
  title: 'Field',
  examples: [
    {
      name: 'with hint',
      render: () => (
        <Field label="Location" hint="Where it is, so you can find it later.">
          <Input placeholder="Air handler, attic" />
        </Field>
      ),
    },
    {
      name: 'with error',
      render: () => (
        <Field label="Name" error="You already have a home with that name.">
          <Input defaultValue="Lab" />
        </Field>
      ),
    },
  ],
};

export default examples;
