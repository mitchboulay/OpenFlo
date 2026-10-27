import { useState } from 'react';
import type { ExampleSet } from '@/types/examples';
import { Tabs, tabPanelProps } from './Tabs';

const TABS = [
  { value: 'dispenses', label: 'Dispenses' },
  { value: 'events', label: 'Events' },
  { value: 'syncs', label: 'Check-ins' },
] as const;

type TabValue = (typeof TABS)[number]['value'];

function HistoryTabs() {
  const [tab, setTab] = useState<TabValue>('dispenses');
  return (
    <div className="flex flex-col gap-2">
      <Tabs label="History" tabs={TABS} selected={tab} onSelect={setTab} idPrefix="tabs-example" />
      <p {...tabPanelProps('tabs-example', tab)} className="m-0 text-dim">
        Showing {tab}
      </p>
    </div>
  );
}

const examples: ExampleSet = { title: 'Tabs', examples: [{ name: 'history', render: () => <HistoryTabs /> }] };

export default examples;
