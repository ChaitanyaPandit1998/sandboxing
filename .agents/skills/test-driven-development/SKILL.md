---
name: test-driven-development
description: Implement behavior using a red-green-refactor cycle. Use for well-defined features or bug fixes when reliable automated tests are available; not for exploratory or purely documentary tasks.
---

# Test-driven development

## Workflow
1. Locate the right test level, framework, and existing test patterns. Define behavior and edge cases before implementation.
2. Write one focused test that fails for the expected reason (RED). Run it and capture the failing result.
3. Make the smallest production change that passes that test (GREEN). Run it again.
4. Refactor without changing behavior; rerun the tests after each meaningful refactor.
5. Repeat for invalid input, boundary conditions, errors, and regression cases as appropriate.
6. Run the broader relevant suite plus lint/build checks if available.

## Test quality
- Assert observable behavior, not private implementation details.
- Keep tests deterministic and independent; avoid sleeps, network calls, and clock assumptions where substitutes exist.
- Use fixtures and mocks only at real boundaries; do not mock the unit under test.
- Include a regression test for fixed defects.

## If tests cannot run
Explain the blocker and what was inspected. Never claim a red/green cycle occurred if the environment prevented execution.
