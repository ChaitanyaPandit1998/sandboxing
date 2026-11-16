# Pilot alert rules and review criteria

**Version:** `pilot-review-v1` (2026-11-14). These are starting thresholds for the single-operator pilot, not validated production detection thresholds. The worker's [rule catalog](../../scripts/alert_rules.py) is the source of truth and is shown in the console's Detection rules view. Changes are reviewed/deployed in source; there is no UI editor.

| Signal | Priority | Trigger |
|---|---|---|
| Policy drift | High | One failed selected configuration check; one event per failing episode. |
| Worker lifecycle failure | Review | A worker failure or incomplete cleanup event. |
| Egress denied | Review | One new deduplicated denied flow/stage observation. |
| Repeated egress denials | High | At least five distinct denied flow/stage observations collected within five minutes. |
| Resource pressure | Review | CPU ≥90%, memory ≥85%, or Docker PIDs ≥112: at least three consecutive valid samples spanning at least 60 seconds. |
| Incomplete samples | Review | At least three consecutive incomplete samples spanning at least 60 seconds. |
| Collector gap / clock change | Review | On resumption, the prior collection is more than 90 seconds old, or its timestamp is in the future. This is a worker-level signal. |

A gap above 90 seconds resets a sustained-sample streak. Repeated sampling at the same timestamp does not advance it. Missing/invalid resource values reset pending resource streaks, but do not establish recovery from an already-observed problem. A valid below-threshold sample establishes resource recovery. Policy drift requires a verified healthy check before a subsequent failing episode creates another event. Alert review state is independent: resolving an alert does not remediate the condition or stop a session.

CPU, memory and PIDs are Docker-reported measurements; memory is percentage of the 1 GiB agent limit, and Docker PIDs can include runtime overhead. Collection now includes these measurements in the resident loop. The nominal wait is 30 seconds **after** a completed collection, so the real cadence also includes sampling work. This is not continuous load monitoring. Sustained state is persisted in SQLite so a collector restart does not erase progress; long collection gaps still reset pending streaks.

Burst timing uses **collection observation time**, not packet time. The gateway sampling window is up to 200 log lines from the previous 15 minutes, so older traffic read in one collection can look like a burst. Distinct flow/stage observations are not necessarily unique application requests. Duplicate reads do not increase counts. A burst creates one derived event per threshold episode; it does not emit another burst event for every retry while above threshold. Individual denial events remain separate.

A collector cannot record its own downtime while stopped. The UI's stale banner is the immediate visibility mechanism; the durable gap signal is emitted only after collection resumes. These thresholds do not measure uptime or establish complete incident coverage. New evidence records the rule version; evidence predating that metadata keeps `legacy-observation-v0`. Alert metadata labels the latest evidence version, while the expanded review panel shows the **current** trigger/guidance. Historical rows are not silently attributed to the new rule version.

## Review procedure

1. Check subject, observation time, rule version and collector freshness. Distinguish a real workload from a documented validation session.
2. Compare policy state, current utilization and lifecycle history. For denials, review the expected workload locally; blocked destination names are not captured in the journal. Do not widen the allowlist merely to clear an alert.
3. Acknowledge to record that the local operator has seen the item. Investigate and use the existing Stop control if intervention is warranted; these rules never automatically stop sessions or change enforcement.
4. Resolve after review. A distinct new evidence event reopens a resolved alert. A derived threshold episode recurs only after its recovery/reset conditions. The current audit records state actions, not a written incident investigation or SSO identity.

The UI includes rule-specific review guidance: configuration drift calls for approved-policy comparison; lifecycle failures call for owned-resource cleanup review; repeated denials call for expected-destination/retry review; resource pressure calls for workload/capacity analysis; missing samples/gaps call for Docker, gateway, VM/Mac sleep and clock checks. None is proof of malicious behavior. No prompt-injection detector, malware scanner, external notification, auto-quarantine or new privilege is introduced.

## Validation and remaining work

- Eight rule tests exercise exact threshold boundaries, deduplication, time windows, resource recovery/reopening, missing/invalid measurements, sample gaps, duplicate timestamps, persisted streak progress and backwards clock handling.
- Seven journal tests and four sanitization/policy tests passed; 17 local API tests passed with one separate live lifecycle test skipped. Rules are authenticated and read-only; new history filters are bounded.
- The updated resident service passed 11 isolated service checks. A disposable real session produced five blocked CONNECT requests (403), and resident collection created one high-priority burst alert. The next collection did not duplicate the five denied-flow events or the burst episode. The session was stopped; workspace retained.
- The browser verified seven rule cards, current trigger/review guidance, burst-history filtering and resolution of only the synthetic validation alerts, with no console errors. The active API/catalog and additive evidence-version migration were checked. [Evidence](../../results/alert-rules-20261114/).

Resource pressure, missing telemetry and clock/gap boundaries used injected unit samples; no CPU/memory stress, model calls, full incident response or false-positive calibration was performed. Next run representative allowed workloads, classify expected alerts, calibrate thresholds and expand rules with controlled negative tests before adding organization delivery or enforcement automation.
