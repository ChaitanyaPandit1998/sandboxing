---
name: database-change-safety
description: Plan and implement safe schema, query, and migration changes for relational or document databases. Use for migrations, indexes, data backfills, transaction changes, and performance-sensitive queries.
---

# Database change safety

## Workflow
1. Inspect database engine/version, schema, existing migrations, query patterns, table sizes if available, and deployment model.
2. State invariants: correctness, uniqueness, referential integrity, compatibility with old and new application versions.
3. For production-facing changes, prefer expand-migrate-contract: additive schema first, backfill with observability, switch readers/writers, then remove old fields in a later deployment.
4. Assess locking, backfill batching, transaction boundaries, long-running queries, and rollback feasibility.
5. Use parameterized queries; validate index usefulness against query patterns and write costs.
6. Test migrations against representative schema/data and verify downgrade or recovery strategy where applicable.
7. Provide deploy order, verification queries, and operational rollback or forward-fix approach.

## Guardrails
No destructive migrations or mass data changes without explicit authorization and backups/recovery plan. Do not assume a migration is zero-downtime without measuring its effects.
