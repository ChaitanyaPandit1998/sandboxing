---
name: observability
description: Add or review actionable logs, metrics, traces, and alert signals. Use for production diagnostics, new request flows, async pipelines, and reliability improvements.
---

# Observability

## Workflow
1. Define what operators need to know: success, latency, errors, saturation, and business outcome.
2. Follow existing telemetry stack, naming conventions, trace-context propagation, and log schemas.
3. Add structured logs at meaningful boundaries with stable event names and correlation IDs.
4. Add bounded-cardinality metrics (rates, errors, durations, queue lag) and traces for cross-service operations.
5. Prevent sensitive data leakage and high-cardinality labels; avoid logging full payloads by default.
6. Distinguish expected business errors from operational failures; avoid duplicate noisy logging.
7. Validate that telemetry is emitted and documented, and name signals useful for dashboards/alerts.

## Deliverable
Telemetry changes, suggested dashboard/alert signals, and verification status.
