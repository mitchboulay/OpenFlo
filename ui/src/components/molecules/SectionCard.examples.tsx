import type { ExampleSet } from '@/types/examples';
import { SectionCard } from './SectionCard';

const examples: ExampleSet = {
  title: 'SectionCard',
  examples: [
    {
      name: 'plain',
      render: () => (
        <SectionCard title="Schedule" icon="calendar">
          <p className="m-0 text-dim">Nothing coming up.</p>
        </SectionCard>
      ),
    },
    {
      name: 'collapsible below lg, with aside',
      render: () => (
        <SectionCard title="Battery" icon="battery" collapsible aside={<span className="text-2xl font-semibold text-ok">82%</span>}>
          <p className="m-0">≈ 120 days until the batteries need replacing.</p>
        </SectionCard>
      ),
    },
  ],
};

export default examples;
