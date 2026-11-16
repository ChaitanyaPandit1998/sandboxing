---
name: performance-profiling
description: Investigate and improve CPU, memory, latency, throughput, and query performance using measurements. Use for slow code, bottlenecks, resource regressions, and optimization requests.
---

# Performance profiling

## Workflow
1. Clarify the metric and target: latency percentiles, throughput, CPU, memory, allocations, or cost.
2. Reproduce under a controlled representative workload. Record baseline, environment, dataset, and variance.
3. Profile first: CPU, allocations, locks, queries, tracing, or flamegraphs as the stack allows.
4. Identify the dominant bottleneck and the smallest change likely to help. Include algorithmic and I/O causes.
5. Re-run the same benchmark with consistent conditions; compare before and after, including correctness and tail latency.
6. Check regressions under concurrency and realistic input size. Revert optimizations that do not measurably help.
7. Report numbers, method, uncertainty, and trade-offs.

## Rules
Do not claim a performance gain without measurements. Avoid micro-optimizations that reduce readability without meaningful benefit.
