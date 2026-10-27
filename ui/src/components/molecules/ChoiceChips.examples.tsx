import type { ExampleSet } from '@/types/examples';
import { ChoiceChips } from './ChoiceChips';

const noop = () => undefined;

const examples: ExampleSet = {
  title: 'ChoiceChips',
  examples: [
    {
      name: 'dose presets',
      render: () => (
        <ChoiceChips
          label="Dose presets"
          selected="standard"
          onSelect={noop}
          options={[
            { value: 'light', label: 'Light', detail: '118 mL' },
            { value: 'standard', label: 'Standard', detail: '177 mL' },
            { value: 'strong', label: 'Strong', detail: '236 mL' },
          ]}
        />
      ),
    },
    {
      name: 'liquids with a trailing action',
      render: () => (
        <ChoiceChips
          label="Liquid"
          selected={1}
          onSelect={noop}
          options={[
            { value: 1, label: 'Standard' },
            { value: 2, label: 'Vinegar', detail: 'Not calibrated yet', detailTone: 'warn' },
          ]}
          trailing={
            <button type="button" className="min-h-11 rounded-control border border-dashed border-border2 px-3.5 text-sm text-dim">
              New liquid…
            </button>
          }
        />
      ),
    },
  ],
};

export default examples;
