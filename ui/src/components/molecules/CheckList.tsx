import { StatusDot } from '@/components/atoms/StatusDot';
import { cn } from '@/lib/cn';
import type { CheckRowModel, CheckRowState } from '@/lib/addressCheck';
import type { Tone } from '@/types/tone';

export interface CheckListProps {
  /** Accessible name of the list, e.g. "Address check". */
  label: string;
  rows: readonly CheckRowModel[];
}

const STATES: Record<CheckRowState, { tone: Tone; label: string }> = {
  ok: { tone: 'ok', label: 'OK' },
  warn: { tone: 'warn', label: 'Warning' },
  fail: { tone: 'bad', label: 'Problem' },
  checking: { tone: 'neutral', label: 'Checking…' },
  skipped: { tone: 'neutral', label: 'Not checked' },
};

/** `backticks` mark words to type (config keys), set in mono so they don't read as explanation. */
function Line({ text }: { text: string }) {
  return (
    <p className="m-0 text-sm text-pretty text-dim">
      {text.split('`').map((part, index) =>
        index % 2 === 1 ? (
          <code key={index} className="rounded-sm bg-surface2 px-1 font-mono text-[13px] text-fg">
            {part}
          </code>
        ) : (
          part
        ),
      )}
    </p>
  );
}

/**
 * Check results as rows: title, status dot with its text, a plain line, and the server's raw text
 * behind "Details" (the StepList pattern with ok/warn/fail tones, critique-v2 #11).
 */
export function CheckList({ label, rows }: CheckListProps) {
  return (
    <ul aria-label={label} className="m-0 flex list-none flex-col overflow-hidden rounded-[18px] border border-border bg-surface p-0">
      {rows.map((row) => {
        const state = STATES[row.state];
        const quiet = row.state === 'checking' || row.state === 'skipped';
        return (
          <li key={row.id} className="flex flex-col gap-1 border-t border-border px-[18px] py-3.5 first:border-t-0">
            <div className="flex items-center justify-between gap-3">
              <span className={cn('font-medium', quiet && 'text-dim')}>{row.title}</span>
              <StatusDot tone={state.tone} label={state.label} className="flex-none text-[13px]" />
            </div>
            {row.line && <Line text={row.line} />}
            {row.details && (
              <details className="text-sm">
                <summary className="inline-flex min-h-11 cursor-pointer items-center font-medium text-accent-text">Details</summary>
                <p className="m-0 font-mono text-[12.5px] [overflow-wrap:anywhere] text-dim">{row.details}</p>
              </details>
            )}
          </li>
        );
      })}
    </ul>
  );
}
