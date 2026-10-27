import type { ExampleSet } from '@/types/examples';
import { QrCode } from './QrCode';

const examples: ExampleSet = {
  title: 'QrCode',
  examples: [
    {
      name: 'Wi-Fi network',
      render: () => <QrCode value="WIFI:T:WPA;S:iFLO device;P:13106423;;" label="QR code to join Wi-Fi network iFLO device" />,
    },
    { name: 'small', render: () => <QrCode value="https://example.com" label="QR code for example.com" size={120} /> },
  ],
};

export default examples;
