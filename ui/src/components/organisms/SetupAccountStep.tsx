import { useId, useState, type FormEvent } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/atoms/Button';
import { Icon } from '@/components/atoms/Icon';
import { Input } from '@/components/atoms/Input';
import { Notice } from '@/components/atoms/Notice';
import { StatusDot } from '@/components/atoms/StatusDot';
import { Field } from '@/components/molecules/Field';
import { ListRow } from '@/components/molecules/ListRow';
import { PasswordInput } from '@/components/molecules/PasswordInput';
import { WizardShell, type WizardShellProps } from '@/components/templates/WizardShell';
import { queryKeys } from '@/api/queryKeys';
import type { ServerInfo } from '@/api/types';
import { useCreateAdmin } from '@/hooks/useAuth';
import { issuerHost } from '@/lib/addressCheck';
import { errorCode, errorMessage } from '@/lib/errors';
import { SIGN_IN_DOCS_URL } from '@/lib/links';

export const MIN_PASSWORD_LENGTH = 12;
const WEAK_PASSWORD = 'Use at least 12 characters.';

export interface SetupAccountStepProps {
  auth: ServerInfo['auth'];
  /** `steps.auth` is done: the admin exists (basic) or the identity provider answers (oidc). */
  done: boolean;
  /** The admin created on this screen, for "Account created · {username}". */
  username: string | null;
  onCreated: (username: string) => void;
  /** Re-reads the step states, e.g. to test the identity provider again. */
  onRecheck: () => void;
  onContinue: () => void;
  shell: Pick<WizardShellProps, 'progress' | 'eyebrow'>;
}

const LEADS: Record<ServerInfo['auth']['mode'], (host: string) => string> = {
  basic: () => 'You’ll use this to sign in from your phone or computer.',
  oidc: (host) => `Sign-in is handled by ${host}.`,
  proxy: () => 'Sign-in is handled by your reverse proxy.',
  none: () => 'Anyone who can reach this page can use it. You can turn on sign-in later.',
};

/** Setup step 1 (v3 §12): create the admin (basic) or confirm how sign-in works in the other modes. */
export function SetupAccountStep({ auth, done, username, onCreated, onRecheck, onContinue, shell }: SetupAccountStepProps) {
  const formId = useId();
  const host = issuerHost(auth.oidc_issuer);
  const creating = auth.mode === 'basic' && !done;
  return (
    <WizardShell
      {...shell}
      title="Your account"
      body={LEADS[auth.mode](host)}
      actions={
        <>
          <Button
            type={creating ? 'submit' : 'button'}
            form={creating ? formId : undefined}
            variant="primary"
            disabled={auth.mode === 'oidc' && !done}
            onClick={creating ? undefined : onContinue}
          >
            Continue
          </Button>
          {auth.mode === 'oidc' && !done && (
            <Button variant="ghost" onClick={onRecheck}>
              Check again
            </Button>
          )}
        </>
      }
    >
      {creating && <AdminForm formId={formId} onCreated={onCreated} />}
      {auth.mode === 'basic' && done && (
        <Notice tone="ok" role="status" className="flex items-center gap-2">
          <Icon name="check" size={16} className="text-ok" />
          {username ? `Account created · ${username}` : 'Account created'}
        </Notice>
      )}
      {auth.mode === 'oidc' && (
        <ul className="m-0 list-none rounded-control border border-border px-3.5 py-1">
          <ListRow
            title={<span className="font-mono text-fg">{host}</span>}
            subtitle={done ? undefined : 'Check OPENFLO_OIDC_ISSUER and that the server can reach it.'}
            value={<StatusDot tone={done ? 'ok' : 'bad'} label={done ? 'Connected' : 'Can’t reach it'} />}
          />
        </ul>
      )}
      {auth.mode === 'none' && (
        <Notice tone="warn">
          <a href={SIGN_IN_DOCS_URL} target="_blank" rel="noreferrer" className="font-semibold text-accent-text">
            How to turn on sign-in
          </a>
        </Notice>
      )}
    </WizardShell>
  );
}

function AdminForm({ formId, onCreated }: { formId: string; onCreated: (username: string) => void }) {
  const queryClient = useQueryClient();
  const create = useCreateAdmin();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [tooShort, setTooShort] = useState(false);
  const code = errorCode(create.error);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const name = username.trim();
    if (!name) return;
    setTooShort(password.length < MIN_PASSWORD_LENGTH);
    if (password.length < MIN_PASSWORD_LENGTH) return;
    const result = await create.run({ username: name, password });
    if (result.ok) {
      setPassword('');
      onCreated(name);
    }
    // ALREADY_SET: another tab made the admin; refresh so the step shows it as done.
    if (result.ok || errorCode(result.error) === 'ALREADY_SET') void queryClient.invalidateQueries({ queryKey: queryKeys.setup });
  };

  return (
    <form id={formId} onSubmit={(event) => void submit(event)} className="flex flex-col gap-4" noValidate>
      <Field label="Username">
        <Input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" autoCapitalize="off" autoCorrect="off" spellCheck={false} maxLength={60} required />
      </Field>
      <Field label="Password" hint="At least 12 characters." error={tooShort || code === 'WEAK_PASSWORD' ? WEAK_PASSWORD : null}>
        <PasswordInput value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="new-password" maxLength={1024} required />
      </Field>
      {create.error !== null && code !== 'WEAK_PASSWORD' && code !== 'ALREADY_SET' && (
        <Notice tone="bad" role="alert">
          {errorMessage(create.error)}
        </Notice>
      )}
    </form>
  );
}
