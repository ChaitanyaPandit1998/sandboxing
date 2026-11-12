# Strict HTTPS egress enforcement plan

**Status: initial candidate implemented and tested; full acceptance pending.** The separate mitmproxy gateway passed 16 selected checks per runtime, including both TLS-name and encrypted HTTP Host mismatches. See [candidate results and remaining gates](TLS_GATEWAY_RESULTS.md). The original CONNECT proxy remains unchanged and still has the recorded limitation.

## Required design

Place a TLS-terminating gateway between the internal session network and external destinations. The session has no direct external route. Give the agent image a dedicated gateway CA trust bundle; keep the signing key accessible only to the gateway. Do not install this CA on the Mac host or copy the key into sessions.

Authorize each request against the session's approved policy. Require CONNECT authority, TLS server name, and decrypted HTTP Host (or HTTP/2 `:authority`) to agree with the permitted hostname and port. Reject malformed or ambiguous authorities, missing/hidden names, unsupported protocols, IP literals, and unauthorized ports. A check of visible TLS SNI alone would not enforce the encrypted HTTP authority.

Resolve and validate public destination addresses before connecting; connect to the validated address and verify the upstream TLS certificate for the approved hostname. Apply the policy again to every new destination, redirect, and reused connection. Default-deny QUIC/UDP and alternate paths. Keep approval grants narrowly scoped and expiring; approval must not disable hostname or private-address checks.

Use an established gateway implementation and review its protocol handling before deployment. First validate it with synthetic HTTPS endpoints and a test-only CA, then test whether the chosen Codex/provider authentication path accepts the dedicated trust bundle. Treat certificate pinning or trust incompatibility as a blocker, not a reason to bypass inspection silently. Logs should contain redacted policy decisions and correlation IDs; exclude tokens, prompts, request bodies, and decrypted content.

## Acceptance cases

1. Approved CONNECT + matching TLS name + matching HTTP authority succeeds, with valid upstream TLS verification.
2. The existing `example.com` CONNECT / `example.org` TLS-name probe is denied.
3. Matching CONNECT/TLS names with a different encrypted HTTP Host or HTTP/2 authority is denied.
4. Missing names, encrypted/unsupported ClientHello handling, malformed authorities, duplicate Host fields, and unsupported protocols fail closed.
5. Unlisted domains, redirects to denied destinations, IP literals, alternate ports, private/link-local/metadata addresses, DNS rebinding, direct egress, and UDP bypasses are denied.
6. Request replay after approval denial/expiry fails; an approved exception permits only the approved destination and scope.
7. A successful synthetic request and an unauthenticated provider request work under the exact candidate image/runtime; an authenticated Codex smoke then verifies normal use without credential leakage.

Until these cases pass, [FR-2 remains partial](REQUIREMENTS_STATUS.md) and strict hostname allowlisting must not be described as achieved.
