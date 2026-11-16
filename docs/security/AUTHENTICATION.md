# Personal mode and optional Okta login

**Status (2026-11-14): optional OIDC redirect, token validation and per-browser console sessions are implemented and tested with a simulated provider and signed synthetic tokens. A real tenant/application and explicit member configuration are prepared, but real login is not verified; user enrollment encountered a missing-passkey prompt.** The running pilot remains in personal mode. Both modes bind only to `127.0.0.1`; remote deployment and organization-authenticated browser terminal access remain open; the local personal-mode terminal is implemented.

## Current decision: defer authentication (2026-11-14)

At the user's request, further Okta enrollment/login troubleshooting is deferred. The running console has returned to trusted personal mode on loopback port 4180. The OIDC implementation and external temporary public configuration are retained; no client secret was copied into repository files or logs. Real SSO acceptance remains open, and this deferral does not authorize remote or mutually untrusted multi-user exposure. Next work follows the [active delivery priorities](../platform/PLATFORM_ROADMAP.md#active-delivery-priorities-2026-11-14).

## Modes

| Mode | Behavior | Identity source |
|---|---|---|
| `personal` (default) | Existing local bootstrap, fixed principal/role and embedded browser terminal with Mac Terminal fallback | Trusted local OS operator; no Okta requirement |
| `okta` (optional) | Okta-hosted authorization-code login with S256 PKCE; verified identity mapped to a private server session | Exact configured issuer and assigned OIDC subject |

There is no browser switch that bypasses SSO. Okta bootstrap requires an authenticated browser session and never issues the personal operator cookie. Missing dependencies, secret or valid discovery settings prevent startup before worker connection or listening socket creation. A configured tenant with one assigned subject could serve personal Okta use; multiple assigned subjects use the same implementation. Neither has been tested against a real tenant.

Codex device login is separate from platform login and remains private inside a sandbox. Existing local-pilot workspace ownership is preserved; it is not silently transferred to an Okta identity.

## Personal use now

```bash
python3 scripts/serve_session_console.py --auth-mode personal --check-auth-config
python3 scripts/serve_session_console.py --auth-mode personal --port 4180
```

Personal mode requires only Python's standard library plus the existing Lima worker. An explicit `--principal member-a` defaults to member; trusted `--role operator` can elevate the local binding. These flags are rejected in Okta mode. Personal mode authenticates no distinct people and trusts all local processes capable of reaching bootstrap.

## Prepare Okta settings

[Example public configuration](../../config/okta.example.json) contains placeholders only. Keep the real configuration outside the repository. Preflight is offline and works without optional dependencies or a secret:

```bash
python3 scripts/serve_session_console.py --auth-mode okta \
  --auth-config config/okta.example.json --check-auth-config
```

This validates **shape only**, without DNS, discovery, token exchange, credentials, application assignment or tenant verification. It reports `login_ready: false`, `organization_sso: false`, and `tenant_verification_required`. Preflight success never establishes a working login.

Only these six fields are accepted; duplicates, unknown fields and files above 16 KiB are rejected:

| Field | Contract |
|---|---|
| `issuer` | Exact HTTPS issuer including authorization-server path where appropriate; no trailing slash, credentials, query or fragment. Use the registered app's actual issuer, not an assumed example. |
| `client_id` | Public OIDC application ID. |
| `redirect_uri` | Exactly `http://127.0.0.1:<console-port>/auth/callback`, matching both CLI port and Okta registration. No remote/proxy callback support. |
| `client_secret_env` | Environment-variable name beginning `POC_OKTA_`. The value is loaded server-side at startup; preflight does not read it. Never put a secret in JSON, chat or Git. |
| `allowed_subjects` | One to 100 exact assigned OIDC subjects; no wildcard semantics. Assignment in Okta must also permit the app. |
| `operator_subjects` | Explicit subset of assigned subjects; empty by default. Other assigned users are members. |

The provider discovery document must match the exact issuer, advertise code flow, S256, RS256 and `client_secret_basic`, and supply HTTPS authorization/token/JWKS endpoints on the issuer's exact origin. Redirects are refused for backend HTTP calls. Discovery/JWKS/token responses have a 1 MiB limit and connect/read timeouts. Ambient proxy and netrc settings are disabled. If a corporate network needs proxies or custom CA support, that needs a separate reviewed configuration change; do not turn off TLS verification.

## Starting a configured local Okta pilot

After registering an OIDC **Web Application**, assign pilot accounts and register the exact callback URI. Verify the issuer, supported capabilities and tenant entitlements for that app. Obtain exact subject identifiers through trusted administration; email/display name is not the owner identifier. Never paste tokens into a website/chat to inspect claims.

Install optional dependencies in a dedicated environment:

```bash
python3 -m venv .venv-console
.venv-console/bin/python -m pip install -r requirements-console-oidc.txt
```

For Mac zsh, enter the secret privately without adding its value to shell history:

```zsh
read -s 'POC_OKTA_CLIENT_SECRET?Okta client secret: '
export POC_OKTA_CLIENT_SECRET
.venv-console/bin/python scripts/serve_session_console.py --auth-mode okta \
  --auth-config "$HOME/.config/sandbox-console/okta.json" --port 4180
unset POC_OKTA_CLIENT_SECRET
```

Use the environment-variable name specified in your external JSON. The server must retain access to that public config file to reload assignments. Any existing process on port 4180 must be deliberately stopped or use a different port with a matching registered callback/config. The installer does not provision Okta or overwrite a running console.

Open the printed loopback URL. Unauthenticated users see `/login` and **Continue with Okta**. The dashboard reports the authenticated opaque identity/role and offers **Sign out**. Login/Open Codex controls are disabled in Okta mode, and `/terminal` returns `secure_attach_relay_required` without exporting privileged host commands. Personal-mode terminal behavior remains available to the trusted operator.

