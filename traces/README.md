# Trajectory Evidence

AgentProof keeps representative evidence in two categories:

```text
traces/
├── development/   Selected build episodes from each coding or research agent
└── runtime/       AgentProof baseline and verification trajectories
```

Each submitted trajectory should remain understandable from instruction to outcome and include:

- Trace identifier, timestamp, agent, model, and relevant version.
- Initial instruction and approved inputs.
- Tool calls and the tool responses that affected the next decision.
- Failures, retries, feedback, and human checkpoints.
- Final result with links or digests for generated evidence.
- A redaction note for any removed credentials, private data, or irrelevant local paths.

Representative excerpts are acceptable, but they must not hide failures or splice unrelated events into a misleading sequence. Raw local traces and generated reports belong in `artifacts/` and are not committed by default.

Committed representative development traces cover every agent used materially during the project:

- `development/codex-building-agentproof.md`
- `development/qwen-opencode-directory-picker.md`
- `development/gemini-project-research.md`

Committed runtime evidence includes a successful Qwen2.5-Coder smoke run, unsuccessful Qwen3.6
experiments, and the machine-readable 11-case result at
`../evaluation/results/recorded-evaluation.json`.

Phase 3 challenge runs store `trajectory.json`, `report.json`, the generated test, and both disposable
workspaces under `artifacts/runs/<run-id>/challenges/<challenge-id>/`. The trajectory records the full
model prompt and response, so it must be reviewed for private source content before submission. Failed,
empty, malformed, and safety-rejected model attempts also retain a trajectory instead of disappearing
as an unexplained UI error.
