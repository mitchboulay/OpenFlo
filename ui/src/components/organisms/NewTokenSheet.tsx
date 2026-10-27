import { useId, useState, type FormEvent } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/atoms/Button';
import { Input } from '@/components/atoms/Input';
import { Notice } from '@/components/atoms/Notice';
import { CopyField } from '@/components/molecules/CopyField';
import { Field } from '@/components/molecules/Field';
import { Sheet } from '@/components/templates/Sheet';
import { queryKeys } from '@/api/queryKeys';
import { useCreateToken } from '@/hooks/useAuth';
import { errorMessage } from '@/lib/errors';

export interface NewTokenSheetProps {
  open: boolean;
  onClose: () => void;
}

/**
 * Create an API token, then show it once (FR-15). The plaintext lives in this component's state
 * only and is dropped on close, like the pairing token in the add-device wizard.
 */
export function NewTokenSheet({ open, onClose }: NewTokenSheetProps) {
  const formId = useId();
  const queryClient = useQueryClient();
  const create = useCreateToken();
  const [name, setName] = useState('');
  const [token, setToken] = useState<string | null>(null);
  const trimmed = name.trim();

  const close = () => {
    setToken(null);
    setName('');
    create.reset();
    onClose();
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!trimmed) return;
    const result = await create.run({ name: trimmed });
    if (!result.ok) return;
    setToken(result.value.token);
    void queryClient.invalidateQueries({ queryKey: queryKeys.tokens });
  };

  return (
    <Sheet
      open={open}
      onClose={close}
      title={token ? 'Copy your token' : 'New token'}
      footer={
        token ? (
          <Button variant="primary" onClick={close}>
            Done
          </Button>
        ) : (
          <Button type="submit" form={formId} variant="primary" disabled={!trimmed || create.pending}>
            Create
          </Button>
        )
      }
    >
      {token ? (
        <div className="flex flex-col gap-3">
          <CopyField label="New token" value={token} />
          <Notice tone="warn">You won’t see this again. Store it somewhere safe.</Notice>
        </div>
      ) : (
        <form id={formId} onSubmit={(event) => void submit(event)}>
          <Field label="Name" hint="The script or app that will use it." error={create.error ? errorMessage(create.error) : null}>
            <Input value={name} onChange={(event) => setName(event.target.value)} maxLength={60} placeholder="Home Assistant" autoComplete="off" required />
          </Field>
        </form>
      )}
    </Sheet>
  );
}
