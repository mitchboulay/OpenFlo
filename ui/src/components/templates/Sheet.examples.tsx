import { useState } from 'react';
import { Button } from '@/components/atoms/Button';
import type { ExampleSet } from '@/types/examples';
import { Sheet } from './Sheet';

function SheetDemo() {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  return (
    <>
      <Button onClick={() => setOpen(true)}>Open sheet</Button>
      <Sheet
        open={open}
        onClose={close}
        title="New bottle"
        footer={
          <>
            <Button variant="ghost" onClick={close}>
              Cancel
            </Button>
            <Button variant="primary" onClick={close}>
              Save
            </Button>
          </>
        }
      >
        <p className="m-0 text-dim">A bottom sheet on phones and a centered dialog from 640 px up.</p>
      </Sheet>
    </>
  );
}

const examples: ExampleSet = {
  title: 'Sheet',
  examples: [{ name: 'With footer actions', render: () => <SheetDemo /> }],
};

export default examples;
