# AgentProof Product Capabilities

This document defines the complete AgentProof product contract. It describes what the product does,
independent of release sequencing. The README states the currently runnable scope, and the Improvement
Changelog links implemented behavior to evidence.

## Simple verification intake

- Accept a project folder and a natural-language description of the requested change.
- Discover relevant changes automatically without requiring a user to understand unified diffs.
- Accept an optional coding-agent trace, commit, branch comparison, or explicit patch when available.
- Show the detected files and change summary before verification begins.
- Preserve an advanced explicit-patch mode for expert and reproducibility workflows.

## Project recognition and isolation

- Assign every project a stable identity that is independent of its current filesystem path.
- Recognize a previously analysed project after its folder moves or is renamed.
- Maintain separate baselines, snapshots, findings, traces, and reports for every project.
- Restore the correct project history when a user switches between any number of projects.
- Reject cross-project baseline comparisons and ambiguous identity collisions.
- Distinguish a moved project from an unrelated project created later at the same path.
- Ask for confirmation before linking a copied or cloned workspace to existing history.

## Baselines and version history

- Capture the current project as a first approved baseline when no earlier version exists.
- Report current test health honestly when comparison with an older version is impossible.
- Make an approved result the parent baseline for the next verification.
- Retain older immutable baselines rather than replacing them.
- Compare any current state with its correct approved baseline.
- Record file hashes, task context, environment details, test evidence, timestamps, and human approval.
- Detect baseline corruption or tampering before using it as evidence.
- Preview, restore, or export an older version without silently overwriting current work.

## Change discovery

- Select a local project through a mouse-driven directory browser or enter its path manually.
- Detect modified, added, deleted, renamed, and binary files.
- Discover staged, unstaged, committed, and snapshot-relative changes.
- Compare non-Git projects using AgentProof-owned before-and-after snapshots.
- Reject empty or no-op changes.
- Detect when the source changes between inspection, verification, and approval.
- Present human-readable summaries while retaining exact machine-readable changes as evidence.

## Independent verification

- Apply candidate changes only inside a disposable workspace.
- Preserve existing tests and test configuration as protected baseline evidence.
- Quarantine changes that weaken, delete, add, or reconfigure candidate-controlled checks; execute the
  application-only patch against the untouched approved versions instead.
- Run bounded baseline tests, builds, linters, and supported static checks.
- Extract requirements and invariants from the task, repository, and optional agent trace.
- Generate independent challenge tests outside the candidate change's control.
- Require generated tests to compile and demonstrate the intended failure before they count.
- Retry bounded verification steps without allowing a model to declare its own work correct.
- Return `UNSAFE`, `INCONCLUSIVE`, or `VERIFIED` only from deterministic evidence rules.
- Explain which requirement failed, which command demonstrated it, and how to reproduce the result.

## Current-state audit

- Audit a project even when no earlier version or Git history exists.
- Report which available tests and checks pass in the current state.
- Clearly separate “current checks pass” from “the change was verified against a baseline.”
- Allow a human to approve the audited state as the first baseline.
- Refuse to invent or reconstruct historical evidence that is unavailable.

## Evidence and traceability

- Record the exact source identity, baseline, task, change digest, model configuration, and commands.
- Store command output, durations, exit codes, retries, resource measurements, and final decisions.
- Preserve both successful and failed trajectories.
- Produce local, inspectable reports that another person can reproduce.
- Link every verdict to the baseline and repository identity that produced it.
- Export reviewer-friendly evidence without requiring the entire development conversation.

## Model evaluation

- Run candidate models against identical repositories, tasks, patches, prompts, limits, and settings.
- Serialize model execution so large local models are never benchmarked concurrently on memory-bound
  machines.
- Score unsafe-patch detection, correct-patch acceptance, executable-test quality, speed, tokens, and memory.
- Treat serious false-safe results as a correctness failure rather than averaging them away.
- Support local model runtimes and compatible local endpoints without requiring a paid API.
- Keep model suggestions untrusted until deterministic execution confirms them.

## Human control and recovery

- Require human approval before creating a baseline, applying a generated change, restoring, or exporting.
- Show the evidence and affected files before consequential actions.
- Keep the source project unchanged during verification.
- Restore an older baseline into a separate folder by default.
- Support explicit in-place rollback only after warning about unrecorded work.
- Export a change set so an approved change can be reapplied later.

## Local-first safety and privacy

- Keep repositories, snapshots, models, traces, and reports on the user's machine by default.
- Never send project contents to an external service without explicit approval.
- Exclude dependency folders, build output, caches, and configured sensitive files from snapshots.
- Use bounded commands without shell interpolation.
- Disable interactive Git prompts and record execution timeouts.
- Fail closed when repository identity, baseline integrity, or execution evidence is uncertain.

## Reproducibility and portability

- Run through a local browser interface on macOS, Linux, and Windows.
- Use isolated project dependencies and documented one-command quality gates.
- Record exact tool, model, prompt, baseline, and environment identifiers.
- Provide clean-environment reproduction instructions and deterministic fixtures.
- Keep platform-specific sandboxing behind replaceable execution adapters.

## Honest result language

- `UNSAFE`: executable evidence demonstrates a concrete failure or an integrity rule was violated.
- `INCONCLUSIVE`: available evidence cannot justify either safety or correctness.
- `VERIFIED`: preserved baseline evidence and independent challenges support the requested behavior.
- “Current checks pass”: the present project is healthy under available checks, but no historical comparison
  was possible.
