# Reproduction Guide

This guide rebuilds AgentProof, runs its checks, and repeats the recorded evaluation. AgentProof
uses a local model through Ollama. It does not need a paid model service or API key.

## What you need

- Git: <https://git-scm.com/downloads>
- `uv` 0.11 or newer: <https://docs.astral.sh/uv/getting-started/installation/>
- Node.js 22 or newer and npm 10 or newer: <https://nodejs.org/en/download>
- Ollama: <https://ollama.com/download>
- About 8 GB of free space for the project tools and local model

The recorded setup used Python 3.12.13, `uv` 0.11.32, Node.js 24.18.0, npm 11.16.0, and
Ollama 0.33.2. `uv` installs Python for this project, so a system-wide Python setup is not required.

## macOS or Linux

Run every command below from the AgentProof folder.

### 1. Install the project

```bash
make setup
```

This creates `.python` and `.venv` inside the project, installs the fixed Python packages, and
installs the frontend packages inside `frontend/node_modules`.

### 2. Check the project

```bash
make check
```

The expected result is:

- 77 backend tests pass.
- 13 frontend tests pass.
- Python and TypeScript checks pass.
- The frontend build finishes successfully.

### 3. Install and start the local model

Download the tested model once:

```bash
ollama pull qwen2.5-coder:7b
```

Start the Ollama desktop app, or run this in a separate terminal:

```bash
ollama serve
```

Do not start both. Check that the model is available:

```bash
ollama list
curl --max-time 5 http://127.0.0.1:11434/v1/models
```

The model is downloaded once. Later model runs stay on the computer.

### 4. Start AgentProof

```bash
make dev
```

AgentProof chooses free local ports and opens the page. If the page does not open, use the address
printed in the terminal.

In Step 02 of the page, use:

- Local model address: `http://127.0.0.1:11434/v1`
- Model name: `qwen2.5-coder:7b`

### 5. Test the local-model workflow

Keep Ollama running, open another terminal in the AgentProof folder, and run:

```bash
make phase3-smoke
```

A successful result shows:

- `challenge_verdict`: `VERIFIED`
- `baseline_challenge`: `failed`
- `candidate_challenge`: `passed`

If automatic model choice reports more than one model, run:

```bash
PYTHONPATH="$PWD/backend" .venv/bin/python scripts/phase3_smoke.py --model-name qwen2.5-coder:7b
```

### 6. Repeat the recorded evaluation

```bash
make evaluate
```

The final summary should contain:

```text
case_count: 11
baseline_accuracy_percent: 63.6
agentproof_accuracy_percent: 100.0
baseline_unsafe_detection_percent: 20.0
agentproof_unsafe_detection_percent: 100.0
agentproof_correct_patch_verification_percent: 100.0
challenge_execution_percent: 63.6
```

The recorded run used 9,467 prompt tokens, 1,600 completion tokens, and 32,938 ms. Time will change
with the computer, but the verdicts should match. The new report is saved under
`evaluation/results/`.

If automatic model choice reports more than one model, run:

```bash
PYTHONPATH="$PWD/backend" .venv/bin/python scripts/evaluate.py --model-name qwen2.5-coder:7b
```

## Windows

Use PowerShell from the AgentProof folder. These commands follow the same project tools, but Windows
was not manually tested on the submission machine.

### Install

```powershell
uv python install 3.12
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
Set-Location frontend
npm install
Set-Location ..
```

### Check

```powershell
.\.venv\Scripts\python.exe -m ruff check backend scripts
.\.venv\Scripts\python.exe -m pytest backend\tests
Set-Location frontend
npm run lint
npm test
npm run build
Set-Location ..
```

Install and start the same local model:

```powershell
ollama pull qwen2.5-coder:7b
ollama serve
```

Start AgentProof in two PowerShell windows.

Window 1:

```powershell
.\.venv\Scripts\python.exe -m uvicorn agentproof.app:app --app-dir backend --host 127.0.0.1 --port 8000
```

Window 2:

```powershell
Set-Location frontend
npm run dev -- --host 127.0.0.1
```

Open <http://127.0.0.1:5173>. Use `http://127.0.0.1:11434/v1` and
`qwen2.5-coder:7b` in Step 02.

To run the smoke test and evaluation:

```powershell
$env:PYTHONPATH = "$PWD\backend"
.\.venv\Scripts\python.exe scripts\phase3_smoke.py --model-name qwen2.5-coder:7b
.\.venv\Scripts\python.exe scripts\evaluate.py --model-name qwen2.5-coder:7b
```

## Common problems

- **Cannot connect to the model:** Start Ollama and check `ollama list`.
- **More than one model found:** Enter or pass the exact name `qwen2.5-coder:7b`.
- **A port is already used:** `make dev` chooses another free port. Use the address it prints.
- **The model is slow:** Speed depends on the computer. Keep only one large model loaded.
- **`make` is missing on Windows:** Use the PowerShell commands above.

## Safety and current scope

- Project files and model requests stay on the local computer.
- AgentProof does not change the selected source folder. It works in disposable copies.
- Generated independent challenges currently support Python projects that use pytest.
- Test code is executed locally. The current isolation is not a hardened container or virtual machine,
  so only select projects you trust.
