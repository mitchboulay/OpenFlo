import { useState, type FormEvent } from 'react';
import { Input } from '@/components/atoms/Input';
import { Field } from '@/components/molecules/Field';
import { useSaveServerAddress } from '@/hooks/useServer';
import { SERVER_ADDRESS_COPY, validateServerAddress } from '@/lib/addressCheck';
import { errorMessage } from '@/lib/errors';

export interface ServerAddressFormProps {
  /** Lets a submit button outside the form (wizard actions, sheet footer) submit it. */
  formId: string;
  initial: string | null;
  /** After the API saved (and normalized) the address. */
  onSaved: (address: string) => void;
}

/** The server address field with its client check (`https://` and a host), shared by setup and Settings. */
export function ServerAddressForm({ formId, initial, onSaved }: ServerAddressFormProps) {
  const [value, setValue] = useState(initial ?? '');
  const [invalid, setInvalid] = useState<string | null>(null);
  const save = useSaveServerAddress();

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const problem = validateServerAddress(value);
    setInvalid(problem);
    if (problem) return;
    // A repeated PUT of the same address is harmless, so the submit button stays simple.
    save.mutate(value.trim(), { onSuccess: ({ server_address }) => onSaved(server_address) });
  };

  return (
    <form id={formId} onSubmit={submit} noValidate>
      <Field label={SERVER_ADDRESS_COPY.label} hint={SERVER_ADDRESS_COPY.hint} error={invalid ?? (save.isError ? errorMessage(save.error) : null)}>
        <Input
          value={value}
          onChange={(event) => setValue(event.target.value)}
          type="url"
          inputMode="url"
          autoComplete="url"
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
          placeholder={SERVER_ADDRESS_COPY.placeholder}
          maxLength={2048}
        />
      </Field>
    </form>
  );
}
