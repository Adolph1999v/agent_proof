# Evaluation Plan

## Evaluation principles

- Use authentic, publicly verifiable patches and outcomes for headline evidence.
- Pin repository commits, issue text, patches, tests, model identifiers, quantization, prompts, and tool versions.
- Give the baseline and AgentProof the same task, repository, patch, model, context limit, and execution budget.
- Preserve all results, including failures and inconclusive runs.
- Keep the final verdict deterministic and outside the model.

## Primary workflow metric

The primary metric is **unsafe-patch detection rate**: the percentage of known-unsafe agent patches that AgentProof blocks with executable evidence.

Guardrail metrics include the false-block rate on known-correct patches, generated-test execution rate, wall-clock time, token usage, peak memory, and retry count.

## Model selection rubric

Qwen3.6 27B Q6, Qwen3-Coder 30B, and Qwen2.5-Coder 7B will receive identical real patches, prompts, context limits, output limits, and deterministic settings. Each model artifact and quantization will be identified exactly.

| Category | Weight |
| --- | ---: |
| Correctly catches unsafe patches | 40% |
| Does not block correct patches | 20% |
| Produces relevant, executable tests | 20% |
| Execution time | 10% |
| Tokens and memory usage | 10% |
| **Total** | **100%** |

Correctness is a gate, not merely an average: a serious false-safe result cannot be compensated for by faster execution. The selected model will maximize verified task performance rather than external benchmark reputation.

## Initial model bake-off

The Phase 3 kill test will include at least:

1. A real unsafe patch that changes or weakens an existing test.
2. A real unsafe patch with a semantic defect missed by the visible test suite.
3. A real correct patch that should not be blocked.
4. One difficult case involving state, timing, or a multi-file invariant if it can run deterministically.

Every run will record:

- Exact model identifier, artifact digest, quantization, and runtime version.
- Input prompt, repository commit, issue or task text, and patch digest.
- Generated invariants and tests.
- Test compilation and execution results.
- Input, reasoning, and output tokens when exposed by the runtime.
- Wall-clock time, retry count, and peak memory where available.
- Final deterministic verdict and supporting evidence identifiers.

## Baseline

The Phase 2 baseline will run the repository's existing tests and a simple general-purpose model review without AgentProof's frozen-test comparison, external adversarial tests, or claim-to-evidence validation. Its exact definition will be frozen before final evaluation.
