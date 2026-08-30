# AgentProof

AgentProof is a local-first verification layer for AI-generated code changes.

A coding agent can say that a task is complete while accidentally removing required behavior, weakening a regression test, or reporting checks it did not actually run. AgentProof will independently inspect the task, patch, original tests, and agent trace; create additional verification outside the patch's control; execute the evidence in a disposable workspace; and return a reproducible `VERIFIED` or `UNSAFE` result.

## Current status

Phase 3 adds local-model independent challenges to the automatic baseline workflow:

- FastAPI backend with health, capability, and model-evaluation-rubric endpoints.
- React + Vite TypeScript interface connected to the backend.
- Isolated Python environment managed by `uv`.
- Backend and frontend automated tests.
- One-command lint, test, build, and full quality gates.
- A typed `POST /api/verifications` workflow for a user-approved local Git repository and unified diff.
- AgentProof-owned disposable Git clones; the source checkout is never patched or tested in place.
- Immutable snapshots of existing tests, `conftest.py`, and pytest configuration before patch application.
- Explicit rejection of patches that apply but produce no repository change.
- A bounded, fixed `python -m pytest -q` baseline adapter and a local JSON evidence report per run.
- Natural-language automatic mode that does not require users to supply a Git patch.
- Stable project identities that survive folder moves and prevent cross-project baseline reuse.
- Immutable, content-addressed baselines with parent history and human approval.
- Current-state audits for projects that do not yet have an older baseline.
- Automatic added, modified, deleted, and renamed-file discovery against the latest approved state.
- A localhost-only OpenAI-compatible adapter for LM Studio and Ollama.
- Single-request model admission so memory-bound machines never run parallel model calls.
- Structured invariant and pytest challenge generation with static safety validation.
- Separate baseline and candidate challenge workspaces with deterministic verdict rules.
- Complete local trajectories containing prompts, model responses, token usage, generated tests,
  command output, and hashes.

The implemented model challenge adapter intentionally supports pytest repositories only. Other test
frameworks and stronger operating-system/container isolation remain future work.

### Honest verdicts

- `UNSAFE`: the patch does not apply, produces no application change, or causes an unchanged frozen
  baseline test to fail. Candidate-authored test and test-configuration changes are quarantined rather
  than trusted.
- `INCONCLUSIVE`: the baseline passes, times out, or cannot be run. Passing existing tests alone is not proof
  that the task was solved, so Phase 2 does not emit `VERIFIED`.
- `VERIFIED`: the preserved baseline suite passes and an accepted independent challenge produces the
  expected baseline/candidate evidence.

See [docs/DETERMINISTIC_VERIFIER.md](docs/DETERMINISTIC_VERIFIER.md) for the security boundary and
reproducible evidence schema.

The normal workflow now discovers changes automatically. For a reliable advanced-mode manual run,
use the maintained case in [evaluation/cases/README.md](evaluation/cases/README.md) instead of
reconstructing a unified diff by hand.

See [PRODUCT_CAPABILITIES.md](PRODUCT_CAPABILITIES.md) for the concise, reviewer-facing product
contract. It describes the complete product surface; this README and the Improvement Changelog remain
the authority for runnable implementation status.

## Why a local web application?

AgentProof is an application served locally, not a hosted service. The browser provides a consistent interface on macOS, Linux, and Windows, while the local FastAPI process will work with user-approved repositories and model servers. This avoids native application signing, installers, and operating-system-specific filesystem permission layers that do not improve verification quality.

## Requirements

- `uv` 0.11 or newer
- Node.js 22 or newer
- npm 10 or newer
- Optional for Phase 3: LM Studio or Ollama serving one loaded model through a localhost
  OpenAI-compatible endpoint

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

The normal quality gate does not download or run a model. With one model already loaded in LM Studio
on port 1234, the transparent synthetic integration check is:

```bash
make phase3-smoke
```

## Planned phases

1. **Foundation:** reproducible application shell, documentation, and quality gates.
2. **Deterministic verifier:** patch ingestion, immutable test snapshots, diff checks, isolated execution, and evidence schemas. **Implemented for pytest repositories.**
3. **Baseline manager (Phase 2.5):** automatic discovery, stable project identity, current-state audit, immutable baseline approval, and isolated histories. **Implemented.**
4. **Independent model challenge:** localhost model connection, invariant extraction, generated pytest
   challenge, baseline/candidate execution, and trajectories. **Implemented.**
5. **Model bake-off:** compare Qwen3.6 27B Q6, Qwen3-Coder 30B, and Qwen2.5-Coder 7B on authentic patches.
6. **Evaluation and submission:** ten or more cases, fair baseline, measured improvement, representative trajectories, and video-ready workflow.

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
