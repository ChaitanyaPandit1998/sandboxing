# Wardyn Fit Assessment

**Assessment date:** 2026-11-12
**Wardyn source reviewed:** local checkout `a60890b1e` (2026-11-05), version `0.10.0-rc.13`
**Assessment type:** source and documentation review; no Wardyn deployment or live session was exercised in this assessment.

## Summary

Wardyn's current source describes a broad session-governance control plane that overlaps substantially with the platform layer proposed for this POC: users and roles, policy-driven run creation, workspace handling, egress proxying, approvals, credential brokering, audit, attach, and stop/kill flows. The POC's comparative value is its independent, evidence-backed validation of the Codex container and `runsc-next` behavior in the Lima VM.

**Provisional direction:** evaluate Wardyn as the control plane and retain the POC regression suite as a worker/runtime acceptance suite. Do not start duplicating Wardyn's control-plane capabilities before the live compatibility checks below. This is not an adoption or production-readiness approval: Wardyn labels itself pre-alpha and says not to run production workloads.

## Requirement-to-evidence matrix

| Requirement | Wardyn source evidence | Current POC evidence | Assessment / remaining check |
|---|---|---|---|
| Create, inspect, attach to, stop a session | CLI/API and run lifecycle are documented in `README.md`, `docs/TRY-IT.md`, and `docs/OPERATIONS.md`; run kill and audit behavior are described. | Sessions are launched manually with scripts and Docker in Lima. | **Wardyn covers broader workflow by design.** Live-test create/attach/stop, timeout, and cleanup with our image. |
| User and organization identity | README and operations docs describe OIDC/SSO roles, admin/member separation, and per-run ownership. | No org identity or authorization control plane. | **Wardyn has the relevant layer.** Verify our IdP, group/role mapping, and cross-user attach/inspect denial. |
| gVisor confinement | Policies describe CC2 as gVisor; Docker runner code selects the runsc runtime and refuses CC2 if runsc is unavailable. Kubernetes requires an explicitly configured `RuntimeClass` whose handler is runsc. | `runsc-next` passed the POC's targeted boundary, proxy, syscall, cross-session, and Codex workspace-write regression set; pinned stable `runsc` failed the nested namespace case. | **Strong POC evidence, not yet integrated.** Configure Wardyn's Docker CC2 runtime mapping to the POC-tested `runsc-next` alias and verify the launched container's actual runtime and policy. Do not assume a runtime name or the stable runsc behaves like the nightly. |
| Workspace and persistence | Wardyn documents workspaces, declared mounts/repos, per-user drive, and retention/operations flows. | `/workspace` is usable inside the agent container; this is not a multi-user durable workspace service. | **Wardyn covers broader lifecycle by design.** Test ownership, persistence, path restrictions, deletion/retention, and cross-session isolation. |
| Egress allowlist and approval | Wardyn policy docs specify default-deny allowlists, proxy-only routing, approvals, and denial precedence. | POC passed targeted provider proxy, exact-host allowlist, direct-egress denial, bypass, and controlled DNS-rebinding checks under `runsc-next`. | **Complementary evidence.** Repeat those negative controls against Wardyn's complete run/proxy path, including direct egress, DNS, IP literals, alternate ports, and redirects. |
| Model/provider credentials | Wardyn supports per-person provider credentials, proxy-side injection for API-key lanes, and documented Claude subscription sign-in. Codex is configured with an OpenAI provider/API-key lane and a proxy sentinel. | Codex CLI was authenticated in the local sandbox via device login; the state lived in the disposable agent home. | **Important compatibility question.** The reviewed Wardyn docs/source do not establish support for importing/reusing the Codex device-login or ChatGPT subscription session used in this POC. Verify the intended user authentication path. Do not copy a personal `auth.json` into shared images/workspaces as a shortcut. |
| Credentials for source control and other tools | Wardyn documents brokered credentials, approvals, and explicit exceptions for credential kinds that must enter a sandbox. | No organization credential broker in the POC. | **Wardyn has a broader mechanism.** Verify the specific Git provider and least-privilege scope needed by the pilot; record which credentials remain readable inside the sandbox. |
| Audit and approvals | Wardyn documents attributed audit, approval workflows, and append-only audit storage. | POC stores test output and raw evidence but has no user-attributed control-plane audit. | **Wardyn covers broader governance by design.** Live-test that the relevant run, approval, credential, and kill events appear with actor and session identity. |
| Startup and concurrency | No directly comparable measurements were found in the reviewed POC evidence. Wardyn has runner and lifecycle machinery, but documentation is not a benchmark. | Existing numbers are cached-image CLI process-start measurements, not request-to-ready session latency. | **Unknown.** Benchmark both systems on the same VM, image, policy, warm/cold conditions, and concurrency. |
| Operational readiness | Wardyn README and chart/docs describe Compose and Kubernetes deployments, but the README explicitly marks the project pre-alpha and says not to run production workloads. | POC is a manually operated Lima engineering setup; it is not an org service. | **Neither is production-ready based on this comparison.** Review upgrade, recovery, backup, support, and security ownership before any pilot with sensitive work. |

