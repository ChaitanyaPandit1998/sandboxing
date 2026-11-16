---
name: unit-integration-testing
description: Design and run unit, integration, and contract tests for application changes. Use when expanding coverage, validating services, or testing APIs and persistence boundaries.
---

# Unit and integration testing

## Workflow
1. Map behavior to test levels: pure logic -> unit; interactions with DB, message broker, or HTTP -> integration; shared service contracts -> contract.
2. Identify happy path, boundary values, malformed input, authentication/authorization, concurrency, and retry/error paths.
3. Match repository fixtures, test containers, and environment conventions; isolate resources and clean up state.
4. Ensure tests are deterministic, hermetic when feasible, and safe to parallelize.
5. Run targeted tests, then the relevant integration suite; record failures with command and cause.
6. Distinguish code regressions from missing infrastructure and flaky tests. Never delete or relax assertions to hide failures.

## Exit criteria
Tests describe user-visible behavior, protect important failure modes, and can be repeated by another developer with documented commands.
