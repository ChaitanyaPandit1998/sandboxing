---
name: systematic-debugging
description: Diagnose exceptions, failed tests, crashes, deadlocks, and unexpected behavior by reproducing and isolating root causes. Use when investigating defects; not for speculative code rewrites.
---

# Systematic debugging

## Workflow
1. Capture symptoms: expected vs actual behavior, environment, exact error, timestamps, recent changes, and reproduction steps.
2. Reproduce using the smallest reliable command or test. If not reproducible, state the uncertainty.
3. Trace data and control flow from entry point to failure. Inspect logs, stack traces, state, and boundaries.
4. Propose competing hypotheses and test the cheapest discriminating observation first.
5. Identify the root cause before patching. Prefer the smallest fix that addresses the cause rather than suppressing symptoms.
6. Add a regression test; run targeted and relevant broader checks.
7. Summarize cause, fix, evidence, and residual risk.

## Rules
- Do not randomly change timeouts, retry counts, or catch blocks to mask a bug.
- Redact secrets and personal data from logs and reports.
- For concurrency issues, examine lock ordering, ownership, thread safety, and cancellation explicitly.
