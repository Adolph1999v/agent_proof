# AgentProof Product Capabilities

This page lists what the submitted version can do. Future ideas are kept in a separate file so they
are not presented as completed features.

## Intake and project selection

- Select a local project with a mouse-driven folder picker or manual path fallback.
- Enter the original coding task in natural language; no hand-written Git diff is required.
- Discover added, modified, deleted, and renamed files against the correct approved baseline.
- Show a read-only Before/After view using the approved baseline and the current project. Added,
  changed, deleted, and renamed text files are supported; binary contents are not shown.
- Retain an explicit-patch API for deterministic fixtures and advanced reproduction.

## Project identity and baseline isolation

- Assign each project a stable identity rather than using its path as identity.
- Recognize Git and non-Git projects after their folder moves.
- Keep baselines, manifests, findings, and reports isolated per project.
- Reject copied identities, incompatible Git lineages, cross-project manifest tampering, corrupted
  objects, stale approvals, and ambiguous identity collisions.
- Store immutable, content-addressed baselines with parent history and human approval.
- Report when the current project exactly matches its latest approved baseline.
- Audit current tests when no earlier baseline exists without pretending that historical comparison
  occurred.

## Deterministic verification

- Create AgentProof-owned disposable Git clones; never patch or test the selected source folder.
- Preflight the candidate patch and reject invalid or no-op changes.
- Freeze approved pytest tests, `conftest.py`, and pytest configuration before applying the candidate.
- Quarantine candidate-added, modified, deleted, or reconfigured test evidence.
- Apply only the application change while replaying every frozen approved test.
- Run bounded pytest commands with fixed environment controls, timeouts, and captured output.
- Return `UNSAFE` immediately for concrete integrity violations or failing preserved evidence.
- Return `INCONCLUSIVE` when available evidence cannot justify a safe/correct claim.

## Independent local-model challenge

- Connect only to plain-HTTP model endpoints on `127.0.0.1`, `localhost`, or `::1`.
- Auto-select the sole loaded generation model while excluding embedding/reranking models.
- Admit only one local-model request at a time to protect memory-bound machines.
- Bound the task, changed-file count, patch, source excerpts, prompt, output tokens, and timeout.
- Ask the model for one JSON-schema-constrained Python/pytest challenge.
- Require an application import plus a non-trivial assertion or `pytest.raises` check.
- Reject generated tests that use blocked filesystem, network, subprocess, dynamic execution,
  randomness, sleep, skip, or xfail capabilities.
- Run the generated challenge independently on baseline and candidate workspaces.
- Perform at most two evidence-guided repairs after the first proposal, aggregating all token/time
  cost and preserving every attempt.
- Derive explicit behavior-preservation intent from refactor tasks rather than trusting a model label.
- Keep the model outside the verdict: executed baseline/candidate outcomes decide the result.

## Evidence and user control

- Store local JSON reports with input digests, changed files, protected inputs, commands, exit codes,
  durations, output previews, model identity, token usage, generated invariants, and evidence paths.
- Preserve successful, malformed, timed-out, safety-rejected, and repaired model trajectories.
- Keep project content and model inference local; no API key or paid service is required.
- Require a human to approve a baseline; verification itself does not mutate the source project.
- Show honest result language: `VERIFIED`, `UNSAFE`, `INCONCLUSIVE`, or current checks only.

## Reproducibility and measured behavior

- Install Python only in `.venv` through `uv`; frontend packages stay in `frontend/node_modules`.
- Provide one-command setup, development, lint, test, build, smoke, and evaluation workflows.
- Run through Make on the tested macOS setup. Linux and Windows commands are documented but were not
  manually tested for this submission.
- Recreate eleven dependency-free evaluation repositories from pinned JSON inputs.
- Compare a normal green-test baseline and AgentProof under the same patch/test budget.
- Commit the exact recorded result and public-case provenance.

## Future plans

Planned work is listed in [FUTURE_PLANS.md](FUTURE_PLANS.md). It is kept separate so reviewers can
clearly tell the difference between current features and future ideas.
