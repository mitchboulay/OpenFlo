import { describe, expect, it } from 'vitest';

// Raw sources of all UI code. Colors live only in styles/tokens.css.
const sources = import.meta.glob<string>(['../**/*.{ts,tsx}', '!../**/*.test.{ts,tsx}', '!../api/schema.d.ts'], {
  query: '?raw',
  import: 'default',
  eager: true,
});

const RAW_COLOR = /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/;

describe('design rules', () => {
  it('scans the UI sources', () => {
    expect(Object.keys(sources).length).toBeGreaterThan(10);
  });

  it.each(Object.entries(sources))('%s uses token colors only', (_path, source) => {
    expect(source).not.toMatch(RAW_COLOR);
  });

  it('keeps every atom and molecule paired with an examples file', () => {
    const files = Object.keys(sources);
    const components = files.filter(
      (file) => /\/components\/(atoms|molecules)\/[A-Z]\w+\.tsx$/.test(file) && !file.endsWith('.examples.tsx'),
    );
    expect(components.length).toBeGreaterThan(0);
    for (const component of components) {
      expect(files).toContain(component.replace(/\.tsx$/, '.examples.tsx'));
    }
  });
});
