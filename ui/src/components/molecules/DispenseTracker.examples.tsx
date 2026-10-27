import { Button } from '@/components/atoms/Button';
import type { ExampleSet } from '@/types/examples';
import { DispenseTracker } from './DispenseTracker';

const examples: ExampleSet = {
  title: 'DispenseTracker',
  examples: [
    {
      name: 'queued',
      render: () => (
        <DispenseTracker
          stage="queued"
          title="Queued for next check-in"
          note="Waiting for device · ~4:42 PM EDT. To dispense sooner, twist the bottle or press the device’s button."
          action={
            <Button variant="ghost" className="text-bad">
              Cancel request
            </Button>
          }
        />
      ),
    },
    { name: 'sent', render: () => <DispenseTracker stage="sent" title="Sent to device" note="Your iFLO has the request." /> },
    {
      name: 'dispensed',
      render: () => (
        <DispenseTracker
          stage="dispensed"
          title="Dispensed 177 mL"
          note="Confirmed by the device · 4:43 PM"
          action={<Button variant="ghost">Done</Button>}
        />
      ),
    },
  ],
};

export default examples;
