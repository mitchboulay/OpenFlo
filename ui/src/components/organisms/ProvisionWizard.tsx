import { useEffect, useId, useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router';
import { Button, buttonClassName } from '@/components/atoms/Button';
import { Notice } from '@/components/atoms/Notice';
import { NameLocationFields } from '@/components/molecules/NameLocationFields';
import { StepList } from '@/components/molecules/StepList';
import { WizardShell } from '@/components/templates/WizardShell';
import { ApiError } from '@/api/client';
import type { HomeSummary } from '@/api/types';
import { useProvisioningAction, useProvisioningStatus, useResetTarget, useStartProvisioning } from '@/hooks/useProvisioning';
import { errorCode, errorMessage } from '@/lib/errors';
import { isOpenSession, numberedScreens, progressSteps, screenFor, type PhoneStep } from '@/lib/provisioning';
import { ProvisionPhoneStep, type Pairing } from './ProvisionPhoneStep';
import { ProvisionResetStep } from './ProvisionResetStep';

export interface ProvisionWizardProps {
  home: HomeSummary;
  /** The open session from the URL (`/homes/:id/add/:sessionId`), or null before one starts. */
  sessionId: number | null;
  /** Reset kind: the device being set up again (`?device=`). */
  targetDeviceId: string | null;
}

const LOCATION_SUGGESTIONS = ['Air handler, attic', 'Furnace, garage', 'Air handler, basement', 'Hall closet'] as const;

/** `WIZARD_OPEN` names the home's open session in `detail.session_id`. */
function openSessionId(error: unknown): number | null {
  if (!(error instanceof ApiError) || error.code !== 'WIZARD_OPEN') return null;
  const detail = error.detail as { session_id?: unknown } | undefined;
  return typeof detail?.session_id === 'number' ? detail.session_id : null;
}

/** The add-device wizard (FR-4, AD-4): details → (reset) → phone → live progress → done. */
export function ProvisionWizard({ home, sessionId, targetDeviceId }: ProvisionWizardProps) {
  const navigate = useNavigate();
  const resumed = (useLocation().state as { resumed?: boolean } | null)?.resumed === true;
  const formId = useId();
  const status = useProvisioningStatus(sessionId);
  const session = status.data?.session ?? null;
  const targetId = session?.target_device_id ?? targetDeviceId;
  const target = useResetTarget(targetId).data ?? null;
  const starter = useStartProvisioning();
  const cancel = useProvisioningAction(sessionId);
  // The token-bearing payloads live here only, and go when the wizard unmounts or the session ends.
  const [pairing, setPairing] = useState<Pairing | null>(null);
  const [phone, setPhone] = useState<PhoneStep>('join');
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const [draft, setDraft] = useState<{ name: string; location: string } | null>(null);

  const closed = session !== null && !isOpenSession(session.status);
  useEffect(() => {
    if (closed) setPairing(null);
  }, [closed]);

  const kind = targetId ? 'reset' : 'new';
  // An open session's labels win (it may be another tab's); before one, the operator's draft.
  const fields =
    sessionId !== null && session
      ? { name: session.device_name, location: session.location ?? '' }
      : (draft ?? { name: target?.name ?? '', location: target?.location ?? '' });
  const name = fields.name.trim() || 'Your iFLO';
  const search = targetId ? `?device=${encodeURIComponent(targetId)}` : '';
  const base = `/homes/${home.id}/add`;
  const exitTo = targetId ? `/devices/${encodeURIComponent(targetId)}` : `/homes/${home.id}`;
  const screen = screenFor(sessionId === null ? null : session, phone);
  const numbered = numberedScreens(kind);
  const index = numbered.indexOf(screen);
  const shell = {
    notice: resumed && session && isOpenSession(session.status) && (
      <Notice role="status">A setup was already in progress in this home, so you’re continuing it.</Notice>
    ),
    progress: index >= 0 && screen !== 'done' ? { current: index + 1, total: numbered.length } : undefined,
    onCancel: screen === 'details' ? () => navigate(exitTo) : () => setConfirmingCancel(true),
  };

  const restart = (keepDetails: boolean) => {
    setPairing(null);
    setPhone('join');
    setConfirmingCancel(false);
    setDraft(keepDetails ? fields : { name: '', location: '' });
    navigate(`${base}${search}`, { replace: true });
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!fields.name.trim()) return;
    const result = await starter.start({
      home_id: home.id,
      kind,
      target_device_id: targetId,
      device_name: fields.name.trim(),
      location: fields.location.trim() || null,
    });
    if (result.ok) {
      setPairing({ pairingUrl: result.created.pairing_url, wifiQr: result.created.wifi_qr });
      setPhone('join');
      navigate(`${base}/${result.created.session.id}${search}`, { replace: true });
      return;
    }
    const openId = openSessionId(result.error);
    if (openId !== null) navigate(`${base}/${openId}${search}`, { replace: true, state: { resumed: true } });
  };

  if (sessionId !== null && !session) {
    return (
      <WizardShell
        visual={{ icon: status.isError ? 'warning' : 'clock', tone: status.isError ? 'warn' : 'neutral' }}
        title={status.isError ? 'Couldn’t load this setup' : 'Loading setup…'}
        body={status.isError ? errorMessage(status.error) : undefined}
        actions={status.isError && <Link to={exitTo} className={buttonClassName('primary')}>Back to {home.name}</Link>}
      />
    );
  }

  // Shown at once, even while a just-created session is still loading; only "Stop setup" needs it.
  if (confirmingCancel && (!session || isOpenSession(session.status))) {
    const wasReset = !!session && session.kind === 'reset' && session.status !== 'awaiting_reset';
    return (
      <WizardShell
        visual={{ icon: 'clock', tone: 'neutral' }}
        title="Stop setting up?"
        body={wasReset ? 'The device was already reset. It waits in setup mode until you start again.' : 'Nothing on the device changes. You can start again any time.'}
        actions={
          <>
            <Button variant="primary" onClick={() => setConfirmingCancel(false)}>Keep going</Button>
            <Button variant="ghost" disabled={cancel.isPending || !session} onClick={() => cancel.mutate('cancel', { onSuccess: () => navigate(exitTo) })}>
              Stop setup
            </Button>
          </>
        }
      >
        {cancel.isError && <Notice tone="bad" role="alert">{errorMessage(cancel.error)}</Notice>}
      </WizardShell>
    );
  }

  switch (screen) {
    case 'details':
      return (
        <WizardShell
          {...shell}
          visual={{ icon: 'drop', tone: 'accent' }}
          title={kind === 'reset' ? 'Move to a new network' : 'Name it'}
          body={kind === 'reset' ? 'Keep the name, or change it while you’re here.' : 'So you can tell your devices apart.'}
          actions={<Button type="submit" form={formId} variant="primary" disabled={!fields.name.trim() || starter.pending}>Continue</Button>}
        >
          <form id={formId} onSubmit={(event) => void submit(event)} className="flex flex-col gap-4">
            <NameLocationFields
              name={fields.name}
              location={fields.location}
              onNameChange={(value) => setDraft({ ...fields, name: value })}
              onLocationChange={(value) => setDraft({ ...fields, location: value })}
              suggestions={LOCATION_SUGGESTIONS}
            />
          </form>
          {errorCode(starter.error) === 'ADDRESS_UNVERIFIED' ? (
            <Notice tone="bad" role="alert">
              {errorMessage(starter.error)}{' '}
              <Link to="/settings" className="font-semibold text-accent-text">Open Settings</Link>
            </Notice>
          ) : (
            starter.error !== null && openSessionId(starter.error) === null && <Notice tone="bad" role="alert">{errorMessage(starter.error)}</Notice>
          )}
        </WizardShell>
      );
    case 'reset':
      return session && <ProvisionResetStep session={session} nextExpectedSync={status.data?.next_expected_sync ?? null} timeZone={home.timezone} shell={shell} />;
    case 'join':
    case 'open':
      return (
        <ProvisionPhoneStep
          step={screen}
          pairing={pairing}
          shell={shell}
          onNext={() => setPhone(screen === 'join' && pairing ? 'open' : 'waiting')}
          onStartOver={() => cancel.mutate('cancel', { onSettled: () => restart(true) })}
        />
      );
    case 'progress':
      return (
        <WizardShell {...shell} visual={{ icon: 'wifi', tone: 'accent' }} title={`Connecting ${name}`} body="Keep the device nearby. This usually takes under a minute.">
          {session && <StepList label="Setup progress" steps={progressSteps(session.kind, session.status)} />}
        </WizardShell>
      );
    case 'done':
      return (
        <WizardShell
          visual={{ icon: 'check', tone: 'ok' }}
          title={kind === 'reset' ? `${name} is on the new network.` : `${name} is ready.`}
          body={kind === 'reset' ? undefined : 'Next, set the bottle level.'}
          actions={
            <>
              {session?.bound_device_id && (
                <Link to={`/devices/${encodeURIComponent(session.bound_device_id)}`} className={buttonClassName('primary')}>Go to {name}</Link>
              )}
              {kind === 'new' && <Button variant="ghost" onClick={() => restart(false)}>Add another</Button>}
            </>
          }
        />
      );
    case 'expired':
    case 'cancelled':
      return (
        <WizardShell
          visual={{ icon: 'clock', tone: 'warn' }}
          title={screen === 'expired' ? 'This setup timed out.' : 'This setup was stopped.'}
          body={
            screen === 'expired'
              ? 'The device didn’t finish connecting in time. Nothing was changed. Make sure your phone saved the network, then start again.'
              : 'Someone stopped it. You can start again any time.'
          }
          actions={
            <>
              <Button variant="primary" onClick={() => restart(true)}>Start again</Button>
              <Link to={exitTo} className={buttonClassName('ghost')}>Back to {targetId ? name : home.name}</Link>
            </>
          }
        />
      );
  }
}
