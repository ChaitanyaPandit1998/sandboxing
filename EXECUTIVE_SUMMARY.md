# Executive summary: gVisor sandbox POC

## Outcome

The POC demonstrated that gVisor (`runsc`) can run the same bounded workloads as Docker's standard `runc` runtime in our ARM64 Lima test environment. Both runtimes passed the selected isolation and network-policy checks, and the test harness detected each deliberately weakened configuration. This is a positive feasibility result and supports moving to a focused security-validation phase.

## Evidence

- Both runtimes passed **25 selected isolation and privilege checks** and **5 HTTPS allowlist checks**.
- The negative controls detected **all 10 weakened cases** across both runtimes, including root execution, added capability, writable root filesystem, a synthetic host bind mount, and direct network egress.
- In a **20-trial benchmark on one VM**, `runsc` median workload time was **7.7% to 28.2% higher** than `runc`; end-to-end container time was **22.2% to 25.7% higher**.
- A small syscall matrix showed runtime-dependent behavior, but does not identify every enforcement layer.

## Recommendation

Proceed with the **P0 security-validation tests** in [SECURITY_VALIDATION_PLAN.md](SECURITY_VALIDATION_PLAN.md): expand filesystem and process-boundary tests, probe egress-policy bypasses, add launch-policy negative controls, and broaden focused privilege and syscall coverage. Run these only in the disposable Lima VM with synthetic data. Then repeat performance measurements across multiple VM boots and representative workloads.

**Decision boundary:** The POC supports continued evaluation; it does not yet support a production security claim or prove that `runsc` is more secure than `runc`. The security-validation plan is proposed work and has not been executed.

Detailed methodology and results are in [REPORT.md](REPORT.md); the full project overview is in [POC_SUMMARY.md](POC_SUMMARY.md).
