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

For the recorded LM Studio smoke run, exactly one existing model was loaded:

```bash
lms server start --port 1234 --bind 127.0.0.1
lms load qwen/qwen3.6-27b --gpu max --context-length 16384 --parallel 1 \
  --identifier agentproof-qwen3.6-27b --ttl 900 --yes
make phase3-smoke
```

The model remains outside the repository and is not duplicated by AgentProof. The `--parallel 1`
setting and AgentProof's process-wide request lock prevent concurrent inference. The 15-minute idle TTL
releases memory automatically. A reviewer may use a smaller local model by entering its exact loaded
identifier in the interface; correctness must be re-evaluated rather than assumed to transfer.

A large local model can take several minutes to generate a challenge. The interface shows elapsed time
while waiting. Use a concrete task description that names the feature and expected behavior; AgentProof
still bounds and prioritizes Python application context so a large change cannot consume the full model
window. Failed or length-limited attempts are preserved under the source run's `challenges/` directory.

The smoke case is synthetic and exists only to prove the end-to-end connection. Model selection claims
must come from the pinned multi-case bake-off described in `docs/EVALUATION.md`.
