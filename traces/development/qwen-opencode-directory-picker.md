# Representative development trajectory — Qwen 3.6 through OpenCode

This excerpt records the bounded task delegated to the local Qwen model and the subsequent human/Codex
review. It does not imply Qwen built AgentProof end to end.

## Instruction

Implement only a read-only localhost backend endpoint for browsing directories for a future folder
picker. Requirements included: optional path defaulting to home, `~` resolution, absolute normalized
paths, validation, immediate readable child directories only, case-insensitive sorting, silent skip of
unreadable children, pathlib/direct Python filesystem APIs, focused tests, no frontend/dependency/
existing-test changes, and a root handoff report.

## Qwen/OpenCode actions reported

- Added directory request/response models and a FastAPI endpoint.
- Added focused tests for home, sorting, file exclusion, parent paths, invalid inputs, unreadable
  children, and child resolution failures.
- Corrected an initially missing import plus Ruff issues.
- Reported 60 backend tests and 7 frontend tests passing at that checkpoint.
- Wrote `QWEN_HANDOFF.md`.

## Review and feedback

- Human observation: no frontend change was visible. This was expected because the strict task was
  backend-only; the report had not made that distinction clear enough.
- Codex review: verified the endpoint and tests, found the handoff had stale claims, required a
  correction, and retained the child-resolution regression.
- Follow-up implementation: connected a browser-based directory picker, then simplified it after the
  human found a raw home-directory list too technical. Hidden directories were removed from the
  default view, navigation gained a one-step back action, and manual path entry remained a fallback.

## Outcome

The local Qwen model contributed one bounded backend component. Codex and the human reviewed its
scope, corrected documentation, integrated the frontend separately, and ran the complete quality
gate. This trace demonstrates supervised delegation rather than an unreviewed model handoff.

