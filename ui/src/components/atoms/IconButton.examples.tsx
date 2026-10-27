import type { ExampleSet } from '@/types/examples';
import { Icon } from './Icon';
import { IconButton } from './IconButton';

const examples: ExampleSet = {
  title: 'IconButton',
  examples: [
    {
      name: 'edit',
      render: () => (
        <IconButton label="Edit home">
          <Icon name="edit" size={16} />
        </IconButton>
      ),
    },
    {
      name: 'disabled',
      render: () => (
        <IconButton label="Close" disabled>
          <Icon name="close" />
        </IconButton>
      ),
    },
  ],
};

export default examples;
