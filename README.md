# AgentProof

AgentProof checks AI-generated Python changes before a person approves them.

A coding agent may say a task is finished even when it removed a useful test, hid a failing test, or
missed an edge case. AgentProof keeps the approved tests, runs the change in disposable copies, and
can ask a local model to create one extra challenge. The model proposes the challenge; executed test
results decide the verdict.

AgentProof is a local web application. The selected project and model requests stay on the user's
computer. No paid model service or API key is required.

## Current workflow

1. Choose a project folder and describe the original coding task.
2. Inspect the project. The first inspected state can become a human-approved baseline.
3. After the project changes, inspect it again. AgentProof compares it with that project's latest
   approved baseline and shows a read-only, line-highlighted Before/After view in the page.
4. Run the preserved approved tests in a disposable copy. Candidate changes to tests and pytest
   settings are not trusted.
5. If existing evidence is not enough, run a local-model challenge against both the baseline and the
   changed version.
6. Review the verdict and saved evidence. Only a human can approve the next baseline.

### Verdicts

- `UNSAFE`: AgentProof found a concrete problem, such as an invalid/no-op change or a failed approved
  test.
- `INCONCLUSIVE`: the available checks did not prove the change correct or unsafe.
- `VERIFIED`: preserved tests passed and an independent challenge produced the required
  baseline-versus-candidate result.

See [PRODUCT_CAPABILITIES.md](PRODUCT_CAPABILITIES.md) for the complete current feature list.

## Measured result

The pinned evaluation contains 11 small Python cases: six correct changes and five unsafe changes.
Ten are controlled cases and one reproduces a behavior reported in python-dateutil issue #78 without
copying the upstream code.

| Metric | Normal green-test check | AgentProof |
| --- | ---: | ---: |
| Overall accuracy | 63.6% (7/11) | **100% (11/11)** |
| Unsafe changes found | 20% (1/5) | **100% (5/5)** |
| Correct changes accepted | 100% (6/6) | **100% (6/6)** |

The recorded run used local `qwen2.5-coder:7b`, finished in 32.9 seconds on the submission machine,
and used no paid service. These 11 cases are hackathon-scale evidence, not proof that AgentProof will
be correct on every repository.

The exact inputs and recorded result are in [evaluation/](evaluation/).

## Honest limits

- Independent model challenges currently support Python application changes and pytest.
- Repository tests are executable code. Disposable copies protect the source folder, but they are not
  a hardened container or virtual machine. Only select projects you trust.
- The recorded setup, UI demos, and evaluation were run on macOS. Windows and Linux instructions are
  provided, but were not manually tested for this submission.
- Local-model speed and output quality depend on the user's model, hardware, and model server.
- The current evaluation is small and mostly controlled. A larger public evaluation is future work.

See [FUTURE_PLANS.md](FUTURE_PLANS.md) for improvements that are not part of the current version.

## Requirements

- `uv` 0.11 or newer
- Node.js 22 or newer
- npm 10 or newer
- A local OpenAI-compatible model server for independent challenges

The recorded path uses Ollama with `qwen2.5-coder:7b`.

Python 3.12 and Python packages are installed inside this project. Frontend packages stay inside
`frontend/node_modules`.

## Quick start on macOS or Linux

From the AgentProof folder:

```bash
make setup
make check
ollama pull qwen2.5-coder:7b
make dev
```

Start the Ollama app or `ollama serve` before running a local-model challenge. `make dev` chooses free
local ports and opens AgentProof in the default browser.

To repeat the local-model smoke test and recorded evaluation:

```bash
make phase3-smoke
make evaluate
```

See [docs/REPRODUCTION.md](docs/REPRODUCTION.md) for full commands, expected results, Windows steps,
and common problems.

## Documentation

- [Submission brief](SUBMISSION.md): short problem, workflow, result, and limits
- [Product capabilities](PRODUCT_CAPABILITIES.md): what the current version can do
- [Reproduction guide](docs/REPRODUCTION.md): exact local setup and checks
- [Evaluation](docs/EVALUATION.md): cases, baseline, metrics, and limits
- [Architecture](docs/ARCHITECTURE.md): components and trust boundaries
- [Improvement changelog](IMPROVEMENT_CHANGELOG.md): failures, evidence, and engineering decisions
- [Future plans](FUTURE_PLANS.md): ideas that are not yet implemented

## Project layout

```text
backend/                   FastAPI application and verification services
frontend/                  React and Vite interface
evaluation/                Pinned evaluation cases and recorded result
traces/                    Selected development and runtime evidence
artifacts/                 Local generated reports; not committed by default
docs/                      Technical and reproduction documents
Makefile                   Main setup, test, run, smoke, and evaluation commands
requirements.txt           Fixed Python package versions
```
