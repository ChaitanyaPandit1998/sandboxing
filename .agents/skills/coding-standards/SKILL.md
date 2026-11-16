---
name: coding-standards
description: Write and improve readable, maintainable production code using existing project conventions. Use when implementing features, editing code, or standardizing code quality; not for pure review-only requests.
---

# Coding standards

## Workflow
1. Read repository conventions and nearby source before editing. Follow existing language, formatting, naming, and module boundaries.
2. Prefer simple cohesive functions and explicit names. Minimize mutable shared state, duplication, hidden side effects, and unnecessary indirection.
3. Use appropriate types and validation at boundaries. Keep dependencies directed inward and public APIs stable unless change is requested.
4. Make error behavior explicit. Do not silently swallow errors; preserve diagnostic context and avoid leaking secrets.
5. Consider time/space complexity and failure modes, but do not optimize without evidence.
6. Add comments for non-obvious rationale rather than narrating code. Update nearby documentation when behavior changes.
7. Run the repository formatter, linter, and relevant tests when available; report what ran.

## Decision checklist
- Are names descriptive and responsibilities focused?
- Does the implementation preserve existing behavior outside the request?
- Are boundary cases and failure paths handled?
- Is the code easier to understand than a more elaborate alternative?

## Anti-patterns
Do not apply SOLID or patterns mechanically; do not refactor unrelated modules; do not change dependencies just for style.
