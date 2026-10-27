import { checkRows, pendingRows } from '@/lib/addressCheck';
import { makeCheckResult } from '@/test/fixtures';
import type { ExampleSet } from '@/types/examples';
import { CheckList } from './CheckList';

const examples: ExampleSet = {
  title: 'CheckList',
  examples: [
    { name: 'checking', render: () => <CheckList label="Address check" rows={pendingRows('https://openflo.example.com', 'checking')} /> },
    { name: 'all ok', render: () => <CheckList label="Address check" rows={checkRows(makeCheckResult())} /> },
    {
      name: 'Cloudflare and a port warning',
      render: () => (
        <CheckList
          label="Address check"
          rows={checkRows(makeCheckResult({ dns: 'warn', healthcheck_reachable: 'warn', port_non_443: 'warn' }, 'https://openflo.example.com:8443'))}
        />
      ),
    },
    {
      name: 'failures',
      render: () => <CheckList label="Address check" rows={checkRows(makeCheckResult({ tls_no_sni: 'fail', leaf_rsa: 'fail' }))} />,
    },
  ],
};

export default examples;
