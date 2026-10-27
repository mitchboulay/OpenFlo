import type { ExampleSet } from '@/types/examples';
import { Field } from './Field';
import { PasswordInput } from './PasswordInput';

const examples: ExampleSet = {
  title: 'PasswordInput',
  examples: [
    {
      name: 'new password',
      render: () => (
        <Field label="Password" hint="At least 12 characters.">
          <PasswordInput autoComplete="new-password" />
        </Field>
      ),
    },
    {
      name: 'with an error',
      render: () => (
        <Field label="Password" error="Use at least 12 characters.">
          <PasswordInput autoComplete="new-password" defaultValue="short" />
        </Field>
      ),
    },
  ],
};

export default examples;
