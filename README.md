# AgentProof

AgentProof is a local-first verification layer for AI-generated code changes.

A coding agent can say that a task is complete while accidentally removing required behavior, weakening a regression test, or reporting checks it did not actually run. AgentProof will independently inspect the task, patch, original tests, and agent trace; create additional verification outside the patch's control; execute the evidence in a disposable workspace; and return a reproducible `VERIFIED` or `UNSAFE` result.

## Current status

Phase 1 provides the reproducible project foundation:

- FastAPI backend with health, capability, and model-evaluation-rubric endpoints.
- React + Vite TypeScript interface connected to the backend.
- Isolated Python environment managed by `uv`.
- Backend and frontend automated tests.
- One-command lint, test, build, and full quality gates.
- Architecture, evaluation, reproduction, trace, and improvement documentation.

Patch verification and model execution intentionally begin in later phases; the interface does not claim that they work yet.

## Why a local web application?

AgentProof is an application served locally, not a hosted service. The browser provides a consistent interface on macOS, Linux, and Windows, while the local FastAPI process will work with user-approved repositories and model servers. This avoids native application signing, installers, and operating-system-specific filesystem permission layers that do not improve verification quality.

## Requirements

- `uv` 0.11 or newer
- Node.js 22 or newer
- npm 10 or newer

Python 3.12 is installed and managed locally by `uv`. Python dependencies are installed only inside `.venv`; frontend dependencies remain inside `frontend/node_modules`.

## Setup

From the repository root on macOS or Linux:

```bash
make setup
```

## Run

```bash
make dev
```

AgentProof selects available local ports, prints the address, and opens it in your default browser. If the preferred ports are occupied by another project, no extra arguments are required.

You can also run the frontend from the repository root with:

```bash
npm run dev
```

The backend must still be started separately with `make dev-backend` when using that frontend-only command. `make dev` remains the recommended workflow.

## Quality gates

```bash
make test
make lint
make check
```

See [docs/REPRODUCTION.md](docs/REPRODUCTION.md) for clean-environment and Windows commands.

## Planned phases

1. **Foundation:** reproducible application shell, documentation, and quality gates.
2. **Deterministic verifier:** patch ingestion, immutable test snapshots, diff checks, isolated execution, and evidence schemas.
3. **Model bake-off:** compare Qwen3.6 27B Q6, Qwen3-Coder 30B, and Qwen2.5-Coder 7B on authentic patches.
4. **Agent workflow:** invariant extraction, adversarial-test generation, bounded retries, and human checkpoints.
5. **Evaluation and submission:** ten or more cases, fair baseline, measured improvement, representative trajectories, and video-ready workflow.

## Project layout

```text
backend/                   FastAPI application and deterministic services
frontend/                  React + Vite TypeScript interface
evaluation/                Pinned authentic evaluation inputs
traces/                    Representative development and runtime trajectories
artifacts/                 Generated local reports and runs (not committed)
docs/                      Architecture, evaluation, and reproduction decisions
IMPROVEMENT_CHANGELOG.md   Evidence-backed iteration history
Makefile                   Reproducible developer commands
pyproject.toml             Python dependency source
requirements.txt           Exact Python dependency lock
```

## Safety boundary

AgentProof will never treat an LLM's confidence as proof. Models may propose requirements or tests, but only deterministic checks executed in a disposable workspace can contribute to the verdict. Applying or exporting a change will require human approval.
