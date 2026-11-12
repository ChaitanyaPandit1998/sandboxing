# Synthetic stream and gateway failure checks

**Date:** 2026-11-13. **Result:** 11/11 checks passed under each of `runc` and `runsc-stable-20261109` (22 total).

## Scope

The test client receives synthetic SSE responses through the candidate gateway's existing TLS/HTTP authorization and streaming hooks. A test-only subclass replaces upstream DNS/public-address routing with one loopback TLS fixture inside the gateway container. Both gateway and clients have only an internal Docker network. No credentials, model requests, real provider traffic, or external egress are used.

**This fixture does not validate production DNS/public-IP enforcement, Codex retry/resume behavior, or organization-platform recovery.** Production `tls_gateway.py` is unchanged. The loopback routing override is confined to `tests/fixtures/stream_gateway/route.py` and is not used by the session runner. Upstream TLS certificate verification stays enabled with a temporary fixture CA.

## Observations

| Check | Result under both runtimes |
|---|---|
| Progressive delivery | Three SSE events arrived separately; the first preceded the final completion marker by at least 0.3 seconds. |
| Truncated stream | The first event arrived but the completion marker did not. The test client classified the response as incomplete. |
| Idle stall | A first event arrived, then the client's 0.8-second socket timeout fired. |
| Client cancellation | The client closed after its first event without treating the stream as complete. |
| Request after cancellation | A new stream completed successfully. |
| Upstream reset | The reset produced a transport error or a gateway 502, rather than successful completion. |
| Provider 503 | The gateway preserved the synthetic upstream 503 response. |
| Gateway process killed mid-stream | The active stream ended without its completion marker. |
| New request after process restart | The test supervisor restarted the gateway process; a new request completed using the retained temporary CA. |
| Gateway paused | New requests timed out without receiving an SSE event or completion marker. |
| Gateway resumed | A fresh stream completed successfully. |

For the truncated case, the observed HTTP stream ended without a client HTTP exception, even though the application-level completion marker was missing. Consumers must check their protocol's terminal event; HTTP 200 alone does not prove that a streamed task completed. The synthetic marker is not the full OpenAI Responses event protocol.

The restart check uses a test-only local process supervisor. It proves recovery for a **new request** after that process restart; the interrupted stream was not resumed, and this is not worker failover or persisted-session reconciliation. It does not measure uptime or a production recovery SLO.

## Reproduce

Inside the disposable Linux VM, with cached mitmproxy and POC client images:

```bash
python3 scripts/run_stream_failure_smoke.py --output results/stream-failure-unique-run
```

The runner creates uniquely named containers/networks, temporary CA material, and a local TLS fixture, then removes them in `finally`. Post-run inspection found no remaining `poc-stream-*` containers or networks. Only JSON observations, source hashes, and image metadata were copied back; private CA/leaf keys were not exported.

Evidence: [summary](../../results/stream-failures-20261113/summary.json), [runc observations](../../results/stream-failures-20261113/runc.json), [stable runsc observations](../../results/stream-failures-20261113/runsc-stable-20261109.json), and [environment/source fingerprints](../../results/stream-failures-20261113/environment.json). The implementation uses mitmproxy's documented [streaming hooks](https://docs.mitmproxy.org/stable/overview/features/#streaming).

## Next gate: provisioning integration

The operator session runner already provisions the TLS gateway, temporary Codex home, trust certificate, and explicit HTTPS provider together. The next platform work is to verify the selected control plane can apply that exact policy, retain a managed workspace separately from credentials, and reconcile stop/expiry/restart cleanup. Then inject network faults into an authenticated Codex run and verify provider-specific completion, retries, and recovery. Five-session request-to-ready through the service remains unmeasured.
