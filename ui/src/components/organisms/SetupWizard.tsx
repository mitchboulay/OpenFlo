import { useEffect, useId, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/atoms/Button';
import { Notice } from '@/components/atoms/Notice';
import { WizardShell } from '@/components/templates/WizardShell';
import type { ServerInfo } from '@/api/types';
import { patchServerInfo, useCompleteSetup, useSetupStatus } from '@/hooks/useServer';
import { errorMessage } from '@/lib/errors';
import { QueryBoundary } from './QueryBoundary';
import { ServerAddressForm } from './ServerAddressForm';
import { SetupAccountStep } from './SetupAccountStep';
import { SetupCheckStep } from './SetupCheckStep';

export interface SetupWizardProps {
  info: ServerInfo;
}

type Step = 'account' | 'address' | 'check' | 'done';
const DOTS: Record<Exclude<Step, 'done'>, number> = { account: 1, address: 2, check: 3 };
const EYEBROW = 'Set up OpenFLO';

/** First-run setup (FR-16, v3 §12): account → server address → address check → done, in every auth mode. */
export function SetupWizard({ info }: SetupWizardProps) {
  const queryClient = useQueryClient();
  const addressFormId = useId();
  const setup = useSetupStatus();
  const complete = useCompleteSetup();
  const [step, setStep] = useState<Step>('account');
  const [username, setUsername] = useState<string | null>(null);
  const [address, setAddress] = useState(info.server_address);

  // Another tab may have finished setup since boot; the step status says so, and the gate moves on.
  const finished = setup.data?.setup_state === 'ready';
  useEffect(() => {
    if (finished) patchServerInfo(queryClient, { setup_state: 'ready' });
  }, [finished, queryClient]);

  const shell = { eyebrow: EYEBROW, progress: step === 'done' ? undefined : { current: DOTS[step], total: 3 } };

  if (!setup.data) {
    return (
      <WizardShell {...shell} title="Your account">
        <QueryBoundary query={setup} what="setup">
          {() => null}
        </QueryBoundary>
      </WizardShell>
    );
  }

  if (step === 'account') {
    return (
      <SetupAccountStep
        auth={info.auth}
        done={setup.data.steps.auth === 'done'}
        username={username}
        onCreated={(name) => {
          setUsername(name);
          setStep('address');
        }}
        onRecheck={() => void setup.refetch()}
        onContinue={() => setStep('address')}
        shell={shell}
      />
    );
  }

  if (step === 'address' || !address) {
    return (
      <WizardShell
        {...shell}
        title="Where devices find OpenFLO"
        body="Your iFLO devices use this address to reach OpenFLO, from anywhere. A device keeps it until it’s set up again."
        actions={
          <Button type="submit" form={addressFormId} variant="primary">
            Check address
          </Button>
        }
      >
        <ServerAddressForm
          formId={addressFormId}
          initial={address}
          onSaved={(saved) => {
            setAddress(saved);
            setStep('check');
          }}
        />
      </WizardShell>
    );
  }

  if (step === 'check') {
    return <SetupCheckStep address={address} onChange={() => setStep('address')} onContinue={() => setStep('done')} shell={shell} />;
  }

  const failed = setup.data.steps.address_check === 'fail';
  return (
    <WizardShell
      visual={{ icon: 'check', tone: 'accent' }}
      title="OpenFLO is ready"
      body={
        <>
          <p className="m-0">Add your first home, then your first device.</p>
          {failed && <p className="m-0 mt-2 text-sm">Adding a device unlocks once the address check passes. You can re-run it in Settings.</p>}
        </>
      }
      notice={
        complete.isError && (
          <Notice tone="bad" role="alert">
            {errorMessage(complete.error)}
          </Notice>
        )
      }
      actions={
        <Button
          variant="primary"
          disabled={complete.isPending}
          // Once ready, the boot gate leaves /setup for Homes with Add home open.
          onClick={() => complete.mutate(undefined, { onSuccess: ({ setup_state }) => patchServerInfo(queryClient, { setup_state }) })}
        >
          Add a home
        </Button>
      }
    />
  );
}
