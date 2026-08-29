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
