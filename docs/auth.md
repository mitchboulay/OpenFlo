# Sign-in

OpenFLO has one operator. Choose how that person signs in with `OPENFLO_AUTH_MODE` in `.env`: `basic` (the default), `oidc`, `proxy` or `none`. After any change, run `docker compose up -d` to apply it.

In every mode:

- **API tokens** also work (see [API tokens](#api-tokens)).
- **Browser sessions** are a signed cookie, keyed by `/data/secret.key`. The key is created on first start. Deleting it signs everyone out. Sessions expire after 12 hours idle.
- **Changes from a browser** must come from the OpenFLO page itself. Cross-site requests are refused.
- **The device API stays open.** The firmware can't sign in, so `/device-api/*` never needs a login. See [security-model.md](security-model.md).

OpenFLO refuses to start when:

- `OPENFLO_AUTH_MODE=none` and `OPENFLO_PUBLIC=true`;
- `OPENFLO_AUTH_MODE=proxy` and `OPENFLO_TRUSTED_PROXY_CIDR` is empty or invalid;
- `OPENFLO_AUTH_MODE=oidc` and `OPENFLO_OIDC_ISSUER` or `OPENFLO_OIDC_CLIENT_ID` is missing.

`docker compose logs openflo` shows the reason.

## Basic (default)

One admin account with a password.

**From the setup wizard.** Leave `OPENFLO_ADMIN_USER` and `OPENFLO_ADMIN_PASSWORD_HASH` empty. The first step of the wizard creates the admin and signs you in.

**From `.env`.** Set the user name and an argon2 hash of the password. The `.env` account takes precedence over one created in setup.

1. Generate the hash. The command asks for the password without echoing it. It uses the `backup` service, which works whether or not OpenFLO is running:

   ```bash
   docker compose run --rm backup python -c "import getpass, argon2; print(argon2.PasswordHasher().hash(getpass.getpass()))"
   ```

2. Put it in `.env` in single quotes, because the hash contains `$`:

   ```bash
   OPENFLO_ADMIN_USER=admin
   OPENFLO_ADMIN_PASSWORD_HASH='$argon2id$v=19$m=65536,t=3,p=4$...'
   ```

3. Run `docker compose up -d`.

Sign-in allows 5 attempts per minute from each IP address.

## OIDC (Authentik and others)

OpenFLO uses the Authorization Code flow with PKCE. It works with any OpenID Connect provider. These steps use Authentik.

### 1. Create the provider in Authentik

1. In the Authentik admin, go to **Applications → Providers → Create**. Choose **OAuth2/OpenID Provider**.
2. **Client type:** Confidential. (Public also works; then leave the client secret empty in OpenFLO.)
3. **Redirect URI:** strict, set to:

   ```
   https://openflo.example.com/api/v1/auth/oidc/callback
   ```

   The host must match the server address saved in OpenFLO setup.
4. **Scopes:** keep the defaults `openid`, `email` and `profile`. OpenFLO asks for exactly these three. Authentik's default `profile` scope includes a `groups` claim.
5. **Signing key:** choose a key, so ID tokens are signed.
6. Save. Note the **Client ID** and **Client Secret**.

### 2. Create the application

1. Go to **Applications → Applications → Create**.
2. Give it a name and a slug, for example `openflo`, and select the provider from step 1.
3. Optional: bind a group (for example `openflo-admins`) in the application's policy bindings.

### 3. Configure OpenFLO

```bash
OPENFLO_AUTH_MODE=oidc
OPENFLO_OIDC_ISSUER=https://auth.example.com/application/o/openflo/
OPENFLO_OIDC_CLIENT_ID=<client id>
OPENFLO_OIDC_CLIENT_SECRET=<client secret>
OPENFLO_OIDC_ALLOWED_GROUPS=openflo-admins
```

- The issuer is Authentik's **OpenID Configuration Issuer** for the application. OpenFLO loads `<issuer>/.well-known/openid-configuration` from it.
- `OPENFLO_OIDC_ALLOWED_GROUPS` is a comma-separated list. A user needs at least one listed group in the `groups` claim. Leave it empty to admit anyone the provider signs in.
- The OpenFLO server must be able to reach the issuer URL.

Run `docker compose up -d`. In the setup wizard, the first step confirms that OpenFLO can reach your provider. Sign-in then sends you to Authentik and back.

If sign-in fails, you return to the sign-in page with a reason:

- **Not in an allowed group:** add the user to a group in `OPENFLO_OIDC_ALLOWED_GROUPS`.
- **Provider not responding:** OpenFLO couldn't reach the issuer. API tokens and existing sessions keep working.
- **Sign-in failed:** usually a redirect URI or client secret mismatch.

### Apps and scripts

A client that runs its own PKCE flow against your provider can trade its `id_token` for an OpenFLO API token at `POST /api/v1/auth/oidc/exchange`. The token lasts 90 days.

## Auth proxy

Use this when an auth proxy (an Authentik outpost, Authelia, oauth2-proxy) already signs users in. The proxy passes the user in headers, and OpenFLO trusts them only from the proxy's address.

OpenFLO reads these headers:

| | Generic (Authelia, oauth2-proxy) | Authentik |
|---|---|---|
| User | `Remote-User` | `X-authentik-username` |
| Email (used if there's no user) | `Remote-Email` | `X-authentik-email` |
| Groups | `Remote-Groups` (comma-separated) | `X-authentik-groups` (`\|`-separated) |

### The layout

Devices must still reach OpenFLO's Caddy directly, because they can't pass through a sign-in page or another TLS proxy. So the auth proxy handles **browsers only**:

- **Devices** use `openflo.example.com`, which points straight at OpenFLO's Caddy (port 443). This is the server address in Settings.
- **Browsers** use a second name, for example `openflo-login.example.com`, served by your auth proxy. After sign-in, the proxy forwards the request to `https://openflo.example.com` with the user headers.

A browser that skips the proxy and opens `openflo.example.com` directly gets no user headers, so it can't sign in.

### Configure OpenFLO

```bash
OPENFLO_AUTH_MODE=proxy
OPENFLO_TRUSTED_PROXY_CIDR=192.168.1.20/32
OPENFLO_OIDC_ALLOWED_GROUPS=openflo-admins
```

- `OPENFLO_TRUSTED_PROXY_CIDR` is the address of your auth proxy, as OpenFLO's Caddy sees it connect. Use a single address (`/32`) if you can. Several CIDRs can be comma-separated. Headers from any other address are ignored.
- Never trust a Docker gateway address such as `172.30.0.1`. Some Docker setups (Docker Desktop, or a host running Docker's userland proxy) make every connection appear to come from it, which would let anyone send user headers. Run the auth proxy on a different machine or a fixed LAN address.
- `OPENFLO_OIDC_ALLOWED_GROUPS` works the same way as in OIDC mode, using the groups header.

Make sure your proxy removes any user headers the browser sends, and sets its own.

**Authentik:** create a **Proxy Provider** in "Proxy" mode with the external host `https://openflo-login.example.com` and the internal host `https://openflo.example.com`. Run it on an outpost at `192.168.1.20`.

**Authelia:** put it in front of `openflo-login.example.com` with your reverse proxy's forward-auth integration, and forward to `https://openflo.example.com`. Authelia sets `Remote-User`, `Remote-Email` and `Remote-Groups`.

## API tokens

Tokens are for scripts and other apps. A token can do anything you can.

- **Create:** go to **Settings → API tokens → New token…**. The token is shown once. Copy it then.
- **Use:** send it as `Authorization: Bearer <token>`:

  ```bash
  curl -fsS -H "Authorization: Bearer $TOKEN" https://openflo.example.com/api/v1/homes
  ```

- **Revoke:** select **Revoke** next to the token in Settings, then confirm. It stops working at once.
- **Bootstrap token:** set `OPENFLO_API_TOKEN` in `.env` for automation before anyone signs in. Changing or clearing it revokes the old value.

OpenFLO stores only a SHA-256 hash of each token. The API description is at `/api/v1/openapi.json`.

## No login (`none`)

```bash
OPENFLO_AUTH_MODE=none
OPENFLO_PUBLIC=false
```

**Warning:** anyone who can reach the page controls your devices, including dispensing. Every page shows a "No login" banner. Use this only on a private network you trust, never on a server reachable from the internet. OpenFLO refuses to start in this mode while `OPENFLO_PUBLIC=true`.
