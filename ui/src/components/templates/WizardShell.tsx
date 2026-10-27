import { useEffect, useRef, type ReactNode } from 'react';
import { Button } from '@/components/atoms/Button';
import { Icon, type IconName } from '@/components/atoms/Icon';
import { StepDots } from '@/components/molecules/StepDots';
import { cn } from '@/lib/cn';

export type WizardVisualTone = 'accent' | 'ok' | 'warn' | 'neutral';

export interface WizardShellProps {
  /** Step dots and "Step 2 of 5"; omit on end states (done, timed out). */
  progress?: { current: number; total: number };
  /** Shows "Cancel" in the top bar. */
  onCancel?: () => void;
  /** The large tile above the title. Omit when the step has its own visual (a QR code). */
  visual?: { icon: IconName; tone: WizardVisualTone };
  /** Small dim line above the title, e.g. "Set up OpenFLO". */
  eyebrow?: string;
  title: string;
  body?: ReactNode;
  /** A status line above the content, e.g. "You're continuing a setup already in progress". */
  notice?: ReactNode;
  /** The step's content: fields, QR card, progress list. */
  children?: ReactNode;
  /** One primary action, then at most one secondary, stacked full width at the bottom. */
  actions?: ReactNode;
}

const VISUAL_TONES: Record<WizardVisualTone, string> = {
  accent: 'bg-accent-soft text-accent-text',
  ok: 'bg-ok-soft text-ok',
  warn: 'bg-warn-soft text-warn',
  neutral: 'bg-surface2 text-dim',
};

/**
 * Full-screen guided flow on phone, a centered card at `sm`+: one instruction per screen.
 * Focus moves to the title on every step so screen readers announce it.
 */
export function WizardShell({ progress, onCancel, visual, eyebrow, title, body, notice, children, actions }: WizardShellProps) {
  const titleRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => titleRef.current?.focus(), [title]);

  return (
    <div className="flex min-h-dvh flex-col sm:items-center sm:justify-center sm:p-6">
      <div className="flex w-full flex-1 flex-col sm:max-w-[480px] sm:flex-none sm:rounded-sheet sm:border sm:border-card-border sm:bg-surface sm:shadow-card">
        <div className="flex h-16 items-center gap-3 px-4">
          <div className="flex-1">{progress && <StepDots current={progress.current} total={progress.total} />}</div>
          {onCancel && (
            <Button variant="ghost" onClick={onCancel}>
              Cancel
            </Button>
          )}
        </div>
        <main className="flex flex-1 flex-col gap-6 px-5 pt-3 pb-8">
          {visual && (
            <div
              aria-hidden="true"
              className={cn('mt-4 flex size-[148px] items-center justify-center self-center rounded-[44px]', VISUAL_TONES[visual.tone])}
            >
              <Icon name={visual.icon} size={64} strokeWidth={1.4} />
            </div>
          )}
          <div className="flex flex-col gap-2 text-center">
            {eyebrow && <p className="m-0 text-sm font-medium text-dim">{eyebrow}</p>}
            <h1 ref={titleRef} tabIndex={-1} className="m-0 text-[30px] leading-tight font-semibold tracking-tight text-balance outline-none">
              {title}
            </h1>
            {body && <div className="text-base text-pretty text-dim">{body}</div>}
          </div>
          {notice}
          {children}
          <div className="flex-1" />
          {actions && <div className="flex flex-col gap-2 [&>*]:w-full">{actions}</div>}
        </main>
      </div>
    </div>
  );
}
