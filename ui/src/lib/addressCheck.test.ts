import { describe, expect, it } from 'vitest';
import { makeCheckResult } from '@/test/fixtures';
import { checkRows, checkSummary, checkVerdict, issuerHost, pendingRows, validateServerAddress } from './addressCheck';

describe('checkRows', () => {
  it('renders the fixed order with plain lines, hiding an ok port and raw details', () => {
    const result = makeCheckResult();
    result.checks.reverse(); // the API order must not matter
    const rows = checkRows(result);
    expect(rows.map((row) => row.id)).toEqual(['dns', 'tls_no_sni', 'chain_firmware_bundle', 'leaf_rsa', 'healthcheck_reachable']);
    expect(rows[0]).toMatchObject({ title: 'Found your server', state: 'ok', line: 'openflo.example.com points to this server.', details: null });
  });

  it('maps failures to fixes and keeps the raw detail for the disclosure', () => {
    const rows = checkRows(makeCheckResult({ leaf_rsa: 'fail', dns: 'fail' }));
    expect(rows.find((row) => row.id === 'leaf_rsa')).toMatchObject({
      state: 'fail',
      line: 'iFLO needs an RSA certificate (2048-bit or larger). In Caddy, set `key_type rsa2048`.',
      details: 'leaf_rsa: raw failure detail',
    });
    expect(rows[0]?.line).toBe('Create a DNS record for openflo.example.com that points to this server.');
  });

  it('shows Cloudflare once: on DNS, with the healthcheck row not checked', () => {
    const rows = checkRows(makeCheckResult({ dns: 'warn', healthcheck_reachable: 'warn' }));
    expect(rows[0]?.line).toMatch(/goes through Cloudflare/);
    expect(rows.find((row) => row.id === 'healthcheck_reachable')).toMatchObject({ state: 'skipped', line: null });
  });

  it('shows the port row only when it warns', () => {
    const rows = checkRows(makeCheckResult({ port_non_443: 'warn' }, 'https://openflo.example.com:8443'));
    expect(rows.at(-1)).toMatchObject({ title: 'Port', line: 'Port 8443 hasn’t been tested with iFLO yet. Port 443 is known to work.' });
  });

  it('lists pending rows, with the port only for a non-443 address', () => {
    expect(pendingRows('https://a.example.com', 'checking')).toHaveLength(5);
    expect(pendingRows('https://a.example.com:8443', 'skipped').map((row) => row.state)).toEqual(Array(6).fill('skipped'));
  });
});

describe('verdict and summary', () => {
  it.each([
    [{}, 'ok', 'Everything checks out'],
    [{ port_non_443: 'warn' as const, dns: 'warn' as const }, 'warn', '2 warnings'],
    [{ dns: 'warn' as const, leaf_rsa: 'fail' as const }, 'fail', 'Devices can’t connect'],
  ])('%o → %s', (statuses, verdict, summary) => {
    expect(checkVerdict(makeCheckResult(statuses))).toBe(verdict);
    expect(checkSummary(makeCheckResult(statuses))).toBe(summary);
  });
});

describe('validateServerAddress', () => {
  it.each([
    ['https://openflo.example.com', null],
    [' https://openflo.example.com:8443 ', null],
    ['http://openflo.example.com', 'Devices only connect over https://.'],
    ['openflo.example.com', 'Enter the full address, starting with https://'],
    ['https://', 'Enter the full address, starting with https://'],
  ])('%s', (input, error) => expect(validateServerAddress(input)).toBe(error));
});

describe('issuerHost', () => {
  it('shows only the host', () => {
    expect(issuerHost('https://auth.example.com/application/o/openflo/')).toBe('auth.example.com');
    expect(issuerHost(null)).toBe('your identity provider');
  });
});
