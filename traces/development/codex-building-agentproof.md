# Representative development trajectory — Codex

This is a selected, chronological trace of decisions that materially changed AgentProof. It is not a
transcript of the full private conversation. No credentials or private repository contents are
included.

## 1. Problem selection

- Human instruction: choose a hackathon problem that is useful, independently testable, reproducible
  on a judge's machine, and feasible in the remaining time; do not agree merely to be agreeable.
- Candidate ideas reviewed: CV ranking, local coding UI, API migration, environment repair, database
  rollback, merge verification, accessibility repair, and independent patch verification.
- Decision: build AgentProof because a judge can reproduce a known-safe or known-unsafe patch and
  measure a deterministic outcome. Retain ContractFix as a separate portfolio project.

## 2. Deterministic verifier before model integration

- Human checkpoint: manual unified diffs were too technical and a user might have no usable Git
  history.
- Actions: added project-path discovery, project-specific immutable baselines, moved-project identity,
  automatic change detection, current-state audits, and human baseline approval.
- Failure observed: a README fixture read candidate-modified working content while constructing its
  supposed baseline.
- Correction: pin the fixture's exact base content beside its patch; add post-commit regression coverage.
- Result: passing tests alone remained `INCONCLUSIVE`, while protected-test failure and no-op changes
  returned `UNSAFE`.

## 3. Local model integration and failed large-model experiment

- Human constraint: 48 GB Mac, one model at a time, models stored outside the repository, no paid API.
- Actions: localhost-only OpenAI-compatible adapter, process-wide request lock, strict JSON schema,
  bounded repository context, static AST safety checks, separate baseline/candidate execution.
- Failed experiment: Qwen3.6 27B Q6 in the tested LM Studio runtime consumed its completion budget as
  reasoning despite non-thinking controls and returned no challenge JSON.
- Evidence: `traces/runtime/phase3-full-project-context-limit.json` and
  `traces/runtime/phase3-qwen36-smoke.json`.
- Decision: use local `qwen2.5-coder:7b` through Ollama for the reproducible demo; keep the failed
  experiment visible.

## 4. Measured evaluation and repair loop

- Initial command: `make evaluate` on five correct and five unsafe controlled patches.
- Initial result: baseline 60%; AgentProof 70%.
- Preserved failures: long/malformed JSON, missing application imports, incorrect expected literals,
  and change/preservation labels that contradicted explicit refactor intent.
- General corrections (no case IDs in verifier): concise challenge contract, explicit module hints,
  import validation, `pytest.raises` support, task-derived preservation mode, and at most two
  evidence-guided repairs after the first attempt. Token/time cost is aggregated; all attempts remain
  in the trajectory.
- Regression command: `make check`.
- Result at final rehearsal: 77 backend tests, 13 frontend tests, lint, type checking, and production
  build passed.

## 5. Final evidence

- Added a public-bug-derived dateutil empty-input reproduction with explicit provenance.
- Final command: `make evaluate`.
- Final result: 11/11 correct; baseline 63.6%, AgentProof 100%; unsafe detection 20% versus 100%;
  correct-patch acceptance 100%; 32,938 ms; local API cost $0.
- Machine-readable evidence: `evaluation/results/recorded-evaluation.json`.
- Human control retained: AgentProof reports evidence; it does not silently apply or approve source
  changes.
