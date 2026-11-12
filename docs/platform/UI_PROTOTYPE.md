# Session console UI prototype

This is the retained static design prototype. The separate [live local console](../runbooks/LOCAL_CONSOLE.md) now manages real worker sessions through a loopback API. Its login/attach path uses private Mac Terminal handoff; browser terminal relay remains pending.

The first UI prototype is a self-contained static page in [`../../ui/prototype/`](../../ui/prototype). It demonstrates the session lifecycle and the information an operator should see before operating a real agent sandbox.

## Run locally

From the repository root:

```bash
python3 -m http.server 4173 --bind 127.0.0.1
```

Open `http://127.0.0.1:4173/ui/prototype/` in a browser. Serving the repository root also makes its documentation and diagram links reachable. The prototype has no package dependencies, backend service, or external font/image requests.

## What is interactive

- Create a sample Codex session and choose `runc`, pinned `runsc`, `runsc-next`, or `runsc-stable-20261109`.
- View the matching `run_agent_model_smoke.sh start` command and copy it to run manually inside the Lima VM.
- Simulate session creation and stopping; update the session list, status counts, and activity feed.
- Review the current network-policy warning and open the architecture or validation documentation.

Every session row and resource indicator is demo data. The buttons do not start, inspect, or stop Docker containers. The UI does not execute shell commands or expose credentials. Real session provisioning needs an authenticated backend that validates requests, applies approved OCI policy, manages credentials and workspace retention, and reports the real container state.

Requirement status: session monitoring is only represented by simulated prototype data; live session telemetry and suspicious-activity detection are not implemented. See the [requirements status matrix](../REQUIREMENTS_STATUS.md).

## Current design constraints

The demo intentionally surfaces the observed TLS tunnel finding: the POC proxy accepts a CONNECT to an allowlisted host, but does not enforce the TLS SNI or HTTP Host inside the encrypted tunnel. Do not represent this prototype or the current proxy as a production-ready session platform or strict domain allowlist.

Before wiring the UI to real session operations, address TLS-aware egress enforcement, define the operator/user authorization model, and add backend-owned lifecycle and cleanup handling. Keep the CLI command preview as a development aid rather than allowing the browser to send arbitrary shell text.
