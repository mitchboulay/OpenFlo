import { useState } from 'react';
import { Button } from '@/components/atoms/Button';
import { Notice } from '@/components/atoms/Notice';
import { WizardShell, type WizardShellProps } from '@/components/templates/WizardShell';
import type { ProvisioningSession } from '@/api/types';
import { useProvisioningAction } from '@/hooks/useProvisioning';
import { errorMessage } from '@/lib/errors';
import { formatWhen, zoneLabel } from '@/lib/time';

export interface ProvisionResetStepProps {
  session: ProvisioningSession;
  /** When the device next checks in (from the session status). */
  nextExpectedSync: string | null;
  timeZone: string;
  shell: Pick<WizardShellProps, 'progress' | 'onCancel' | 'notice'>;
}

/**
 * Reset kind only (FR-4): the server resets the device over the LAN while it is awake (`reset_mode: lan`),
 * otherwise the operator holds its reset button and confirms.
 */
export function ProvisionResetStep({ session, nextExpectedSync, timeZone, shell }: ProvisionResetStepProps) {
  const [holdButton, setHoldButton] = useState(false);
  const action = useProvisioningAction(session.id);
  const lanFailed = session.reset_result !== null && !session.reset_result.startsWith('ok');
  const lan = session.reset_mode === 'lan' && !holdButton;
  const nextCheckIn = formatWhen(nextExpectedSync, timeZone);
  const zone = zoneLabel(timeZone);

  return (
    <WizardShell
      {...shell}
      visual={{ icon: 'refresh', tone: 'accent' }}
      title="Reset it"
      body={nextCheckIn ? `It next checks in around ${nextCheckIn}${zone ? ` ${zone}` : ''}.` : 'It hasn’t checked in yet.'}
      actions={
        lan ? (
          <>
            <Button variant="primary" disabled={action.isPending} onClick={() => action.mutate('reset')}>
              Reset now
            </Button>
            <Button variant="ghost" onClick={() => setHoldButton(true)}>
              I’ll hold the reset button
            </Button>
          </>
        ) : (
          <Button variant="primary" disabled={action.isPending} onClick={() => action.mutate('manual-reset')}>
            I’ve reset it
          </Button>
        )
      }
    >
      {lanFailed && <Notice tone="warn">Couldn’t reach the device. Hold its reset button instead.</Notice>}
      <p className="m-0 text-center text-pretty">
        {lan
          ? 'OpenFLO can reset it over your network while it’s awake. To wake it now, twist the bottle.'
          : 'Hold the reset button on the device for a few seconds until its light changes, then tap “I’ve reset it”.'}
      </p>
      {action.isError && (
        <Notice tone="bad" role="alert">
          {errorMessage(action.error)}
        </Notice>
      )}
    </WizardShell>
  );
}
