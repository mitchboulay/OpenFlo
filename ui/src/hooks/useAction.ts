import { useCallback, useRef, useState } from 'react';

export type ActionResult<R> = { ok: true; value: R } | { ok: false; error: unknown };

/**
 * A one-off request with pending/error state and nothing retained after it settles. Use it instead
 * of `useMutation` when the request or response carries a secret (a password, a new API token):
 * TanStack's mutation cache keeps both `variables` and `data` after the component unmounts.
 */
export function useAction<A extends unknown[], R>(request: (...args: A) => Promise<R>) {
  const requestRef = useRef(request);
  requestRef.current = request;
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const run = useCallback(async (...args: A): Promise<ActionResult<R>> => {
    setPending(true);
    setError(null);
    try {
      return { ok: true, value: await requestRef.current(...args) };
    } catch (caught) {
      setError(caught);
      return { ok: false, error: caught };
    } finally {
      setPending(false);
    }
  }, []);

  const reset = useCallback(() => setError(null), []);
  return { run, pending, error, reset };
}