## Implemented flow

```mermaid
sequenceDiagram
    participant B as Browser
    participant C as Loopback console
    participant O as Configured Okta provider
    participant W as Ownership-scoped worker
    B->>C: GET /auth/login
    C->>C: Store state, nonce and PKCE verifier for 5 minutes
    C-->>B: Browser transaction cookie + authorization redirect
    B->>O: Sign in / MFA under provider policy
    O-->>B: Registered callback with code and state
    B->>C: GET /auth/callback with transaction cookie
    C->>C: Check browser binding and consume transaction
    C->>O: Confidential code exchange with S256 verifier
    C->>O: Fetch configured JWKS
    C->>C: Library validates RS256 signature and OIDC claims
    C->>C: Check exact issuer/subject assignment and role
    C-->>B: New opaque expiring HttpOnly session cookie
    B->>C: Request with session cookie and CSRF for mutations
    C->>C: Reload assignments; derive request-local identity
    C->>W: Immutable principal/role command binding
```

Authlib handles code/PKCE exchange and OIDC claim validation; joserfc verifies signatures with a fixed RS256 allowlist. Required issuer, audience, subject, expiry, issued-at and nonce are checked, including authorized-party/access-token-hash claims when present. Tokens cannot choose a remote JWKS URL or accepted algorithm. Provider failures and callback errors return bounded messages without codes, claims or provider details. [Okta redirect model](https://developer.okta.com/docs/guides/sign-into-web-app-redirect/), [ID-token validation](https://developer.okta.com/docs/guides/validate-id-tokens/-/main/), [Authlib requests integration](https://docs.authlib.org/en/stable/oauth2/client/http/requests.html).

## Identity, expiry and revocation

- Workspace owner IDs are stable opaque hashes of the exact `(issuer, subject)` tuple, independent of email or display-name changes. Another issuer or subject gets another owner. Local-pilot files are not automatically imported; identity migrations need explicit review.
- A new immutable worker adapter is bound per authenticated request. The shared trusted operator adapter is used only for background reconciliation. Browser headers/JSON cannot select principal/role, and concurrent browser identities do not mutate the shared adapter.
- Each browser gets an independent CSRF token and a new random opaque session cookie. Successful re-login invalidates that browser's previous session. Callback transactions are browser-bound, expire after five minutes and are consumed before code exchange; replay is rejected.
- Browser sessions expire after at most one hour, 15 minutes without authenticated requests, or ID-token expiry, whichever comes first. Background dashboard polling counts as activity. Session/transaction stores are bounded to 128 entries each and protected by a lock. Restart clears all sessions. Provider ID/access tokens are not retained in browser sessions, cookies, SQLite or logs; no refresh/offline token is requested.
- Public config is reloaded on each authenticated request. Removing an assigned subject revokes its console session on its next request; changing its configured role applies on the next request. Missing/invalid config or changed issuer/client/callback fails closed. Secret rotation requires restarting the server.
- **Sign out** is a CSRF-protected local console logout. It deletes that browser's server session/cookie, without stopping sandboxes, removing workspaces or ending the upstream Okta browser session. There is no Okta back-channel logout, continuous provider introspection or immediate detection of a provider-side account/application change; such changes may remain effective only after session expiry/restart unless local assignment is removed.
- Cookies are HttpOnly and SameSite=Lax for the OIDC top-level GET callback; the personal cookie stays SameSite=Strict. This implementation uses HTTP only on loopback and does not set Secure cookies. It must not be exposed through a proxy, forwarded port or remote bind. Production HTTPS/cookie/proxy handling needs separate implementation and review.

## Validation and remaining gates

[Retained evidence](../../results/oidc-console-20261114/) covers 20 OIDC tests: signed synthetic RSA tokens, invalid signature/none/HMAC algorithms, required claims, nonce/issuer/audience/time/hash failures, discovery endpoints/capabilities, JWKS/HTTP failures, actual Authlib code-exchange request construction, browser binding/replay/expiry, session rotation/logout/assignment changes, bounds, and two concurrent identities through real loopback HTTP. Twelve profile tests, six ownership regressions and 18 existing API regressions also passed; one separate live VM lifecycle test was skipped. The OIDC tests require the optional dependency environment and otherwise explicitly skip. The simulated provider is test-only; there is no mock-login runtime flag or test bypass in the application.

These results establish a locally tested candidate, **not a real Okta or production multi-user deployment**. Remaining work:

1. Configure a real Okta tenant/application and verify actual login, MFA/application assignment, failed login recovery and logout semantics.
2. Test two distinct real identities against real worker resources, including cross-owner reads/mutations, quotas and role promotion/demotion. Current OIDC HTTP tests use a recording worker adapter; real worker ownership evidence is from separate simulated-principal checks.
3. Extend and validate the implemented personal-mode browser relay for verified organization identities; it remains disabled in Okta mode. See the [terminal runbook](../runbooks/LOCAL_CONSOLE.md#browser-terminal-for-the-local-personal-pilot-2026-11-15).
4. Add reviewed remote HTTPS/session infrastructure, organization/tenant provisioning, centralized auth audit, provider revocation/back-channel handling and deployment secrets. No remote access is enabled by this work.

See [ownership boundary](USER_ISOLATION.md), [console runbook](../runbooks/LOCAL_CONSOLE.md) and [requirements status](../REQUIREMENTS_STATUS.md). Earlier [profile-only evidence](../../results/auth-profiles-20261114/) records the preceding gated stage; it is historical, not the current adapter status.
