import { useState } from 'react';
import type { ExampleSet } from '@/types/examples';
import { NameLocationFields } from './NameLocationFields';

function Example({ suggestions, error }: { suggestions?: string[]; error?: string }) {
  const [name, setName] = useState('Attic unit');
  const [location, setLocation] = useState('');
  return (
    <NameLocationFields
      name={name}
      location={location}
      onNameChange={setName}
      onLocationChange={setLocation}
      suggestions={suggestions}
      error={error}
    />
  );
}

const examples: ExampleSet = {
  title: 'NameLocationFields',
  examples: [
    { name: 'plain', render: () => <Example /> },
    { name: 'with suggestions', render: () => <Example suggestions={['Air handler, attic', 'Furnace, garage', 'Hall closet']} /> },
    { name: 'with an error', render: () => <Example error="Someone already added this device." /> },
  ],
};

export default examples;
