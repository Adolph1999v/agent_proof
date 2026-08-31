# AgentProof

AgentProof is a local-first verification layer for AI-generated code changes.

A coding agent can say that a task is complete while accidentally removing required behavior, weakening a regression test, or reporting checks it did not actually run. AgentProof will independently inspect the task, patch, original tests, and agent trace; create additional verification outside the patch's control; execute the evidence in a disposable workspace; and return a reproducible `VERIFIED` or `UNSAFE` result.

