# How I Used Agents

This is my short overview of the agents used to research, build, test, and improve AgentProof. It is
not a full private chat export. The linked traces keep representative instructions, tool results,
failures, retries, and decisions.

## Codex — main build and review agent

I used Codex to plan the product, implement most of the backend and frontend, write tests, investigate
failures, and keep the evidence and documentation consistent.

I did not leave the whole project to the agent. I reviewed the UI after each phase, ran the commands on
my Mac, pasted failures and screenshots back, and approved the next step only after a manual check. My
feedback led to natural-language project inspection, separate baselines for each repository, moved-
folder recognition, the folder picker, the Before/After view, clearer button text, a smaller UI, and
more honest verdict messages.

Important retries included invalid pasted patches, a moving README fixture, deleted-test handling,
model timeouts, missing imports in generated tests, and an `INCONCLUSIVE` challenge caused by an
undefined `date` name. Codex used the saved outputs to make general fixes and add regression tests,
then I replayed the UI cases.

Result: the complete local app, automated checks, evaluation, and submission evidence. See
[traces/development/codex-building-agentproof.md](traces/development/codex-building-agentproof.md).

## Gemini — project research second opinion

I used Gemini before the build to compare project ideas and risks. It ranked other ideas highly, such
as database rollback and infrastructure drift. I did not accept that ranking automatically. I used it
to sharpen my rule: reviewers must be able to reproduce the problem and measure the result on their
own machine. That helped me choose AgentProof.

Gemini did not write production code or make runtime verdicts. See
[traces/development/gemini-project-research.md](traces/development/gemini-project-research.md).

## Qwen3.6 27B Q6 with OpenCode — bounded development task

I gave local Qwen one narrow task: build the read-only backend directory browser and focused tests.
The first response only described a plan, and a later handoff had missing imports and lint issues.
After stricter prompts, it completed the backend part. Codex reviewed it, corrected the remaining
issues, and connected and simplified the frontend after my manual feedback.

This was supervised delegation, not an unchecked handoff. See
[traces/development/qwen-opencode-directory-picker.md](traces/development/qwen-opencode-directory-picker.md).

## Qwen models inside AgentProof — local challenge agents

I first tested Qwen3.6 27B Q6 through LM Studio. One small run succeeded, but larger runs spent too
long reasoning, exhausted the output budget, or returned no usable JSON. I kept those failed traces
instead of hiding them.

I then tested local Qwen2.5-Coder 7B through Ollama. It was faster and reliable enough for the short
demo, so it became the submission default. It proposes a pytest challenge, but AgentProof checks the
test and executes it on both versions. The model cannot declare the final verdict. When it produced a
bad test, AgentProof rejected or repaired only safe, clear mistakes and kept every attempt in the
trajectory.

Runtime examples are in [traces/runtime/](traces/runtime/), including successful Qwen2.5 evidence and
failed Qwen3.6 experiments.

## Human checkpoints

My checkpoints were: approve the problem, review each phase, run `make check`, test the real browser
workflow, compare model speed and failures, inspect Before/After output, confirm `UNSAFE` and
`VERIFIED` cases, and decide whether a verified state becomes the next baseline. Agent output was
always treated as a proposal until code, tests, or a manual replay supported it.
