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

See [PRODUCT_CAPABILITIES.md](docs/PRODUCT_CAPABILITIES.md) for the complete current feature list.

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

See [FUTURE_PLANS.md](docs/FUTURE_PLANS.md) for improvements that are not part of the current version.

## Requirements

- Git
- `uv` 0.11 or newer
- Node.js 22 or newer
- npm 10 or newer
- A local OpenAI-compatible model server for independent challenges

The recorded path uses Ollama with `qwen2.5-coder:7b`.

Python 3.12 and Python packages are installed inside this project. Frontend packages stay inside
`frontend/node_modules`.

## Quick start on macOS or Linux

Clone the repository, then install and check the application:

```bash
git clone https://github.com/Adolph1999v/agent_proof.git
cd agent_proof
make setup
make check
make dev
```

If you already have the project folder, run the last three commands from that folder. `make check`
does not need a model. `make dev` chooses free local ports and opens AgentProof in the default browser.

To use Step 2's independent challenge, download the tested local model and start the Ollama app (or
run `ollama serve` in another terminal):

```bash
ollama pull qwen2.5-coder:7b
```

To repeat the local-model smoke test and recorded evaluation:

```bash
make phase3-smoke
make evaluate
```

New evaluation runs write to ignored `artifacts/evaluation/`; the committed result under
`evaluation/results/` remains a fixed historical record.

To try the two browser demos from a GitHub clone, run `make demo-setup` once. It creates fresh Git
projects under ignored `artifacts/ui_demo_cases/` and leaves existing demo folders alone. Follow the
[reproduction guide](docs/REPRODUCTION.md) to inspect, change, and verify them.

See [docs/REPRODUCTION.md](docs/REPRODUCTION.md) for full commands, expected results, Windows steps,
and common problems.

## Documentation

- [Submission brief](docs/SUBMISSION.md): short problem, workflow, result, and limits
- [Basic to improved comparison](docs/BASELINE_TO_ADVANCED.md): fair baseline, added features, and measured gain
- [Agent trajectories](docs/AGENT_TRAJECTORIES.md): how each agent, retry, and human checkpoint was used
- [Product capabilities](docs/PRODUCT_CAPABILITIES.md): what the current version can do
- [Reproduction guide](docs/REPRODUCTION.md): exact local setup and checks
- [Evaluation](docs/EVALUATION.md): cases, baseline, metrics, and limits
- [Architecture](docs/ARCHITECTURE.md): components and trust boundaries
- [Improvement changelog](docs/IMPROVEMENT_CHANGELOG.md): failures, evidence, and engineering decisions
- [Future plans](docs/FUTURE_PLANS.md): ideas that are not yet implemented
- [Portable baseline design](docs/PORTABLE_BASELINES.md): proposed backup and restore workflow
- [Execution isolation assessment](docs/EXECUTION_ISOLATION.md): current limits and a safer runner design

## Project layout

```text
backend/                   FastAPI application and verification services
frontend/                  React and Vite interface
evaluation/                Pinned evaluation cases and recorded result
demo_fixtures/             Clean UI demo inputs and reusable candidate patches
traces/                    Selected development and runtime evidence
artifacts/                 Local generated reports; not committed by default
docs/                      Technical and reproduction documents
Makefile                   Main setup, test, run, smoke, and evaluation commands
requirements.txt           Fixed Python package versions
```
