import type { ExampleSet } from '@/types/examples';
import { Menu } from './Menu';

const noop = () => undefined;

const examples: ExampleSet = {
  title: 'Menu',
  examples: [
    {
      name: 'device actions',
      render: () => (
        <div className="flex justify-end">
          <Menu
            label="Device actions"
            items={[
              { label: 'Edit name and location', onSelect: noop },
              { label: 'Pause dispensing', onSelect: noop },
              { label: 'Retire device…', tone: 'danger', onSelect: noop },
            ]}
          />
        </div>
      ),
    },
  ],
};

export default examples;
