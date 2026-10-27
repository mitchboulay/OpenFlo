import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import { Button, buttonClassName } from '@/components/atoms/Button';
import { Input } from '@/components/atoms/Input';
import { Notice } from '@/components/atoms/Notice';
import { Field } from '@/components/molecules/Field';
import { PasswordInput } from '@/components/molecules/PasswordInput';
import { WizardShell } from '@/components/templates/WizardShell';
import { ApiError } from '@/api/client';
import type { ServerInfo } from '@/api/types';
import { useLogin } from '@/hooks/useAuth';
import { issuerHost } from '@/lib/addressCheck';
import { errorMessage } from '@/lib/errors';

export interface SignInFormProps {
  info: ServerInfo;
  /** Where to go after signing in (already checked to be a path in this app). */
  next: string;
  /** `?error=` on return from the identity provider. */
  returnError: string | null;
}

/** Without `Retry-After` detail, the login limit is 5 per minute. */
const DEFAULT_LOCKOUT_S = 60;
const GROUP_DENIED_CODES = new Set(['OIDC_GROUP_DENIED', 'GROUP_DENIED']);

function retryAfterSeconds(error: ApiError): number {
  const detail = error.detail as { retry_after_seconds?: unknown } | undefined;
  const seconds = detail?.retry_after_seconds;
  return typeof seconds === 'number' && seconds > 0 ? Math.ceil(seconds) : DEFAULT_LOCKOUT_S;
}

/** Seconds left until `until` (epoch ms), ticking each second; 0 once passed or with no lockout. */
function useSecondsLeft(until: number | null): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (until === null) return undefined;
    setNow(Date.now());
    const timer = window.setInterval(() => {
      const tick = Date.now();
      setNow(tick);
      if (tick >= until) window.clearInterval(timer);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [until]);
  return until === null ? 0 : Math.max(0, Math.ceil((until - now) / 1000));
}

/** Sign-in (v3 §13): username and password (basic), the identity provider (oidc), or a reload (proxy). */
export function SignInForm({ info, next, returnError }: SignInFormProps) {
  const footer = <p className="m-0 text-center text-[12.5px] text-faint">OpenFLO {info.version}</p>;
  const { mode } = info.auth;

  if (mode === 'proxy') {
    return (
      <WizardShell
        title="Your proxy didn’t sign you in"
        body="Reload the page."
        actions={
          <>
            <Button variant="primary" onClick={() => window.location.reload()}>
              Reload
            </Button>
            {footer}
          </>
        }
      />
    );
  }

  if (mode === 'oidc') {
    const host = issuerHost(info.auth.oidc_issuer);
    return (
      <WizardShell
        title="Sign in"
        notice={
          returnError && (
            <Notice tone="bad" role="alert">
              {GROUP_DENIED_CODES.has(returnError)
                ? 'Your account isn’t allowed to use OpenFLO. Ask the person who runs it.'
                : 'Sign-in didn’t finish. Try again.'}
            </Notice>
          )
        }
        actions={
          <>
            <a href={`/api/v1/auth/oidc/login?next=${encodeURIComponent(next)}`} className={buttonClassName('primary')}>
              Sign in with {host}
            </a>
            {footer}
          </>
        }
      />
    );
  }

  return <PasswordSignIn next={next} footer={footer} />;
}

function PasswordSignIn({ next, footer }: { next: string; footer: ReactNode }) {
  const formId = useId();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const login = useLogin();
  const passwordRef = useRef<HTMLInputElement>(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [lockedUntil, setLockedUntil] = useState<number | null>(null);
  const secondsLeft = useSecondsLeft(lockedUntil);
  const error = login.error instanceof ApiError ? login.error : null;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!username.trim() || !password) return;
    const result = await login.run({ username: username.trim(), password });
    setPassword('');
    if (result.ok) {
      await queryClient.invalidateQueries(); // anything that failed with 401 refetches as this user
      navigate(next, { replace: true });
      return;
    }
    if (result.error instanceof ApiError && result.error.status === 429) {
      setLockedUntil(Date.now() + retryAfterSeconds(result.error) * 1000);
    }
    passwordRef.current?.focus();
  };

  const message =
    error?.code === 'INVALID_CREDENTIALS'
      ? 'That username and password don’t match.'
      : error?.code === 'RATE_LIMITED'
        ? 'Too many attempts. Try again in a minute.'
        : error?.status === 0
          ? 'Can’t reach OpenFLO. Check your connection.'
          : login.error
            ? errorMessage(login.error)
            : null;

  return (
    <WizardShell
      title="Sign in"
      notice={
        message && (
          <Notice tone="bad" role="alert">
            {message}
          </Notice>
        )
      }
      actions={
        <>
          <Button type="submit" form={formId} variant="primary" disabled={login.pending || secondsLeft > 0}>
            {secondsLeft > 0 ? `Try again in ${secondsLeft} s` : 'Sign in'}
          </Button>
          {footer}
        </>
      }
    >
      <form id={formId} onSubmit={(event) => void submit(event)} className="flex flex-col gap-4" noValidate>
        <Field label="Username">
          <Input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" autoCapitalize="off" autoCorrect="off" spellCheck={false} maxLength={60} required />
        </Field>
        <Field label="Password">
          <PasswordInput ref={passwordRef} value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" maxLength={1024} required />
        </Field>
      </form>
    </WizardShell>
  );
}
