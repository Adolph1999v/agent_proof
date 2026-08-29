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

## Expected Phase 1 result

- Backend tests pass.
- Frontend tests pass.
- Python lint and TypeScript checks pass.
- Vite creates `frontend/dist`.
- The browser interface loads the model-evaluation rubric from the backend.

No model download or API key is required for Phase 1.
