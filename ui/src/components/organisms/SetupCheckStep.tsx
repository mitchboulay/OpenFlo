import { useEffect, useRef } from 'react';
import { Button } from '@/components/atoms/Button';
import { Notice } from '@/components/atoms/Notice';
import { CheckList } from '@/components/molecules/CheckList';
import { WizardShell, type WizardShellProps } from '@/components/templates/WizardShell';
import { useRunAddressCheck } from '@/hooks/useServer';
import { checkRows, checkVerdict, pendingRows, VERDICT_TITLES, type CheckVerdict } from '@/lib/addressCheck';

export interface SetupCheckStepProps {
  address: string;
  /** Back to the address step. */
  onChange: () => void;
  onContinue: () => void;
  shell: Pick<WizardShellProps, 'progress' | 'eyebrow'>;
}

const LEADS: Record<CheckVerdict, string | null> = {
  ok: null,
  warn: 'You can continue. Devices may have trouble until the warnings are fixed.',
  fail: 'You can finish setup, but adding a device stays off until this passes.',
};

/**
 * Setup step 3 (v3 §12): runs the server's device-view checks on arrival; the verdict becomes the
 * title. Failures never block finishing (FR-16); they block adding devices.
 */
export function SetupCheckStep({ address, onChange, onContinue, shell }: SetupCheckStepProps) {
  const run = useRunAddressCheck();
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    run.mutate();
  }, [run]);

  const result = run.isPending ? null : (run.data ?? null);
  const verdict = result && checkVerdict(result);
  const rows = result ? checkRows(result) : pendingRows(address, run.isError ? 'skipped' : 'checking');

  return (
    <WizardShell
      {...shell}
      title={verdict ? VERDICT_TITLES[verdict] : 'Checking your address'}
      body={verdict ? LEADS[verdict] : null}
      actions={
        <>
          <Button variant="primary" disabled={!result} onClick={onContinue}>
            Continue
          </Button>
          <Button variant="ghost" disabled={run.isPending} onClick={() => run.mutate()}>
            Check again
          </Button>
        </>
      }
    >
      <div className="flex items-center justify-between gap-3">
        <span className="min-w-0 font-mono text-sm [overflow-wrap:anywhere]">{address}</span>
        <Button variant="ghost" onClick={onChange}>
          Change
        </Button>
      </div>
      {run.isError && (
        <Notice tone="bad" role="alert">
          Couldn’t run the check. Check again.
        </Notice>
      )}
      <div aria-busy={run.isPending}>
        <CheckList label="Address check" rows={rows} />
      </div>
    </WizardShell>
  );
}
