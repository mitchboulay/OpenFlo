import type { ExampleSet } from '@/types/examples';
import { Icon, ICON_NAMES } from './Icon';

const examples: ExampleSet = {
  title: 'Icon',
  examples: [
    {
      name: 'all',
      render: () => (
        <div className="flex flex-wrap gap-4 text-dim">
          {ICON_NAMES.map((name) => (
            <span key={name} className="flex flex-col items-center gap-1 text-xs">
              <Icon name={name} />
              {name}
            </span>
          ))}
        </div>
      ),
    },
  ],
};

export default examples;
