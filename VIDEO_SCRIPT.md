# Five-minute video script and submission checklist

Target length: **4:30–4:45**. The two demo repositories are already prepared under the sibling
`ui_demo_cases` folder with one approved baseline each and unapproved candidate changes. Do not click
**Approve as next baseline** before recording.

## Before recording

```bash
make check
curl --max-time 5 http://127.0.0.1:11434/v1/models
make phase3-smoke
make dev
```

The smoke run warms `qwen2.5-coder:7b`; clear the terminal before recording. Confirm that the model
list contains that generation model and no second generation model. Keep these files ready:

- `SUBMISSION.md`
- `evaluation/results/recorded-evaluation.json` at `summary`
- `IMPROVEMENT_CHANGELOG.md` at the final rows
- `traces/runtime/phase3-full-project-context-limit.json`

## Script

### 0:00–0:30 — Problem

> Coding agents can say “done” after changing the same tests used to judge their work. A green suite
> is not independent evidence when a patch can weaken, delete, or hide those tests. AgentProof is a
> local second verifier: it freezes approved evidence and challenges a change in disposable
> workspaces.

### 0:30–1:35 — Unsafe change through the real UI

In AgentProof, click **Browse** and select:

```text
ui_demo_cases/unsafe_deleted_test
```

Use this task:

```text
Refactor total_after_discount to make the membership rule easier to read without changing prices for any order, including large non-member orders.
```

Click **Inspect project**, then open **View before & after**. Show the changed condition and the
deleted test without opening a terminal. Close the preview, click **Verify detected changes**, and
point to:

- `discounts.py` was modified and `tests/test_large_non_member.py` was deleted.
- AgentProof returns `UNSAFE`.
- Test isolation says the candidate deletion was quarantined and approved tests were retained.
- The candidate's three remaining tests are green, but the frozen large-non-member test fails: the
  unsafe `or` condition incorrectly changes a $150 total to $135.

> The ordinary patched suite is green because the failing test was deleted. AgentProof runs the
> approved original test from its baseline, so deleting the judge cannot hide the regression.

### 1:35–2:50 — Correct public-derived fix and local-model challenge

Click **Browse** and select:

```text
ui_demo_cases/public_dateutil_empty_input
```

Use this task:

```text
Update parse_date(text, default) so blank input raises ValueError instead of returning the default; valid ISO dates, whitespace handling, invalid-format errors, and formatting must keep working.
```

Click **Inspect project**, then open **View before & after**. Show the one-line blank-input behavior
change, close the preview, and click **Verify detected changes**. The existing approved tests pass,
but AgentProof honestly returns `INCONCLUSIVE`. Click **Run local challenge** and point to:

- The four approved parser/formatting tests still pass.
- Qwen generates the missing blank-input invariant.
- The challenge fails on the approved baseline and passes on the candidate.
- The UI returns `VERIFIED` and shows model/token/evidence details.

> This behavior comes from a documented python-dateutil bug. The model only proposes a test;
> executed baseline-versus-candidate evidence owns the verdict.

### 2:50–3:30 — Measured comparison

Show `SUBMISSION.md` or the recorded JSON summary.

> Across eleven pinned cases—six correct and five unsafe, including the public-derived behavior—the
> green-test baseline scored 63.6% and detected 20% of unsafe patches. AgentProof scored 100%, found
> all five unsafe patches, and accepted all six correct patches. The final local run took 32.9
> seconds and cost zero API dollars.

State the limitation immediately: eleven hackathon cases are scoped evidence, not universal proof;
the current independent challenge adapter supports Python and pytest.

### 3:30–4:10 — Engineering improvement and traces

Show the final rows of `IMPROVEMENT_CHANGELOG.md` and briefly open `traces/`.

> The first full run scored 70%. Saved trajectories exposed malformed tests, wrong expected values,
> and incorrect preservation labels. I added bounded evidence-guided repair, strict import and safety
> validation, and deterministic verdict rules. The final UI replay also exposed a deleted-test gap,
> so AgentProof now runs every frozen approved test, including original versions of candidate-touched
> paths. There are no benchmark case IDs in the verifier.

### 4:10–4:40 — Honest removed experiment and close

Show `phase3-full-project-context-limit.json`.

> I originally tried Qwen3.6 27B Q6, but the tested runtime spent its bounded output on reasoning and
> was too slow for a five-minute demo. I kept that failure trace and selected Qwen2.5-Coder 7B.
> AgentProof turns “the agent says it is done” into evidence a human can inspect and approve.

## Final submission checklist

- [ ] Source code points to the final commit; repository is public or shared as required.
- [ ] `make setup`, `make check`, `make phase3-smoke`, and `make evaluate` were replayed from the final
      commit.
- [ ] Both prepared UI cases still show one approved baseline and unapproved detected changes.
- [ ] Video is no longer than five minutes and includes both `UNSAFE` and `VERIFIED` UI verdicts.
- [ ] Video includes one actual local-model challenge and the measured comparison.
- [ ] Video shows the Improvement Changelog, strongest improvement, and removed Qwen3.6 experiment.
- [ ] `traces/development/`, `traces/runtime/`, and the recorded evaluation are included.
- [ ] No credentials, private source, usernames, absolute home paths, or unrelated conversations appear
      in the video or committed evidence.
- [ ] Submission description links `SUBMISSION.md`, `docs/REPRODUCTION.md`, and
      `evaluation/results/recorded-evaluation.json`.
- [ ] Claims use “on the pinned 11 cases,” not universal language.
