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
7. Rehash protected inputs. Any modified or deleted baseline input, or newly introduced pytest
   configuration, is unsafe.
8. Run the fixed `python -m pytest -q` command in the clone with a user-bounded timeout.
9. Write `artifacts/runs/<run-id>/report.json` and return the same typed evidence through the API.

## Verdict policy

| Verdict | Meaning |
| --- | --- |
| `UNSAFE` | Invalid or no-op patch, protected-input modification, or failed baseline suite. |
| `INCONCLUSIVE` | Baseline passes, times out, cannot run, or no pytest adapter is available. |

No `VERIFIED` verdict exists in this phase. Existing tests can show a concrete regression, but cannot
prove that an agent met the task. Phase 4 will add independently generated, executable challenge tests.

## Security boundary

The clone protects the source checkout from patch application and test writes. It is not a complete
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
