import type { ReactNode } from 'react';
import type { UseQueryResult } from '@tanstack/react-query';
import { Button } from '@/components/atoms/Button';
import { Notice } from '@/components/atoms/Notice';
import { errorMessage } from '@/lib/errors';

export interface QueryBoundaryProps<T> {
  query: UseQueryResult<T>;
  /** What is loading, for the status text, e.g. "homes". */
  what: string;
  children: (data: T) => ReactNode;
}

/** Loading and error states for one query; renders `children` with the data once it arrives. */
export function QueryBoundary<T>({ query, what, children }: QueryBoundaryProps<T>) {
  if (query.data !== undefined) return <>{children(query.data)}</>;
  if (query.isError) {
    return (
      <Notice tone="bad" role="alert" className="flex flex-wrap items-center justify-between gap-3">
        <span>
          Couldn’t load {what}. {errorMessage(query.error)}
        </span>
        <Button onClick={() => void query.refetch()}>Try again</Button>
      </Notice>
    );
  }
  return (
    <p role="status" className="m-0 py-10 text-center text-dim">
      Loading {what}…
    </p>
  );
}
