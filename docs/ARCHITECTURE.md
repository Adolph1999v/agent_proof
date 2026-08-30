# Architecture

## Product boundary

AgentProof normally receives a project path, a natural-language task, and optionally the producing
agent's trace. It identifies the project, discovers changes against that project's approved baseline,
and returns evidence for a human decision. An explicit patch remains available as an advanced input.
AgentProof does not merge branches or modify the user's source files during verification.

## Planned workflow

```text
Task + project path + optional trace
                 |
                 v
       Project identity registry
  stable ID + isolated history lookup
                 |
                 v
       Baseline-relative intake
  automatic changes + immutable snapshot
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
      Local model challenge (Phase 3)
 untrusted invariants + generated pytest
                 |
                 v
   Baseline / candidate challenge replay
       deterministic evidence rules
                 |
                 v
       Evidence-backed verdict
  UNSAFE / INCONCLUSIVE / VERIFIED
                 |
                 v
             Human review
```

## Components

- **React + Vite:** local interface for selecting inputs, following progress, and reviewing evidence.
- **FastAPI:** typed local API and workflow orchestration.
- **Deterministic verifier:** owns hashing, diff inspection, immutable-test comparison, process limits, and verdict rules. It currently clones a clean user-approved Git repository and runs the fixed pytest adapter only.
- **Project store:** owns stable identities, known paths, content-addressed snapshot objects, immutable
  baseline manifests, parent history, and cross-project isolation.
- **Current-state auditor:** runs the supported baseline checks in a disposable copy when no older
  baseline exists. A passing audit is never described as change verification.
- **Automatic change adapter:** turns a baseline-to-current comparison into an exact internal Git
  patch without asking the user to write one.
- **Model adapter:** calls only a localhost LM Studio or Ollama OpenAI-compatible endpoint, uses
  deterministic settings, and admits one request at a time. Model output is always untrusted.
- **Challenge runner:** validates the structured model response, rejects dangerous or trivial generated
  tests, then executes the accepted test separately on baseline and candidate workspaces.
- **Disposable workspace:** isolates patch application and repository commands from the original checkout.
- **Trajectory recorder:** stores prompts, tool calls, responses, retries, decisions, and evidence references.

## Trust rules

1. Candidate patches may not modify the external verification harness.
2. Existing tests are snapshotted before a candidate patch is applied.
3. Generated tests must compile and fail for the expected reason before they count as evidence in a later phase.
4. A model cannot directly produce a `VERIFIED` verdict.
5. Timeouts, allowed commands, and workspace boundaries are deterministic.
6. The user must approve consequential actions.
7. Every baseline and automatic report must match the active stable repository identity.
8. Baseline approval must match the exact digest that the human inspected.

## Phase 2 scope limit

Passing the preserved baseline suite yields `INCONCLUSIVE`, not `VERIFIED`. It is evidence that the
candidate patch did not visibly break existing checks, not proof that it achieved the task. This deliberate
gap is what later invariant extraction and adversarial tests must close.

## Phase 2.5 identity and baseline boundary

Each Git project receives private identity metadata inside its Git directory; non-Git folders receive
an excluded `.agentproof` identity marker. Baselines are stored outside the target project under an
identity-specific directory. A moved project retains its identity, while an unrelated project at the
same path receives a different identity. A duplicated live identity is rejected rather than merging
histories implicitly. Git baselines must also belong to the current commit lineage; incompatible branch
histories fail closed instead of being compared automatically.

## Phase 3 model boundary

The model receives the natural-language task plus a size-ranked, bounded view of changed Python
application files. Per-file and total budgets prevent a large repository from consuming the model's
entire context window. Documentation, frontend files, existing tests, and candidate-added tests are
excluded from the current pytest adapter so the model cannot merely copy candidate-controlled
evidence. The model returns invariants, a `change` or `preserve` expectation, and one pytest module
under a strict JSON schema.

Every attempt receives an evidence directory before inference begins. Rejected, malformed,
length-limited, and successful responses preserve the exact bounded prompt, model response, finish
reason, usage, and validation outcome in `trajectory.json`. A failed model request never becomes an
execution verdict.

AgentProof statically rejects generated tests that use network, subprocess, dynamic execution,
filesystem mutation, monkeypatching, skip/xfail, or constant assertions. It then runs the accepted test
in two fresh clones: approved baseline and candidate. `VERIFIED` requires the execution pattern promised
by the proposal; `UNSAFE` requires a concrete candidate regression; ambiguous patterns remain
`INCONCLUSIVE`. Static validation is not a complete operating-system sandbox, so production use still
requires the planned container-level executor.

## Cross-platform decision

The product is a local web application because a browser interface is consistent across operating systems. Platform-specific process isolation will remain behind a backend adapter so the evaluation can use a documented portable mode while stronger sandbox integrations can be added later.
