---
name: concurrency-reliability
description: Design and diagnose concurrent, asynchronous, and distributed workflows safely. Use for threads, pools, locks, queues, retries, cancellation, and message processing.
---

# Concurrency and reliability

## Workflow
1. Identify shared state, resource ownership, ordering guarantees, delivery semantics, and failure domains.
2. Specify invariants: what must be atomic, exactly-once claims to avoid, acceptable duplicates, and recovery behavior.
3. Analyze race conditions, deadlocks, starvation, blocking calls, queue bounds, and backpressure.
4. Apply explicit timeouts, cancellation propagation, bounded retries with jitter, and idempotency where appropriate.
5. For Kafka/queues, examine acknowledgments/offset commits, rebalancing, poison messages, replay, and deduplication.
6. Write deterministic concurrency tests where possible; use stress/race detection tools appropriate for the language.
7. Add metrics/logging for queue depth, failed attempts, timeouts, and processing lag.

## Rules
Never imply an at-least-once system provides exactly-once business outcomes without an end-to-end design. Document ordering and consistency trade-offs.
