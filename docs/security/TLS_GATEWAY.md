# TLS gateway candidate validation

**Date:** 2026-11-12. **Status:** experimental candidate, not promoted to the agent session runner.

The new [`tls_gateway.py`](../../tls_gateway.py) addon uses mitmproxy 12.3.1, pinned by image digest in [`run_tls_gateway_smoke.sh`](../../scripts/run_tls_gateway_smoke.sh). The proxy terminates TLS with a CA generated in its memory-backed filesystem. Only the public CA certificate is provided to test clients; the private key and test networks/containers are removed on exit. The Mac trust store is untouched. Requests contain no user credentials or prompts.

The gateway validates CONNECT authority, TLS SNI, and decrypted HTTP Host before forwarding. It rejects disallowed hosts/ports, ambiguous Host headers, plaintext tunnels, and protocol upgrades. Before opening an upstream connection it resolves the approved name, rejects non-public answers, pins the selected IP, and retains the hostname for TLS verification. Lazy upstream connections and disabled certificate sniffing prevent an early upstream connection before request authorization. Body streaming is enabled for allowed requests and responses; real provider streaming remains unverified.

## Observed results

All **16/16 checks passed under both runc and runsc-stable-20261109**:

- Approved HTTPS to `example.com` returned 200.
- The recorded CONNECT `example.com` / TLS SNI `example.org` bypass returned 403.
- Matching CONNECT/TLS with a different encrypted HTTP Host returned 403.
- CONNECT Host mismatch, duplicate Host, missing SNI, unlisted CONNECT, IP literals, metadata address, alternate port, HTTP Host port mismatch, plaintext inside CONNECT, and Upgrade requests were denied.
- A client without the test CA raised `SSLCertVerificationError`.
- An unauthenticated request to `api.openai.com/v1/models` returned the expected 401.
- Direct external TCP egress from the internal client network failed.

The earlier startup attempt encountered an image entrypoint that expected root; the runner now invokes mitmdump directly as UID 10001. Exporting the public CA from tmpfs required `docker exec`, rather than `docker cp`. An initial positive provider check against `/` returned 421; the API-specific control now checks `/v1/models` and requires 401.

Evidence is in [`results/tls-gateway-20261112/`](../../results/tls-gateway-20261112): per-runtime checks, redacted decision logs, image IDs, source hashes, and VM/kernel/engine metadata. This run used kernel `7.0.0-43-generic`; the earlier archived benchmark used `7.0.0-38-generic`. It is not a paired performance rerun.

## Remaining gates

An [isolated Codex session](../runbooks/CODEX_TLS.md) subsequently passed private device login, a synthetic workspace-write task, incremental CLI event delivery, and cancellation after WebSocket denial and fallback. A further [explicit HTTPS transport run](../runbooks/CODEX_TLS.md#explicit-https-configuration-and-validation) passed three authenticated tasks with zero error events, cancellation, and live hostname-policy probes. Both sessions were logged out and removed.

The original `allowlist_proxy.py`, its published results, and the default agent runner remain unchanged. The new candidate closes the two tested hostname mismatch cases in this HTTP/1.1 setup and supports the demonstrated authenticated HTTPS tasks without reconnect errors. It does not yet establish the full strict-egress acceptance matrix or production transport reliability.

Still validate controlled DNS rebinding and mixed DNS answers, invalid upstream certificates, redirects/reused connections, malformed/fragmented requests, ECH, HTTP/2 refusal, UDP/QUIC paths, approval denial/expiry, streaming/cancellation, and cleanup on failures. HTTP/2 is disabled, raw TCP tunneling is disabled, and Upgrade is refused. Before promotion, repeat these checks with the exact agent image, supported certificate-trust settings, and the intended device-login/provider flow. Keep FR-2 partial until the complete path is verified.

## Reproduce inside the disposable VM

```bash
POC_TLS_OUTPUT=results/tls-gateway-unique-run bash scripts/run_tls_gateway_smoke.sh
```

The digest-pinned mitmproxy image and the cached `local/gvisor-poc:latest` client image must already exist. Each run uses dedicated temporary networks and removes only its own resources. It has no live user approval service or credentials.

The implementation follows mitmproxy's [event hook API](https://docs.mitmproxy.org/stable/api/events.html), [options reference](https://docs.mitmproxy.org/stable/concepts/options/), and [certificate model](https://docs.mitmproxy.org/stable/concepts/certificates/).

## Enforcement design and remaining acceptance

**Status: initial candidate implemented and tested; full acceptance pending.** The separate mitmproxy gateway passed 16 selected checks per runtime, including both TLS-name and encrypted HTTP Host mismatches. See [candidate results and remaining gates](TLS_GATEWAY.md). The original CONNECT proxy remains unchanged and still has the recorded limitation.

### Required design

Place a TLS-terminating gateway between the internal session network and external destinations. The session has no direct external route. Give the agent image a dedicated gateway CA trust bundle; keep the signing key accessible only to the gateway. Do not install this CA on the Mac host or copy the key into sessions.

Authorize each request against the session's approved policy. Require CONNECT authority, TLS server name, and decrypted HTTP Host (or HTTP/2 `:authority`) to agree with the permitted hostname and port. Reject malformed or ambiguous authorities, missing/hidden names, unsupported protocols, IP literals, and unauthorized ports. A check of visible TLS SNI alone would not enforce the encrypted HTTP authority.

Resolve and validate public destination addresses before connecting; connect to the validated address and verify the upstream TLS certificate for the approved hostname. Apply the policy again to every new destination, redirect, and reused connection. Default-deny QUIC/UDP and alternate paths. Keep approval grants narrowly scoped and expiring; approval must not disable hostname or private-address checks.

Use an established gateway implementation and review its protocol handling before deployment. First validate it with synthetic HTTPS endpoints and a test-only CA, then test whether the chosen Codex/provider authentication path accepts the dedicated trust bundle. Treat certificate pinning or trust incompatibility as a blocker, not a reason to bypass inspection silently. Logs should contain redacted policy decisions and correlation IDs; exclude tokens, prompts, request bodies, and decrypted content.

### Acceptance cases

1. Approved CONNECT + matching TLS name + matching HTTP authority succeeds, with valid upstream TLS verification.
2. The existing `example.com` CONNECT / `example.org` TLS-name probe is denied.
3. Matching CONNECT/TLS names with a different encrypted HTTP Host or HTTP/2 authority is denied.
4. Missing names, encrypted/unsupported ClientHello handling, malformed authorities, duplicate Host fields, and unsupported protocols fail closed.
5. Unlisted domains, redirects to denied destinations, IP literals, alternate ports, private/link-local/metadata addresses, DNS rebinding, direct egress, and UDP bypasses are denied.
6. Request replay after approval denial/expiry fails; an approved exception permits only the approved destination and scope.
7. A successful synthetic request and an unauthenticated provider request work under the exact candidate image/runtime; an authenticated Codex smoke then verifies normal use without credential leakage.

Until these cases pass, [FR-2 remains partial](../REQUIREMENTS_STATUS.md) and strict hostname allowlisting must not be described as achieved.
