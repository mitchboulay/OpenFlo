import { useState } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { MAX_DEVICE_NAME, NameLocationFields } from './NameLocationFields';

function Harness({ error }: { error?: string }) {
  const [name, setName] = useState('');
  const [location, setLocation] = useState('');
  return (
    <NameLocationFields
      name={name}
      location={location}
      onNameChange={setName}
      onLocationChange={setLocation}
      error={error}
      suggestions={['Air handler, attic', 'Hall closet']}
    />
  );
}

describe('NameLocationFields', () => {
  it('edits both labels and fills the location from a suggestion', async () => {
    render(<Harness />);
    await userEvent.type(screen.getByLabelText('Name'), 'Attic unit');
    expect(screen.getByLabelText('Name')).toHaveValue('Attic unit');
    expect(screen.getByLabelText('Name')).toHaveAttribute('maxLength', String(MAX_DEVICE_NAME));
    await userEvent.click(screen.getByRole('button', { name: 'Hall closet' }));
    expect(screen.getByLabelText('Where is it?')).toHaveValue('Hall closet');
    expect(screen.getByRole('button', { name: 'Hall closet' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('announces an error against the name', () => {
    render(<Harness error="Someone already added this device." />);
    expect(screen.getByRole('alert')).toHaveTextContent('Someone already added this device.');
    expect(screen.getByLabelText('Name')).toHaveAttribute('aria-invalid', 'true');
  });
});
