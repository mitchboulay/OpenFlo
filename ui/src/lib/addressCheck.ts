import type { AddressCheckResult, CheckName, CheckStatus } from '@/api/types';

/** A row's display state: an API status, or the client-side "running" and "not checked". */
export type CheckRowState = CheckStatus | 'checking' | 'skipped';

export interface CheckRowModel {
  id: CheckName;
  title: string;
  state: CheckRowState;
  /** The plain result or fix. `backticks` mark config words to set in mono. */
  line: string | null;
  /** The server's raw text, behind "Details" on non-ok rows. */
  details: string | null;
}

export type CheckVerdict = 'ok' | 'warn' | 'fail';

const TITLES: Record<CheckName, string> = {
  dns: 'Found your server',
  tls_no_sni: 'Devices can connect securely',
  chain_firmware_bundle: 'Certificate is one iFLO trusts',
  leaf_rsa: 'Certificate type works',
  healthcheck_reachable: 'This server answered',
  port_non_443: 'Port',
};

/** The fixed display order (v3 §12 step 3), whatever order the API sends. */
export const CHECK_ORDER = Object.keys(TITLES) as CheckName[];

const CLOUDFLARE_LINE =
  'This name goes through Cloudflare. Devices can’t connect through it. Set it to DNS only (grey cloud).';

function lineFor(check: CheckName, status: CheckStatus, host: string, port: number): string {
  switch (check) {
    case 'dns':
      if (status === 'ok') return `${host} points to this server.`;
      // The API only warns on DNS for an address that resolves into Cloudflare's ranges.
      return status === 'warn' ? CLOUDFLARE_LINE : `Create a DNS record for ${host} that points to this server.`;
    case 'tls_no_sni':
      return status === 'ok'
        ? 'Works the way iFLO connects.'
        : 'iFLO connects without saying which site it wants. Your server must still answer with the OpenFLO certificate. In Caddy, set `default_sni` to this name.';
    case 'chain_firmware_bundle':
      return status === 'ok'
        ? 'Signed by an authority iFLO trusts.'
        : 'iFLO doesn’t trust this certificate. Use a Let’s Encrypt certificate.';
    case 'leaf_rsa':
      return status === 'ok'
        ? 'Works with iFLO.'
        : 'iFLO needs an RSA certificate (2048-bit or larger). In Caddy, set `key_type rsa2048`.';
    case 'healthcheck_reachable':
      if (status === 'ok') return 'Reached this OpenFLO.';
      return status === 'warn' ? CLOUDFLARE_LINE : 'Something else answered at this address. Check that it points to this server.';
    case 'port_non_443':
      return `Port ${port} hasn’t been tested with iFLO yet. Port 443 is known to work.`;
  }
}

/** Host and port of `scheme://host[:port]`; null when it doesn't parse. */
export function addressParts(address: string): { host: string; port: number } | null {
  try {
    const url = new URL(address);
    return { host: url.hostname, port: Number(url.port) || (url.protocol === 'http:' ? 80 : 443) };
  } catch {
    return null;
  }
}

/**
 * Rows with no result: `checking` while the request is in flight, `skipped` after it failed.
 * The port row appears only for a non-443 address.
 */
export function pendingRows(address: string, state: 'checking' | 'skipped'): CheckRowModel[] {
  const port = addressParts(address)?.port ?? 443;
  return CHECK_ORDER.filter((check) => check !== 'port_non_443' || port !== 443).map((check) => ({
    id: check,
    title: TITLES[check],
    state,
    line: null,
    details: null,
  }));
}

/**
 * The CheckList rows for a result, in the fixed order with plain titles and lines (v3 §12 step 3).
 * The port row is hidden when ok; when DNS warns about Cloudflare the healthcheck row is "Not checked",
 * so the Cloudflare problem is shown once.
 */
export function checkRows(result: AddressCheckResult): CheckRowModel[] {
  const { host, port } = addressParts(result.address) ?? { host: result.address, port: 443 };
  const byName = new Map(result.checks.map((item) => [item.check, item]));
  const cloudflare = byName.get('dns')?.status === 'warn';
  return CHECK_ORDER.flatMap((check): CheckRowModel[] => {
    const item = byName.get(check);
    if (!item || (check === 'port_non_443' && item.status === 'ok')) return [];
    if (check === 'healthcheck_reachable' && cloudflare) {
      return [{ id: check, title: TITLES[check], state: 'skipped', line: null, details: null }];
    }
    return [
      {
        id: check,
        title: TITLES[check],
        state: item.status,
        line: lineFor(check, item.status, host, port),
        details: item.status === 'ok' ? null : item.detail,
      },
    ];
  });
}

/** Any fail → fail; else any warn → warn; else ok. Matches the API's own `address_check` step. */
export function checkVerdict(result: AddressCheckResult): CheckVerdict {
  const statuses = new Set(result.checks.map((item) => item.status));
  return statuses.has('fail') ? 'fail' : statuses.has('warn') ? 'warn' : 'ok';
}

export const VERDICT_TITLES: Record<CheckVerdict, string> = {
  ok: 'Everything checks out',
  warn: 'Almost there',
  fail: 'Devices can’t reach OpenFLO yet',
};

/** The Settings summary after "Checked …": "Everything checks out", "1 warning", "Devices can't connect". */
export function checkSummary(result: AddressCheckResult): string {
  const verdict = checkVerdict(result);
  if (verdict === 'ok') return 'Everything checks out';
  if (verdict === 'fail') return 'Devices can’t connect';
  const warnings = result.checks.filter((item) => item.status === 'warn').length;
  return `${warnings} warning${warnings === 1 ? '' : 's'}`;
}

export const SERVER_ADDRESS_COPY = {
  label: 'Server address',
  placeholder: 'https://openflo.example.com',
  hint: 'Devices only connect over https://. Port 443 works best.',
} as const;

/** Client-side check before saving: `https://` and a host (v3 §12 step 2). Null when valid. */
export function validateServerAddress(raw: string): string | null {
  const value = raw.trim();
  if (/^http:\/\//i.test(value)) return 'Devices only connect over https://.';
  if (!/^https:\/\//i.test(value)) return 'Enter the full address, starting with https://';
  try {
    return new URL(value).hostname ? null : 'Enter the full address, starting with https://';
  } catch {
    return 'Enter the full address, starting with https://';
  }
}

/** "auth.example.com" from an OIDC issuer URL; the raw value if it isn't a URL. */
export function issuerHost(issuer: string | null | undefined): string {
  if (!issuer) return 'your identity provider';
  try {
    return new URL(issuer).host;
  } catch {
    return issuer;
  }
}
