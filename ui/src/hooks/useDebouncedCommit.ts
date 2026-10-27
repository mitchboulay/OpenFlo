import { useEffect, useRef, useState } from 'react';

/**
 * A local draft for rapid edits (stepper taps) that commits once input pauses for `delayMs`.
 * `commit` receives the draft and a `done` callback; call it when the server state has caught up
 * so the draft clears without flashing the old value.
 */
export function useDebouncedCommit<T>(commit: (value: T, done: () => void) => void, delayMs = 600) {
  const [draft, setDraft] = useState<T | null>(null);
  const commitRef = useRef(commit);
  commitRef.current = commit;

  useEffect(() => {
    if (draft === null) return undefined;
    const timer = window.setTimeout(() => commitRef.current(draft, () => setDraft(null)), delayMs);
    return () => window.clearTimeout(timer);
  }, [draft, delayMs]);

  return [draft, setDraft] as const;
}
