# Documentation

Start with the [POC overview](overview/POC_SUMMARY.md). For the current implemented/partial/untested requirements, use [Requirements status](REQUIREMENTS_STATUS.md). For a chronological record of changes, failures, and commits, use the root [Development log](../DEVLOG.md).

## Reading guide

| Need | Canonical document |
|---|---|
| Leadership update | [Executive summary](overview/EXECUTIVE_SUMMARY.md) |
| Design, findings, and limits | [POC overview](overview/POC_SUMMARY.md) |
| What is complete or still pending | [Requirements status](REQUIREMENTS_STATUS.md) |
| Create/manage a local pilot session | [Managed worker runbook](runbooks/MANAGED_WORKER.md) |
| Manage real sessions from the local UI | [Local console runbook](runbooks/LOCAL_CONSOLE.md) |
| Private Codex login, CA trust, HTTPS transport, cleanup, and authentication results | [Codex TLS guide](runbooks/CODEX_TLS.md) |
| Gateway implementation, tested policy cases, and remaining acceptance criteria | [TLS gateway](security/TLS_GATEWAY.md) |
| Detailed runtime benchmarks and historical security probes | [Experiment report](reports/REPORT.md) |
| Cached five-container startup measurements | [Sandbox readiness](reports/SESSION_READINESS_RESULTS.md) |
| Synthetic streaming/network-failure checks | [Stream failures](reports/STREAM_FAILURE_RESULTS.md) |
| Broader security test plan | [Security validation](validation/SECURITY_VALIDATION_PLAN.md) |
| Agent/runtime compatibility and validation evidence | [Agent validation](validation/AGENT_SESSION_VALIDATION_PLAN.md) |
| Platform delivery sequence | [Roadmap](platform/PLATFORM_ROADMAP.md) |
| Proposed service API, policy, and lifecycle contract | [Control-plane spec](platform/SESSION_CONTROL_PLANE_SPEC.md) |
| Wardyn evaluation and remaining integration questions | [Wardyn assessment](platform/WARDYN_FIT_ASSESSMENT.md) |
| Current static UI and how to preview it | [UI prototype](platform/UI_PROTOTYPE.md) |

## Layout and ownership

```text
docs/
  README.md                   reading guide
  REQUIREMENTS_STATUS.md      current coverage and acceptance gaps
  overview/                   technical and executive summaries
  runbooks/                   operator instructions and related validation
  security/                   gateway design, results, and acceptance gates
  reports/                    measured runtime/readiness/failure results
  validation/                 test plans and compatibility matrices
  platform/                   delivery plan, API contract, Wardyn, UI status
  diagrams/                   runtime, egress, file flow, and metric SVGs
```

Keep current coverage in the requirements matrix, operational instructions in runbooks, measured results beside their evidence links, and chronology in `DEVLOG.md`. Summaries should link to these sources rather than accumulating duplicate dated progress paragraphs. The runtime diagrams and metrics chart depict the experiment and archived benchmark; they do not depict a completed organization service.

## Consolidated documents

- `CODEX_TLS_SESSION.md`, `CODEX_HTTPS_TRANSPORT.md`, and `CODEX_TLS_AUTHENTICATED_RESULTS.md` were merged into [Codex TLS](runbooks/CODEX_TLS.md), retaining the initial fallback result and later explicit-HTTPS result separately.
- `TLS_GATEWAY_RESULTS.md` and `EGRESS_ENFORCEMENT_PLAN.md` were merged into [TLS gateway](security/TLS_GATEWAY.md), retaining the implementation evidence and uncompleted acceptance cases.
- Repeated progress paragraphs were removed from summaries/plans. The [development log](../DEVLOG.md), source reports, and raw `results/` evidence retain the chronology and test limits. Superseded files remain accessible in Git history.
