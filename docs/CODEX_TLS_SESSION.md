# Codex login through the TLS gateway

**Status (reviewed 2026-11-13):** the first authenticated task succeeded after WebSocket denials and fallback. A subsequent [explicit HTTPS transport run](CODEX_HTTPS_TRANSPORT.md) passed three authenticated workspace tasks with zero error events, cancellation, and live hostname-policy checks. Both temporary sessions were logged out and removed. Start a new session and complete private sign-in before using these commands again.

The [official authentication documentation](https://learn.chatgpt.com/docs/auth#custom-ca-bundles) describes `CODEX_CA_CERTIFICATE` and the `SSL_CERT_FILE` fallback. Both point to the public test CA in this session; `NODE_EXTRA_CA_CERTS` also supports the preflight client. Certificate verification remains enabled. No CA is installed on the Mac.

## Prepare inside the disposable VM

Copy `tls_gateway.py` and `scripts/run_codex_tls_session.sh` into the same repository layout in the VM. Then run:

```bash
bash scripts/run_codex_tls_session.sh start
bash scripts/run_codex_tls_session.sh status
```

The runner uses fixed, ownership-labelled resources prefixed `poc-codex-tls-` and refuses to replace existing containers/networks. It starts the digest-pinned mitmproxy gateway and the cached Codex image, restricts destinations to `auth.openai.com`, `chatgpt.com`, and `api.openai.com`, and gives the session only an internal network. The container has a read-only root and temporary writable home/workspace/tmp filesystems. Codex container Docker logging is disabled; interactive login stays in the user's terminal. The gateway's private CA remains in gateway tmpfs. The only trust material mounted into the session is the public certificate.

The runner now writes the explicit HTTPS provider configuration into the temporary Codex home. See [configuration and validation status](CODEX_HTTPS_TRANSPORT.md). It preserves the gateway's Upgrade denial and hostname checks.

## Private login from Mac Terminal

```bash
limactl shell gvisor-poc -- docker exec -it poc-codex-tls-session codex login --device-auth
```

Complete the browser flow privately. Do not paste login codes, auth files, or tokens into chat. After login, the operator can check the authentication method without reading credential files, then run a fixed harmless workspace-write task, inspect completion/streaming and cancellation, and verify redacted gateway events. Do not copy existing personal authentication material into the session.

## Stop

After the authenticated checks, run this inside the VM:

```bash
bash scripts/run_codex_tls_session.sh stop
```

For the guest copy staged during this test, the Mac command is:

```bash
limactl shell gvisor-poc -- bash /tmp/poc-codex-tls-src/scripts/run_codex_tls_session.sh stop
```

Stopping deletes the memory-backed login home and workspace, gateway CA, and owned networks/containers. This test does not implement the planned persistent workspace or a session-management API. Restarting the session requires private sign-in again.
