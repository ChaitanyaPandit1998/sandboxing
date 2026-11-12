# TLS gateway candidate validation

**Date:** 2026-11-12. **Status:** experimental candidate, not promoted to the agent session runner.

The new [`tls_gateway.py`](../tls_gateway.py) addon uses mitmproxy 12.3.1, pinned by image digest in [`run_tls_gateway_smoke.sh`](../scripts/run_tls_gateway_smoke.sh). The proxy terminates TLS with a CA generated in its memory-backed filesystem. Only the public CA certificate is provided to test clients; the private key and test networks/containers are removed on exit. The Mac trust store is untouched. Requests contain no user credentials or prompts.

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

Evidence is in [`results/tls-gateway-20261112/`](../results/tls-gateway-20261112/): per-runtime checks, redacted decision logs, image IDs, source hashes, and VM/kernel/engine metadata. This run used kernel `7.0.0-43-generic`; the earlier archived benchmark used `7.0.0-38-generic`. It is not a paired performance rerun.

## Remaining gates

An [isolated Codex session](CODEX_TLS_SESSION.md) subsequently passed private device login, a synthetic workspace-write task, incremental CLI event delivery, and cancellation after WebSocket denial and fallback. A further [explicit HTTPS transport run](CODEX_HTTPS_TRANSPORT.md) passed three authenticated tasks with zero error events, cancellation, and live hostname-policy probes. Both sessions were logged out and removed.

The original `allowlist_proxy.py`, its published results, and the default agent runner remain unchanged. The new candidate closes the two tested hostname mismatch cases in this HTTP/1.1 setup and supports the demonstrated authenticated HTTPS tasks without reconnect errors. It does not yet establish the full strict-egress acceptance matrix or production transport reliability.

Still validate controlled DNS rebinding and mixed DNS answers, invalid upstream certificates, redirects/reused connections, malformed/fragmented requests, ECH, HTTP/2 refusal, UDP/QUIC paths, approval denial/expiry, streaming/cancellation, and cleanup on failures. HTTP/2 is disabled, raw TCP tunneling is disabled, and Upgrade is refused. Before promotion, repeat these checks with the exact agent image, supported certificate-trust settings, and the intended device-login/provider flow. Keep FR-2 partial until the complete path is verified.

## Reproduce inside the disposable VM

```bash
POC_TLS_OUTPUT=results/tls-gateway-unique-run bash scripts/run_tls_gateway_smoke.sh
```

The digest-pinned mitmproxy image and the cached `local/gvisor-poc:latest` client image must already exist. Each run uses dedicated temporary networks and removes only its own resources. It has no live user approval service or credentials.

The implementation follows mitmproxy's [event hook API](https://docs.mitmproxy.org/stable/api/events.html), [options reference](https://docs.mitmproxy.org/stable/concepts/options/), and [certificate model](https://docs.mitmproxy.org/stable/concepts/certificates/).
