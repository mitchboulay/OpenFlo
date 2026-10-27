import { useState } from 'react';
import { Button } from '@/components/atoms/Button';
import { Notice } from '@/components/atoms/Notice';
import { QrCard } from '@/components/molecules/QrCard';
import { WizardShell, type WizardShellProps } from '@/components/templates/WizardShell';
import { pairingOrigin, wifiNetworkName } from '@/lib/provisioning';

/** The token-bearing payloads from `POST /provisioning`. Component state only; never cached or stored. */
export interface Pairing {
  pairingUrl: string;
  wifiQr: string;
}

export interface ProvisionPhoneStepProps {
  /** `join`: the hotspot's Wi-Fi QR. `open`: the pairing link's QR and "Copy link". */
  step: 'join' | 'open';
  /** Null when this screen didn't open the session (resumed or reloaded): the codes were shown once. */
  pairing: Pairing | null;
  shell: Pick<WizardShellProps, 'progress' | 'onCancel' | 'notice'>;
  onNext: () => void;
  /** Cancels this session and starts a new one (new codes). */
  onStartOver: () => void;
}

type CopyState = 'idle' | 'copied' | 'failed';

/** "Use your phone" (FR-4): join the device's hotspot, then open its setup page with the one-time link. */
export function ProvisionPhoneStep({ step, pairing, shell, onNext, onStartOver }: ProvisionPhoneStepProps) {
  const [copy, setCopy] = useState<CopyState>('idle');
  const join = step === 'join';

  const copyLink = (link: string) =>
    navigator.clipboard.writeText(link).then(
      () => setCopy('copied'),
      () => setCopy('failed'),
    );

  if (!pairing) {
    return (
      <WizardShell
        {...shell}
        visual={{ icon: 'warning', tone: 'warn' }}
        title="Use your phone"
        body="The setup codes are shown only once, on the screen that started this setup."
        actions={
          <>
            <Button variant="primary" onClick={onNext}>
              I’ve finished on my phone
            </Button>
            <Button variant="ghost" onClick={onStartOver}>
              Start over with new codes
            </Button>
          </>
        }
      >
        <Notice>If your phone already finished the setup page, continue. Otherwise start over to get new codes.</Notice>
      </WizardShell>
    );
  }

  const network = wifiNetworkName(pairing.wifiQr) ?? 'the device’s hotspot';
  return (
    <WizardShell
      {...shell}
      title={join ? 'Join the device’s Wi-Fi' : 'Open the setup page'}
      body={
        join
          ? 'Scan with your phone’s camera to join the hotspot your iFLO is broadcasting.'
          : 'Scan again, then choose your home’s Wi-Fi network and enter its password.'
      }
      actions={
        <Button variant="primary" onClick={onNext}>
          {join ? 'I’ve joined it' : 'I’ve finished on my phone'}
        </Button>
      }
    >
      {join ? (
        <QrCard value={pairing.wifiQr} label={`QR code to join Wi-Fi network ${network}`} caption="Network" displayValue={network} />
      ) : (
        <QrCard
          value={pairing.pairingUrl}
          label="QR code to open the iFLO setup page"
          caption="Setup page"
          displayValue={pairingOrigin(pairing.pairingUrl)}
          action={
            <div className="flex flex-col items-center gap-1">
              <Button variant="ghost" onClick={() => void copyLink(pairing.pairingUrl)}>
                Copy link
              </Button>
              <p role="status" className="m-0 min-h-5 text-sm text-dim">
                {copy === 'copied' ? 'Link copied. Open it on the phone that joined the hotspot.' : copy === 'failed' ? 'Couldn’t copy. Scan the code instead.' : ''}
              </p>
            </div>
          }
        />
      )}
      <Notice>
        {join
          ? 'Use your phone: it works best. It leaves your home Wi-Fi for a minute; that’s expected.'
          : 'Keep this page open. When you tap Save on your phone, come back here.'}
      </Notice>
    </WizardShell>
  );
}
