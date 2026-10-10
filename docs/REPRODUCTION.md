# Reproduction Guide

This guide runs AgentProof through the same browser workflow shown in the video. The submitted folder
contains `agent_proof` and `ui_demo_cases`. Keep them next to each other after extracting the ZIP.

AgentProof uses a local model through Ollama. It does not need a paid API key.

## What you need

- Git: <https://git-scm.com/downloads>
- `uv` 0.11 or newer: <https://docs.astral.sh/uv/getting-started/installation/>
- Node.js 22 or newer and npm 10 or newer: <https://nodejs.org/en/download>
- Ollama: <https://ollama.com/download>
- About 8 GB of free space

The submission was tested on macOS with Python 3.12.13, `uv` 0.11.32, Node.js 24.18.0, npm
11.16.0, Ollama 0.33.2, and `qwen2.5-coder:7b`.

## 1. Install AgentProof

Open a terminal in the `agent_proof` folder:

```bash
make setup
```

This installs Python and frontend packages inside the project folder.

## 2. Start the local model

Download the tested model once:

```bash
ollama pull qwen2.5-coder:7b
```

Start the Ollama desktop app. If you do not use the desktop app, run this in another terminal:

```bash
ollama serve
```

Do not start both. Confirm that the model is available:

```bash
curl --max-time 5 http://127.0.0.1:11434/v1/models
```

The result should include `qwen2.5-coder:7b`.

## 3. Start the web app

From the `agent_proof` folder:

```bash
make dev
```

The page opens automatically. If it does not, open the local address printed in the terminal.

## 4. Correct-change demo

This case is based on the empty-input behavior reported in python-dateutil issue #78. It contains no
copied upstream source code.

### Create the first approved baseline

Open another terminal in the folder that contains both submitted folders and run:

```bash
git -C ui_demo_cases/public_dateutil_empty_input restore --worktree .
```

In AgentProof:

1. Click **Browse** and select `ui_demo_cases/public_dateutil_empty_input`.
2. Enter this original task:

```text
Update parse_date(text, default) so blank input raises ValueError instead of returning the default; valid ISO dates, whitespace handling, invalid-format errors, and formatting must keep working.
```

3. Click **Inspect project**.
4. The first audit should say that the current tests pass and a first baseline is needed.
5. Click **Approve first baseline**.

This approval is only needed once on a new AgentProof installation.

### Apply and verify the change

Keep AgentProof running. From the folder containing both submitted folders, run:

```bash
git -C ui_demo_cases/public_dateutil_empty_input apply ../changes/public_dateutil_empty_input.patch
```

Back in AgentProof:

1. Click **Inspect project** again.
2. Confirm that `parser.py` appears in the Before/After view.
3. Click **Run verification checks**.
4. Expected Step 1 result: `INCONCLUSIVE`. The approved tests pass, but they do not prove the new
   blank-input behavior.
5. In Step 2, keep the default local address `http://127.0.0.1:11434/v1` and model choice `auto`.
6. Click **Run local challenge**.

Expected final result:

- Verdict: `VERIFIED`
- Old approved version challenge: `Failed`
- New changed version challenge: `Passed`

The old version is expected to fail the new challenge because it does not yet raise `ValueError`.
The new version should pass because it adds that requested behavior.

The exact generated wording, token count, and run time may vary because a local model creates the
challenge. If the result is `INCONCLUSIVE`, confirm that the selected model is
`qwen2.5-coder:7b` and run the local challenge once more. Failed attempts are kept as evidence.

Do not click **Approve as next baseline** if you want to repeat the same demo.

## 5. Unsafe deleted-test demo

### Create the first approved baseline

From the folder containing both submitted folders:

```bash
git -C ui_demo_cases/unsafe_deleted_test restore --worktree .
```

In AgentProof:

1. Select `ui_demo_cases/unsafe_deleted_test`.
2. Enter this original task:

```text
Refactor total_after_discount to make the membership rule easier to read without changing prices for any order, including large non-member orders.
```

3. Click **Inspect project**.
4. Confirm that the current tests pass, then click **Approve first baseline**.

### Apply and verify the unsafe change

Keep AgentProof running. From the folder containing both submitted folders:

```bash
git -C ui_demo_cases/unsafe_deleted_test apply ../changes/unsafe_deleted_test.patch
```

Back in AgentProof:

1. Click **Inspect project** again.
2. The Before/After view should show `discounts.py` changed and
   `tests/test_large_non_member.py` deleted.
3. Click **Run verification checks**.

Expected result:

- Verdict: `UNSAFE`
- The deleted approved test is restored and run.
- It expects a large non-member order to remain `150`, but the changed code returns `135`.
- Step 2 does not appear because Step 1 already found direct proof of a problem. No model call is
  needed.

## Repeat either demo

Restore the selected demo to its old version, then apply its change again after inspection:

```bash
git -C ui_demo_cases/public_dateutil_empty_input restore --worktree .
git -C ui_demo_cases/unsafe_deleted_test restore --worktree .
```

If the changed state was already approved, AgentProof will correctly report that it matches the
latest approved baseline. Use a fresh extracted copy for the full first-baseline demonstration.

## Optional developer checks

These commands are not required for the browser demo.

From the `agent_proof` folder:

```bash
make check
make phase3-smoke
make evaluate
```

Expected project check: 82 backend tests and 13 frontend tests pass, followed by a successful
frontend build.

The recorded 11-case evaluation result is:

- Normal green-test accuracy: 63.6%
- AgentProof accuracy: 100%
- Normal unsafe-change detection: 20%
- AgentProof unsafe-change detection: 100%

Model time and token use can change with the computer. The recorded result is saved in
`evaluation/results/recorded-evaluation.json`.

## Clean-copy relocation check (23 September 2026)

We copied the application source and setup files, fresh Git copies of both demo projects, and their
two patch files into a temporary folder whose name contained spaces. The copy did not include a virtual
environment, package cache, frontend build, `.env` file, generated evidence, or model files.

In that copy, `make setup` installed Python 3.12.13 inside the project, 29 pinned Python packages,
and the frontend packages. `make check` passed Python lint, TypeScript checks, 82 backend tests,
13 frontend tests, and the production build. The frontend lockfile did not change. First-time setup
needs network access to download Python and packages. npm reported two moderate dependency
advisories; they did not fail setup or the checks.

The local app started. Its backend health endpoint and frontend page responded successfully. The
directory-browsing service used by the folder picker listed both demo projects, and inspecting each
produced a passing current-state audit.
Generated audit files stayed under `artifacts/`, which Git ignores. No old Desktop path appeared in
the copied source or demo files.

This check did not run a live model challenge. To check that optional step, start Ollama with
`qwen2.5-coder:7b` and follow the two browser demos above.

## Windows notes

Windows was not manually tested for this submission. Install the same tools, run the PowerShell
commands below from `agent_proof`, and then follow the same browser steps.

```powershell
uv python install 3.12
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
Set-Location frontend
npm install
Set-Location ..
```

Start the backend and frontend in separate PowerShell windows:

```powershell
.\.venv\Scripts\python.exe -m uvicorn agentproof.app:app --app-dir backend --host 127.0.0.1 --port 8000
```

```powershell
Set-Location frontend
npm run dev -- --host 127.0.0.1
```

Open <http://127.0.0.1:5173>.

## Safety and current limits

- Project files and model requests stay on the local computer.
- AgentProof does not edit the selected source folder.
- Generated challenges currently support Python projects that use pytest.
- Repository tests are executable code. The current isolation uses disposable local copies, not a
  hardened virtual machine, so only select projects you trust.
