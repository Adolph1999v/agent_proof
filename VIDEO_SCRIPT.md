# Five-minute video script and submission checklist

Target length: **4:30–4:45**. Do not wait for a cold model load while recording.

## Before recording

```bash
make check
curl --max-time 5 http://127.0.0.1:11434/v1/models
make evaluate CASE=unsafe-deleted-test
make dev
```

Run the single case once only to warm the local model, then clear the terminal. Confirm the model list
contains `qwen2.5-coder:7b` and no second generation model. Keep these files ready:

- `SUBMISSION.md`
- `evaluation/benchmark_cases.json` at `unsafe-deleted-test`
- `evaluation/results/recorded-evaluation.json` at `summary`
- `IMPROVEMENT_CHANGELOG.md` at the final evaluation rows
- `traces/runtime/phase3-full-project-context-limit.json`

## Script

### 0:00–0:35 — Problem and baseline

> Coding agents can say “done” after changing the very tests used to judge their work. A normal green
> suite is not independent evidence when the candidate patch can weaken, delete, or hide those tests.
> AgentProof is a local second verifier: it freezes approved evidence and challenges the change in
> disposable workspaces.

Show the `unsafe-deleted-test` case: `is_even` becomes `return True` and the odd-number regression test
is deleted. Explain that the patched suite remains green, so the baseline accepts it.

### 0:35–1:20 — Product workflow

Show the running AgentProof interface.

1. Click **Browse** and show the native folder picker.
2. Select a local project.
3. Point out the natural-language task field and automatic change discovery.
4. Explain: projects have isolated approved baselines; moved folders retain identity; verification
   never patches the selected source folder.

Do not start a long verification against AgentProof's own repository during the video.

### 1:20–2:35 — One realistic agent execution

In the terminal run:

```bash
make evaluate CASE=unsafe-deleted-test
```

While it runs:

> The same task, repository, patch, pytest command, and timeout go to both workflows. AgentProof
> quarantines the deleted test, runs unchanged baseline evidence, asks the local Qwen model for one
> bounded challenge, statically validates it, then runs it on baseline and candidate. The model never
> chooses the verdict.

Point to the final line:

```text
baseline=VERIFIED agentproof=UNSAFE expected=UNSAFE
```

Explain that baseline `VERIFIED` means the ordinary patched suite was green; AgentProof found the
preserved odd-number behavior and blocked the patch.

### 2:35–3:20 — Measured comparison

Show `SUBMISSION.md` or the JSON result summary.

> Across eleven pinned cases—six correct, five unsafe, including one public-bug-derived dateutil
> behavior—the green-test baseline scored 63.6% and detected 20% of unsafe patches. AgentProof scored
> 100%, detected all five unsafe patches, and accepted all six correct patches. The recorded run took
> 92.9 seconds on this machine and cost zero API dollars.

State the limitation immediately: eleven hackathon cases are scoped evidence, not universal proof;
the current challenge adapter is Python/pytest.

### 3:20–4:05 — Strongest improvement and traces

Show the last rows of `IMPROVEMENT_CHANGELOG.md`.

> The first full run scored only 70%. The saved trajectories showed malformed tests, missing imports,
> incorrect literals, and wrong preservation labels. I added bounded evidence-guided repair: the model
> receives the exact validation or baseline/candidate failure, gets at most two repairs, and every
> attempt and token remains recorded. There are no benchmark case IDs in the verifier.

Show `traces/` briefly: Codex, Qwen/OpenCode, Gemini research, successful runtime, and failed runtime.

### 4:05–4:35 — Removed experiment and close

Show `phase3-full-project-context-limit.json`.

> I originally tried Qwen3.6 27B Q6. The tested LM Studio runtime ignored non-thinking controls and
> spent its bounded output on reasoning, so it was too slow and unreliable for the demo. I kept the
> failed trace and switched to Qwen2.5-Coder 7B. AgentProof's core idea is simple: do not trust “done”;
> make the change produce independent evidence a human can inspect.

## Final submission checklist

- [ ] Source code points to final commit; repository is public or shared as required.
- [ ] `make setup`, `make check`, `make phase3-smoke`, and `make evaluate` were replayed from the final
      commit.
- [ ] Video is no longer than five minutes and begins with the problem and baseline.
- [ ] Video includes one actual local-model execution and the final comparison.
- [ ] Video shows the Improvement Changelog, strongest improvement, and removed Qwen3.6 experiment.
- [ ] `traces/development/`, `traces/runtime/`, and the recorded evaluation are included.
- [ ] No credentials, private source, usernames, absolute home paths, or unrelated conversations appear
      in the video or committed evidence.
- [ ] Submission description links `SUBMISSION.md`, `docs/REPRODUCTION.md`, and
      `evaluation/results/recorded-evaluation.json`.
- [ ] Claims use “on the pinned 11 cases,” not universal language.
