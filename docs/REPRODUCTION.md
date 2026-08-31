# Reproduction Guide

AgentProof has two reproducible layers: deterministic quality gates that need no model, and the
local-model evaluation used for the measured submission result.

## Pinned submission environment

| Tool | Recorded version |
| --- | --- |
| Python | 3.12.13 |
| uv | 0.11.32 |
| Node.js | 24.18.0 (22+ supported) |
| npm | 11.16.0 (10+ supported) |
| Ollama client | 0.33.2 |
| Demo model | `qwen2.5-coder:7b` |

The recorded evaluation ran on an Apple M4 Max with 48 GB unified memory. It used only local
inference, so API cost was **$0**. Faster or slower machines will change duration, not the verdict
rules.

## Clean setup

From the repository root on macOS or Linux:

```bash
make setup
make check
```

Expected result: 76 backend tests and 13 frontend tests pass; Ruff, TypeScript, and the Vite
production build pass. The exact test count may increase after the recorded submission commit, but
every command must remain green.

Start the local interface:

```bash
make dev
```

`make dev` selects available localhost ports, prints the URL, and opens the browser. No hosting,
account, API key, or remote service is required.

## Local model setup

Install Ollama separately, then fetch and serve the pinned model:

```bash
ollama pull qwen2.5-coder:7b
ollama serve
```

On systems where the Ollama desktop application already runs the server, omit `ollama serve`.
Confirm exactly one generation model is visible:

```bash
curl --max-time 5 http://127.0.0.1:11434/v1/models
```

AgentProof's `auto` mode ignores embedding/reranking models and selects the sole text-generation
model. When multiple generation models are loaded, it fails clearly and asks for an exact model ID.

## Exact smoke command

```bash
make phase3-smoke
```

Expected final fields:

```text
"challenge_verdict": "VERIFIED"
"baseline_challenge": "failed"
"candidate_challenge": "passed"
```

This proves the end-to-end model connection; it is not the measured comparison.

## Exact baseline and AgentProof evaluation

```bash
make evaluate
```

The command builds all 11 pinned repositories in temporary directories. For every case it runs:

1. **Green-test baseline:** apply the full candidate patch and trust its resulting pytest suite.
2. **AgentProof:** freeze/quarantine test inputs, run unchanged evidence, ask the local model for an
   independent bounded challenge when necessary, execute baseline and candidate separately, and
   apply deterministic verdict rules.

Inputs are in `evaluation/benchmark_cases.json`; the committed output is
`evaluation/results/recorded-evaluation.json`. Expected summary:

```text
case_count: 11
baseline_accuracy_percent: 63.6
agentproof_accuracy_percent: 100.0
baseline_unsafe_detection_percent: 20.0
agentproof_unsafe_detection_percent: 100.0
agentproof_correct_patch_verification_percent: 100.0
```

The recorded run completed in 92,905 ms and used 10,099 prompt plus 1,687 completion tokens. Run one
case for a quick review or video replay:

```bash
make evaluate CASE=unsafe-deleted-test
```

Expected case result: `baseline=VERIFIED agentproof=UNSAFE expected=UNSAFE`.

## Windows PowerShell

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
.\.venv\Scripts\python.exe -m ruff check backend scripts
```

Run backend and frontend in separate terminals:

```powershell
.\.venv\Scripts\python.exe -m uvicorn agentproof.app:app --app-dir backend --host 127.0.0.1 --port 8000
```

```powershell
Set-Location frontend
npm run dev -- --host 127.0.0.1
```

For model evaluation, start Ollama and run:

```powershell
$env:PYTHONPATH = "$PWD\backend"
.\.venv\Scripts\python.exe scripts\phase3_smoke.py
.\.venv\Scripts\python.exe scripts\evaluate.py
```

## Safety and known scope

- Repository and model context remain on localhost.
- Candidate changes run only in AgentProof-owned clones; the selected source folder is not patched.
- Model output is untrusted, statically validated, and never directly chooses the verdict.
- The implemented independent challenge adapter supports changed Python application files and pytest.
- This is application-level isolation, not a hardened container or VM; use disposable repositories for
  untrusted code. Container adapters and additional languages are future work.
