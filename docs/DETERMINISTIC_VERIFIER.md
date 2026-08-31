# Deterministic Verifier (Phase 2)

Phase 2 is deliberately narrow. It validates the integrity of a candidate patch and baseline test
evidence; it does not claim to prove semantic correctness.

## Supported inputs

- A clean, local Git working tree with a readable `HEAD` commit.
- A task description and a unified diff.
- An optional producing-agent trace, retained only as a SHA-256 digest in the report.
- Python repositories with pytest-discoverable tests or pytest configuration.

The source working tree must not have tracked changes. This makes the cloned input commit and report
reproducible.

## Deterministic flow

1. Resolve the user-approved Git root and record its `HEAD` commit.
2. Create `artifacts/runs/<run-id>/workspace` as an AgentProof-owned local clone.
3. Hash every existing protected input: test files, `conftest.py`, and pytest configuration.
4. Preserve the exact submitted patch. If a browser paste omitted its terminal newline, record that
   normalization and create a separate application copy before running `git apply --check`.
5. Apply the patch only to the clone.
6. Reject a patch that applies but leaves the clone unchanged; a no-op cannot support a verdict.
7. Rehash and report protected inputs, then exclude all candidate test and test-configuration changes
   from the executable application patch.
8. Apply the application-only patch to a second clean clone and run every frozen approved pytest
   modules with a fixed `python -m pytest -q` adapter and user-bounded timeout.
9. Preserve the raw candidate patch, quarantined application patch, command output, and final report in
   `artifacts/runs/<run-id>/`, then return the same typed evidence through the API.

## Verdict policy

| Verdict | Meaning |
| --- | --- |
| `UNSAFE` | Invalid or no-op application patch, or a failed frozen approved baseline test. |
| `INCONCLUSIVE` | The frozen approved tests pass, time out, cannot run, no pytest adapter is available, or no test/application evidence remains. |

Candidate-authored tests never contribute to a passing result. If a change includes application code
and test edits, AgentProof tests only the application code against every approved baseline module,
including the frozen original version of a modified or deleted test. If it contains only
test/configuration edits, there is insufficient deterministic application evidence and the result is
`INCONCLUSIVE`.

No `VERIFIED` verdict exists in the deterministic stage alone. Existing tests can show a concrete
regression, but cannot prove that an agent met the task. Phase 3 adds independently generated,
deterministically executed challenge tests before a result can become `VERIFIED`.

## Security boundary

The disposable clones protect the source checkout from patch application and test writes. They are not a complete
operating-system sandbox: repository tests are executable local code. AgentProof therefore accepts
only user-approved local repositories, uses no shell interpolation, limits execution time, disables
interactive Git prompts, and documents the portable local mode in every report. Stronger process,
filesystem, and network isolation belong behind a later platform adapter.

## Evidence fields

Each report records the source commit; SHA-256 digests of the task, patch, and optional trace; protected
snapshot digests before and after application; changed-file statistics; patch and test command results;
the deterministic verdict; and the relative evidence path.

The maintained manual case in `evaluation/cases/` contains a complete Git-generated patch and its
expected Phase 2 result. Using the entire patch matters: deleting its added and removed lines turns it
into a no-op, while omitting surrounding context can make a handwritten patch inapplicable.
