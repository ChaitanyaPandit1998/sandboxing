---
name: behavior-preserving-refactoring
description: Refactor existing code to improve maintainability without changing externally observable behavior. Use for cleanup, decomposition, renaming, or duplication removal.
---

# Behavior-preserving refactoring

## Workflow
1. Describe the code smell, desired improvement, and behaviors that must remain unchanged.
2. Inspect callers, tests, public interfaces, data formats, and compatibility constraints.
3. Establish a baseline by running existing tests; add characterization tests for important untested behavior.
4. Make small reversible transformations. Prefer one structural idea per step.
5. Rerun targeted tests and relevant quality checks after each substantive change.
6. Review the final diff for accidental feature changes, deleted edge cases, and public API shifts.
7. Summarize what got simpler and how behavioral equivalence was checked.

## Rules
- No unrelated formatting churn or large rewrites.
- Separate performance or semantic changes from refactoring; obtain a new acceptance criterion for them.
- If baseline tests fail, report this before proceeding rather than attributing failures to the refactor.
