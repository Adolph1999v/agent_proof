# From Basic Check to AgentProof

This page shows what the simple baseline could do, what AgentProof added, and what improved in the
recorded evaluation.

## Basic baseline

The basic version followed a common review method:

1. Apply the code change.
2. Run the project's tests.
3. Accept the change when the tests are green.

This is useful, but the change can also edit or delete the tests that judge it. On our 11 fixed cases,
this baseline scored **63.6%** and found **1 of 5** unsafe changes.

## Improved AgentProof

AgentProof adds an independent review around the normal tests:

- The user selects a project and describes the original task in plain language.
- Each project keeps its own approved baseline, even if its folder moves.
- A Before/After view shows the detected code changes.
- Approved tests and pytest settings are frozen. Candidate edits to them are not trusted.
- Checks run in disposable copies, not in the user's source folder.
- When normal tests are not enough, a local model proposes one extra challenge.
- AgentProof validates and runs that challenge on both the old and new versions.
- Executed results—not the model's words—decide `VERIFIED`, `UNSAFE`, or `INCONCLUSIVE`.
- A human reviews the evidence and decides whether to approve the next baseline.

## Measured improvement

Both methods received the same 11 repositories, tasks, changes, and normal test command.

| Result | Basic baseline | AgentProof |
| --- | ---: | ---: |
| Overall accuracy | 63.6% (7/11) | **100% (11/11)** |
| Unsafe changes found | 20% (1/5) | **100% (5/5)** |
| Correct changes accepted | 100% (6/6) | **100% (6/6)** |

The final run used local `qwen2.5-coder:7b` and took 32.9 seconds on the submission Mac. Eleven cases
are useful hackathon evidence, not proof that every future repository will get a perfect result.

## Main lesson

A green test suite is not an independent judge when the code change can edit the judge. Preserving the
old evidence and adding a separate challenge made the unsafe cases visible without blocking the
correct cases in this evaluation.

Exact cases and results are in [evaluation/](../evaluation/). The full experiment history is in
[IMPROVEMENT_CHANGELOG.md](IMPROVEMENT_CHANGELOG.md).