## Key compatibility risk: Codex authentication

The POC currently demonstrates Codex using a device-login session inside a temporary user home. Wardyn's reviewed model-provider documentation describes OpenAI API-key injection for Codex and documents a separate Claude subscription sign-in flow. I found no source evidence in this checkout that the exact Codex device-auth / ChatGPT subscription session used by the POC can be connected as a Wardyn-managed provider.

Before adopting Wardyn for this use case, test the desired supported credential path with a test account. If the organization requires subscription/device authentication, treat it as a product requirement and obtain a supported design from the Wardyn maintainers or plan a scoped integration. Keep the current per-session home ephemeral while testing.

## Live validation checklist

Run these with a disposable Wardyn stack and synthetic workspace/test credentials:

1. Register/configure a Docker runner that advertises CC2 through the `runsc-next` runtime alias; inspect the created container to confirm the selected runtime.
2. Create an interactive Codex run under a policy that requires CC2, attaches only the declared workspace, and uses the same CPU, memory, PID, root filesystem, capability, and `no_new_privileges` limits as the POC.
3. Confirm whether the user's supported Codex credential works; verify no provider token or login state appears in the image, logs, audit, or another session.
4. Run the POC filesystem/privilege, cross-session, egress-bypass, allowlist, DNS-rebinding, and syscall compatibility suites through the Wardyn-launched session.
5. Exercise approval, deny, retry, stop/kill, timeout, and worker restart; inspect audit records and verify cleanup/revocation.
6. Measure request-to-session-ready, attach-to-terminal-ready, first provider response, and cleanup at concurrency 1 and the agreed pilot concurrency.

**Promotion criterion:** all required identity, runtime, credential, network, workspace, cleanup, and audit behaviors pass for the exact deployed versions, or documented gaps are accepted by named owners. A passing matrix is scoped evidence; it is not a security certification.

## Live validation status

The source review and read-only runtime preflight completed, but a Wardyn run was not launched. The ordinary shell was denied access to Lima's boot-session state; a subsequent approved read-only check confirmed the VM was running, with Docker 29.9.3, `runsc`, `runsc-next`, 29 GiB free, and the two existing agent containers. A temporary source snapshot and Wardyn images were prepared for an isolated trial, then the user redirected work to pushing the POC changes before the Wardyn stack started. The temporary source and images were removed, no Wardyn containers were left behind, and the existing agent sessions were preserved. The live checks above remain outstanding.

## Reviewed source locations

- Wardyn checkout: `../../wardyn` at commit `a60890b1e`, release string `0.10.0-rc.13`.
- Wardyn docs: [`README.md`](../../wardyn/README.md), [`POLICIES.md`](../../wardyn/docs/POLICIES.md), [`OPERATIONS.md`](../../wardyn/docs/OPERATIONS.md), [`CREDENTIALS.md`](../../wardyn/docs/CREDENTIALS.md), [`TRY-IT.md`](../../wardyn/docs/TRY-IT.md), and [`VERIFY.md`](../../wardyn/docs/VERIFY.md).
- POC agent/runtime evidence: [agent session validation plan](AGENT_SESSION_VALIDATION_PLAN.md) and [`runsc-next` regression summary](../results/agent-session-20261112/runsc-next-regression-summary.json).
