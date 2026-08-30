# Reproduction Guide

## Supported development environment

- Python 3.12, managed by `uv`
- Node.js 22 or newer
- npm 10 or newer
- macOS or Linux for Makefile commands

Windows users can run the underlying commands from PowerShell.

## Clean setup: macOS or Linux

```bash
git clone <repository-url>
cd agent_proof
make setup
make check
make dev
```

`make dev` automatically selects available local ports, prints the final address, and opens it in the default browser. Confirm that the interface reports `Backend connected`.

## Clean setup: Windows PowerShell

```powershell
uv python install 3.12
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
Set-Location frontend
npm install
npm run lint
npm test
npm run build
Set-Location ..
.\.venv\Scripts\python.exe -m pytest backend\tests
.\.venv\Scripts\python.exe -m ruff check backend
```

Run the backend and frontend in separate PowerShell terminals:

```powershell
.\.venv\Scripts\python.exe -m uvicorn agentproof.app:app --app-dir backend --host 127.0.0.1 --port 8000
```

```powershell
Set-Location frontend
npm run dev -- --host 127.0.0.1
```

## Expected deterministic result

- Backend tests pass.
- Frontend tests pass.
- Python lint and TypeScript checks pass.
- Vite creates `frontend/dist`.
- The browser interface can identify a project, run a current-state audit, approve its first baseline,
  discover later changes automatically, and submit a local deterministic verification.
- A supported pytest repository produces an ignored local evidence report under `artifacts/runs/`.
- Project identities and baseline histories remain isolated under `artifacts/projects/<repository-id>/`.

No model download or API key is required for setup, tests, linting, builds, project discovery, baseline
management, or deterministic verification.

## Optional Phase 3 local model

AgentProof accepts an OpenAI-compatible endpoint on `127.0.0.1`, `localhost`, or `::1` only. It never
sends repository context to a remote host. LM Studio's default endpoint is
`http://127.0.0.1:1234/v1`; Ollama's is `http://127.0.0.1:11434/v1`.

The submission demo uses the existing Qwen2.5-Coder 7B model through Ollama because it produces the
bounded structured challenge reliably on a memory-constrained machine:

```bash
ollama run qwen2.5-coder:7b
make phase3-smoke
```

`make phase3-smoke` defaults to Ollama at `http://127.0.0.1:11434/v1` and automatic model discovery.
AgentProof bounds the complete prompt to 18,000 characters and the model proposal to 512 tokens.

The model remains outside the repository and is not duplicated by AgentProof. AgentProof's
process-wide request lock prevents concurrent inference. The default `auto` selection queries the
localhost model list, ignores embedding and reranking models, and selects the only text-generation
model. If more than one is available, AgentProof lists their exact IDs and requires an explicit choice.

Qwen3.6 27B Q6 remains a benchmark candidate and can be loaded with `make model-qwen`. Its current LM
Studio/Qwen3.5-compatible runtime ignores per-prompt and per-request non-thinking controls, so it is not
the submission demo default; that observed failure remains preserved as runtime evidence.

The interface shows elapsed time while waiting. Use a concrete task description that names the feature
and expected behavior; AgentProof bounds and prioritizes Python application context, asks Qwen to use
non-thinking mode, and caps the structured proposal at 512 tokens. Failed or length-limited attempts
are preserved under the source run's `challenges/` directory.

The smoke case is synthetic and exists only to prove the end-to-end connection. Model selection claims
must come from the pinned multi-case bake-off described in `docs/EVALUATION.md`.
