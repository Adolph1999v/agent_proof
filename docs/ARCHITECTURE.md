# Architecture

## Product boundary

AgentProof receives a task description, a candidate patch, an approved repository, and optionally the producing agent's trace. It returns evidence for a human merge decision. It does not merge branches or modify the user's source repository directly.

## Planned workflow

```text
Task + repository + patch + trace
                 |
                 v
        Deterministic intake
     hashes, diff, test snapshot
                 |
                 v
       Deterministic verifier (Phase 2)
  patch preflight + immutable snapshots
                 |
                 v
       Disposable test workspace
 original tests + fixed pytest baseline
                 |
                 v
       Evidence-backed verdict
       UNSAFE / INCONCLUSIVE
                 |
                 v
             Human review
```

## Components

- **React + Vite:** local interface for selecting inputs, following progress, and reviewing evidence.
- **FastAPI:** typed local API and workflow orchestration.
- **Deterministic verifier:** owns hashing, diff inspection, immutable-test comparison, process limits, and verdict rules. It currently clones a clean user-approved Git repository and runs the fixed pytest adapter only.
- **Model adapter:** will support local Ollama or another OpenAI-compatible endpoint. Model output is always untrusted.
- **Disposable workspace:** isolates patch application and repository commands from the original checkout.
- **Trajectory recorder:** stores prompts, tool calls, responses, retries, decisions, and evidence references.

## Trust rules

1. Candidate patches may not modify the external verification harness.
2. Existing tests are snapshotted before a candidate patch is applied.
3. Generated tests must compile and fail for the expected reason before they count as evidence in a later phase.
4. A model cannot directly produce a `VERIFIED` verdict.
5. Timeouts, allowed commands, and workspace boundaries are deterministic.
6. The user must approve consequential actions.

## Phase 2 scope limit

Passing the preserved baseline suite yields `INCONCLUSIVE`, not `VERIFIED`. It is evidence that the
candidate patch did not visibly break existing checks, not proof that it achieved the task. This deliberate
gap is what later invariant extraction and adversarial tests must close.

## Cross-platform decision

The product is a local web application because a browser interface is consistent across operating systems. Platform-specific process isolation will remain behind a backend adapter so the evaluation can use a documented portable mode while stronger sandbox integrations can be added later.
