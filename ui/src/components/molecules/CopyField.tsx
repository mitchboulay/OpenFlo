import { useEffect, useState } from 'react';
import { Button } from '@/components/atoms/Button';

export interface CopyFieldProps {
  /** The text to show and copy, e.g. a new API token. */
  value: string;
  /** Accessible name of the value, e.g. "New token". */
  label: string;
}

/** How long the button reads "Copied". */
export const COPIED_MS = 2000;

type CopyState = 'idle' | 'copied' | 'failed';

/** A value in mono in a bordered box, a Copy button that confirms with "Copied", and a live region. */
export function CopyField({ value, label }: CopyFieldProps) {
  const [state, setState] = useState<CopyState>('idle');

  useEffect(() => {
    if (state !== 'copied') return undefined;
    const timer = window.setTimeout(() => setState('idle'), COPIED_MS);
    return () => window.clearTimeout(timer);
  }, [state]);

  const copy = () =>
    navigator.clipboard.writeText(value).then(
      () => setState('copied'),
      () => setState('failed'),
    );

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-2 rounded-control border border-border2 bg-surface2 py-1 pr-1 pl-3.5">
        <code aria-label={label} className="min-w-0 flex-1 font-mono text-[13px] [overflow-wrap:anywhere] select-all">
          {value}
        </code>
        <Button onClick={() => void copy()}>{state === 'copied' ? 'Copied' : 'Copy'}</Button>
      </div>
      <p role="status" className="m-0 min-h-5 text-sm text-dim">
        {state === 'copied' ? 'Copied to the clipboard.' : state === 'failed' ? 'Couldn’t copy. Select the text and copy it instead.' : ''}
      </p>
    </div>
  );
}
