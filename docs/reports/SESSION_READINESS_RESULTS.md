# Five-session sandbox readiness measurement

**Date:** 2026-11-12. **Scope:** cached image, no external network, no provider credentials, no model calls.

Ten rounds per runtime launched five concurrent containers, retaining each until all five readiness probes finished. Runtime order alternated between rounds. Each session used 1 CPU, 1 GiB memory, 128 PIDs, non-root UID 10001, dropped capabilities, no-new-privileges, read-only root, and private memory-backed home/workspace/tmp paths. All sessions used the same immutable agent image ID recorded in the environment file.

Readiness begins immediately before `docker run` and ends when `docker exec` verifies workspace writability, writes a marker, and successfully runs `codex --version`. Cleanup time is excluded. Percentiles use the nearest-rank method over 50 sessions per runtime. The rounds are grouped samples on one VM; these are exploratory results, not a fleet SLO estimate.

| Runtime | Successful starts | p50 | p95 | Maximum | Cleanup failures |
|---|---:|---:|---:|---:|---:|
| `runc` | 50/50 | 0.228 s | 0.486 s | 0.486 s | 0 |
| `runsc-stable-20261109` | 50/50 | 0.307 s | 0.444 s | 0.479 s | 0 |

Both runtime paths were below 20 and 25 seconds for this narrow readiness definition. This establishes a five-concurrent-container smoke and cached-image lower-level timing. It does not establish 20-user capacity, authenticated Codex readiness, a usable terminal attach path, workspace persistence, queue/API latency, image pull/build latency, provider response time, or uptime. FR-1 and NFR-1 therefore become partial rather than complete.

Evidence: [environment](../../results/session-readiness-20261112/environment.json), [raw samples](../../results/session-readiness-20261112/raw.jsonl), [summary](../../results/session-readiness-20261112/summary.json). Runner: [`measure_session_readiness.py`](../../scripts/measure_session_readiness.py).

Run inside the dedicated Linux VM with the existing cached image and registered runtimes:

```bash
python3 scripts/measure_session_readiness.py --rounds 10 --concurrency 5 \
  --output results/session-readiness-unique-run
```

Next measure request-to-ready through the chosen control plane, persistent workspace setup, proxy readiness, and terminal attach. Report both latency targets until the `<20s` whiteboard versus `<25s` pilot discrepancy is resolved.
