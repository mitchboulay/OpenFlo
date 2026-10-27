import { AppShell } from '@/components/templates/AppShell';
import type { ExampleSet } from '@/types/examples';

// Dev only: App.tsx imports this lazily behind import.meta.env.DEV, so
// production builds contain neither the gallery nor any examples file.
const modules = import.meta.glob<ExampleSet>('../components/**/*.examples.tsx', {
  import: 'default',
  eager: true,
});

const exampleSets = Object.entries(modules)
  .sort(([a], [b]) => a.localeCompare(b))
  .map(([path, set]) => ({ path, set }));

export default function ComponentGallery() {
  return (
    <AppShell back={{ to: '/', label: 'App' }} contentWidth="wide">
      <h1 className="m-0 text-2xl font-bold tracking-tight">Components</h1>
      {exampleSets.map(({ path, set }) => (
        <section
          key={path}
          aria-labelledby={path}
          className="flex flex-col gap-4 rounded-card border border-card-border bg-surface p-5 shadow-card"
        >
          <h2 id={path} className="m-0 text-lg font-semibold">
            {set.title} <span className="text-sm font-normal text-faint">{path.replace('../components/', '')}</span>
          </h2>
          <div className="flex flex-col gap-4">
            {set.examples.map((example) => (
              <div key={example.name} className="flex flex-col gap-1.5">
                <span className="text-sm text-dim">{example.name}</span>
                <div>{example.render()}</div>
              </div>
            ))}
          </div>
        </section>
      ))}
    </AppShell>
  );
}
