import type { ReactNode } from 'react';

/** Default export of every `*.examples.tsx`, rendered by the dev-only /__components route. */
export interface ExampleSet {
  title: string;
  examples: ReadonlyArray<{ name: string; render: () => ReactNode }>;
}
