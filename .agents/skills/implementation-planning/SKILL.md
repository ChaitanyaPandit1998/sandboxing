---
name: implementation-planning
description: Plan implementation of features or changes before editing code. Use for multi-file features, ambiguous requirements, architectural changes, and risky modifications; skip for trivial edits.
---

# Implementation planning

## Workflow
1. Restate the requested outcome and observable acceptance criteria. Separate facts, assumptions, and unknowns.
2. Inspect repository instructions, entry points, relevant tests, APIs, data models, and existing conventions before choosing a design.
3. Identify the smallest coherent change, affected modules, failure modes, backward-compatibility constraints, and rollout needs.
4. Write a short execution plan with ordered steps, files likely to change, validation commands, and risks. Prefer incremental, independently verifiable steps.
5. If requirements are ambiguous but nonblocking, state the assumption and proceed; ask only when a decision is truly blocking or irreversible.
6. Implement against the plan; update the plan when new evidence contradicts it.
7. Compare the completed change with acceptance criteria and disclose remaining gaps.

## Guardrails
- Do not invent repository structure or claim tests were run when they were not.
- Prefer existing abstractions over speculative frameworks or large rewrites.
- Do not perform destructive schema changes, external writes, or production deployments without appropriate authorization.

## Deliverable
A brief plan; completed edits; test evidence; remaining risks or unverified assumptions.
