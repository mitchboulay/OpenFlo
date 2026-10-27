import type { ExampleSet } from '@/types/examples';
import { CheckinOption } from './CheckinOption';

const noop = () => undefined;

const examples: ExampleSet = {
  title: 'CheckinOption',
  examples: [
    {
      name: 'group',
      render: () => (
        <div role="radiogroup" aria-label="Check-in" className="flex flex-col gap-2">
          <CheckinOption
            name="Battery saver"
            line="Checks in daily. Changes can take up to a day."
            cost={1}
            costLabel="Lowest battery use"
            selected={false}
            onSelect={noop}
          />
          <CheckinOption name="Balanced" line="Checks in every 6 hours." cost={2} costLabel="Low battery use" recommended selected onSelect={noop} />
          <CheckinOption
            name="Testing"
            line="Every 15 minutes. Drains the battery. Use briefly."
            cost={4}
            costLabel="Very high battery use"
            selected={false}
            onSelect={noop}
          />
        </div>
      ),
    },
  ],
};

export default examples;
