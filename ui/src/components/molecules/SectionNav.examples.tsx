import type { ExampleSet } from '@/types/examples';
import { SectionNav } from './SectionNav';

const SECTIONS = [
  { id: 'dosing', label: 'Dosing' },
  { id: 'schedule', label: 'Schedule' },
  { id: 'device', label: 'Device' },
];

const examples: ExampleSet = {
  title: 'SectionNav',
  examples: [{ name: 'device', render: () => <SectionNav label="Device sections" sections={SECTIONS} /> }],
};

export default examples;
