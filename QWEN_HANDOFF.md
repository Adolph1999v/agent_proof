# Qwen Handoff — Phase 3 Reliability

## Objective

Bound local-model challenge generation so Qwen produces one concise JSON test proposal within a
demo-safe request budget. Qwen's OpenCode session returned only repository summaries; Codex applied
and reviewed the scoped implementation described below.

## Files Changed

- `backend/agentproof/provider.py` — reduced the completion budget and added explicit timeout errors.
- `backend/agentproof/challenges.py` — added direct-output prompting, deterministic relevance
  ordering, and hard task/file/patch/source/prompt limits.
- `backend/agentproof/models.py` — reduced the default model timeout to two minutes.
- `backend/tests/test_challenges.py` — added regression coverage for every new reliability boundary.
- `IMPROVEMENT_CHANGELOG.md` — connected the observed empty-response failure to this bounded design.
- `QWEN_HANDOFF.md` — replaced the stale directory-picker handoff with this report.

## Reliability Bounds

- Changed Python application files: 4 maximum
- Task text: 2,000 characters
- Patch context: 8,000 characters total; 3,000 per file
- Source context: 4,000 characters total; 2,000 per file
- Changed-file index: 1,500 characters
- Final user prompt: 18,000 characters
- Model output: 1,536 tokens
- Default model timeout: 120 seconds
- Requested JSON target: approximately 900 generated tokens

## Trust Boundaries Preserved

- The model proposes a test but never chooses the verdict.
- Generated tests still pass strict JSON, Pydantic, and AST safety validation.
- Baseline and candidate challenges still run separately in disposable workspaces.
- Candidate-authored tests and configuration remain quarantined.
- Failed model requests and responses remain trajectory evidence.
- Model endpoints remain restricted to loopback HTTP.
- The process still admits only one local-model request at a time.
- Generated tests retain the existing network, subprocess, filesystem, and dynamic-execution blocks.

## Tests Added or Updated

- Provider request preserves strict JSON schema, temperature 0, seed 42, and uses 1,536 tokens.
- Challenge instructions start with `/no_think`.
- Tasks and final prompts are hard-bounded.
- At most four deterministic, task-relevant Python application files enter model context.
- Test, protected, and non-Python inputs remain excluded.
- The default request timeout is 120 seconds.
- Timeout errors name the configured deadline and release the single-model lock.
- Existing verdict, safety, task-binding, and failed-trajectory tests remain passing.

## Commands Run

| Command | Exit status | Result |
| --- | ---: | --- |
| `.venv/bin/python -m pytest backend/tests/test_challenges.py backend/tests/test_phase3_api.py` | 0 | 13 passed |
| `make test-backend` | 0 | 65 passed |
| `make lint-backend` | 0 | Ruff passed |
| `make check` | 0 | 65 backend tests, 13 frontend tests, Python/TypeScript lint, and production build passed |
| `git diff --check` | 0 | No whitespace errors |
| `git status --short` | 0 | Six intended files modified before commit |

## Remaining Manual Test

Run one Qwen3.6 27B Q6 challenge through LM Studio and record wall-clock time, prompt tokens,
completion tokens, response validity, baseline/candidate execution, and final deterministic verdict.
Do not claim a live speed improvement until this replay succeeds.

## Known Limitations

- Phase 3 currently challenges changed Python application files only.
- The relevance selector uses deterministic task-to-path matching rather than repository-wide search.
- Large multi-language repositories and richer dependency-aware retrieval remain future work.
