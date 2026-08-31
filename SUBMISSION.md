# AgentProof — Submission Brief

## One sentence

AgentProof independently challenges an AI-generated Python change in a disposable local workspace so
“the agent says it is done” becomes inspectable baseline/candidate evidence.

## User and problem

The initial user is a developer reviewing code produced by Codex, Claude Code, OpenCode, or another
coding agent. Existing tests may pass even when the patch removes behavior, weakens/deletes a test, or
changes pytest configuration. Asking the same agent to review itself does not create independent
evidence.

**Practical insight:** a green suite is not an independent judge when the candidate patch is allowed
to edit the suite.

## Workflow

1. The user selects a local project and states the original task in plain language.
2. AgentProof identifies the correct project-specific approved baseline and discovers changes.
3. It creates disposable baseline and candidate clones; the source folder is not patched.
4. Existing tests/configuration are frozen. Candidate edits to those inputs are quarantined.
5. Deterministic checks run. If they are not decisive, a local model proposes one bounded challenge.
6. The challenge is statically validated and run separately on baseline and candidate.
7. Deterministic rules return `VERIFIED`, `UNSAFE`, or `INCONCLUSIVE`; a human reviews the evidence.

## Measured comparison

| Metric | Green-test baseline | AgentProof |
| --- | ---: | ---: |
| Overall accuracy (11 cases) | 63.6% | **100%** |
| Unsafe-patch detection (5 cases) | 20% | **100%** |
| Correct-patch acceptance (6 cases) | 100% | **100%** |

The run used local `qwen2.5-coder:7b`, 9,467 prompt tokens, 1,600 completion tokens, and 32.9 seconds
total on the submission machine. API cost was $0. Exact inputs and output are committed under
`evaluation/`.

## Strongest engineering improvement

The first full run scored only 70%. Preserved failures showed that the model could emit malformed
tests, wrong literals, or an incorrect change/preservation label. AgentProof now performs at most two
evidence-guided repairs after the first attempt, aggregates their cost, validates application imports
and exception assertions, and derives explicit behavior-preservation intent from the user task. The
verifier contains no benchmark case IDs.

## Removed/deferred experiment

Qwen3.6 27B Q6 was initially selected for the demo. The tested LM Studio runtime ignored non-thinking
controls and spent its bounded output on private reasoning, making the workflow too slow and
unreliable for a five-minute demonstration. The failure trace is retained; the submission defaults to
Qwen2.5-Coder 7B. A larger three-model bake-off is post-hackathon work.

## Reproduce

```bash
make setup
make check
ollama pull qwen2.5-coder:7b
# Ensure the Ollama server is running, then:
make phase3-smoke
make evaluate
```

Expected evaluation headline: baseline `63.6`, AgentProof `100.0`, unsafe detection `20.0` versus
`100.0`. Detailed environment, Windows commands, runtime, and limitations are in
`docs/REPRODUCTION.md`.

## Evidence map

- Complete capabilities and boundaries: `PRODUCT_CAPABILITIES.md`
- Planned improvements: `FUTURE_PLANS.md`
- Evidence-backed iterations: `IMPROVEMENT_CHANGELOG.md`
- Evaluation design and result: `docs/EVALUATION.md`
- Exact reproduction: `docs/REPRODUCTION.md`
- Public-case provenance: `evaluation/PUBLIC_CASES.md`
- Machine-readable result: `evaluation/results/recorded-evaluation.json`
- Representative development/runtime trajectories: `traces/`
- Video plan and submission checklist: `VIDEO_SCRIPT.md`

## Honest limitations

- Independent generated challenges currently support Python application changes and pytest.
- Eleven cases are scoped evidence, not proof across every repository.
- Isolation is application-level disposable cloning and bounded execution, not a hardened VM.
- The public-derived case reproduces reported behavior without copying the upstream repository.
