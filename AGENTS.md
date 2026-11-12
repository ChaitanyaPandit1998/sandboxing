# Development log maintenance

For each meaningful implementation, documentation, or validation batch, update the root `DEVLOG.md` with the change, checks actually run, relevant failures/limitations, evidence links, and next step.

Use actual ISO 8601 timestamps in Asia/Kolkata (`+05:30`). Distinguish commit timestamps from test execution times; mark historical entries date-only when exact execution times are unavailable. Keep uncommitted/pushed status accurate and never include credentials, login codes, private keys, auth files, or private prompts.

Preserve existing historical entries; add corrections or follow-ups when evidence changes. A batch's own log update does not require a separate recursive log entry.
