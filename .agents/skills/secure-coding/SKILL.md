---
name: secure-coding
description: Implement or assess secure application code and trust boundaries. Use for authentication, authorization, untrusted input, secrets, APIs, file handling, or explicit security reviews.
---

# Secure coding

## Workflow
1. Identify assets, attackers, trust boundaries, inputs, privileged operations, and sensitive data.
2. Review authorization on each resource and action; distinguish authentication from authorization.
3. Validate and constrain untrusted input. Use parameterized SQL, safe shell/HTML handling, and path traversal defenses.
4. Apply least privilege, safe defaults, rate limits where justified, and protective timeouts for network calls.
5. Keep credentials out of source, logs, errors, and test fixtures. Follow the project's secret-management strategy.
6. Review dependencies, deserialization, file uploads, SSRF, injection, and cryptographic usage for applicable threats.
7. Add negative security tests; run available SAST/dependency scans without blindly trusting scan outputs.
8. Report findings with threat scenario, severity, remediation, and verification evidence.

## References
Use OWASP Top 10 and ASVS as guidance; do not label a change 'OWASP compliant' based on this checklist alone.

## Guardrails
Do not introduce custom cryptography, security bypasses, or broad permissions for convenience.
