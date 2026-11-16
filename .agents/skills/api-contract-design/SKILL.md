---
name: api-contract-design
description: Design, extend, and review HTTP or RPC API contracts. Use for endpoints, request/response schemas, versioning, pagination, error models, and backward compatibility.
---

# API contract design

## Workflow
1. Identify consumers, existing contract conventions, auth model, consistency requirements, and latency budget.
2. Specify operations and request/response schemas, required vs optional fields, types, defaults, and validation errors.
3. Define semantics: status codes, idempotency, pagination, sorting, filtering, retries, and timeout behavior.
4. Consider authorization for every operation, rate limits, sensitive field exposure, and backward compatibility.
5. Update OpenAPI/IDL and server-side validation consistently; avoid undocumented behavioral changes.
6. Add success, invalid-input, permission-denied, not-found, and compatibility tests.
7. Document contract examples and migration guidance if consumers must change.

## Principles
Follow repository conventions over generic REST dogma; avoid breaking existing clients silently; use stable machine-readable error codes where appropriate.
