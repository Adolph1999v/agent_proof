# Phase 2 Manual Case

Use this case to demonstrate a valid, behavior-neutral patch against a clean AgentProof checkout.

- Repository: the absolute path to this AgentProof repository
- Task: `Clarify the AgentProof description without changing behavior.`
- Candidate patch: copy the complete contents of `phase2-safe-readme.patch`
- Expected Phase 2 result: `INCONCLUSIVE`, with patch preflight and baseline execution passing

`INCONCLUSIVE` is intentional: this fixture tests only the deterministic stage. Passing the existing
suite is not independent proof that the task was completed. A separate Phase 3 model challenge is
required before AgentProof can return `VERIFIED`.

`phase2-safe-readme-base.md` is frozen fixture input, not current product documentation. Its wording
is intentionally kept unchanged so the pinned patch remains reproducible.
