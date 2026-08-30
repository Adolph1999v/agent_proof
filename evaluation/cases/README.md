# Phase 2 Manual Case

Use this case to demonstrate a valid, behavior-neutral patch against a clean AgentProof checkout.

- Repository: the absolute path to this AgentProof repository
- Task: `Clarify the AgentProof description without changing behavior.`
- Candidate patch: copy the complete contents of `phase2-safe-readme.patch`
- Expected Phase 2 result: `INCONCLUSIVE`, with patch preflight and baseline execution passing

`INCONCLUSIVE` is intentional: passing the existing suite is not independent proof that the task was
completed. Challenge-test generation belongs to a later phase.
