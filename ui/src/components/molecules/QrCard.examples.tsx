import { Button } from '@/components/atoms/Button';
import type { ExampleSet } from '@/types/examples';
import { QrCard } from './QrCard';

const examples: ExampleSet = {
  title: 'QrCard',
  examples: [
    {
      name: 'hotspot',
      render: () => (
        <QrCard
          value="WIFI:T:WPA;S:iFLO device;P:13106423;;"
          label="QR code to join Wi-Fi network iFLO device"
          caption="Network"
          displayValue="iFLO device"
        />
      ),
    },
    {
      name: 'with an action',
      render: () => (
        <QrCard
          value="http://192.168.4.1/index.html?ott=example&apiUrl=https://openflo.example.com&deviceType=0"
          label="QR code to open the setup page"
          caption="Setup page"
          displayValue="http://192.168.4.1"
          action={<Button variant="ghost">Copy link</Button>}
        />
      ),
    },
  ],
};

export default examples;
