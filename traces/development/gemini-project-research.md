# Representative research trajectory — Gemini second opinion

The human requested an independent project-selection opinion before implementation. Gemini was given
the hackathon constraints and the previously discussed project candidates, but not the private local
coding-UI project.

## Research output considered

Gemini ranked database rollback reconciliation (`MigraSafe`) and Terraform drift reconciliation highly,
and criticized BoundaryGuard, browser-heavy Bug2Test, and environment repair on fit, flakiness, or
existing alternatives. It proposed additional topics including data cleanup, flaky-test repair,
dependency downgrade refactoring, feature-flag pruning, localization, and distributed-log analysis.

## Adversarial review

The recommendation was not adopted automatically:

- Database rollback and infrastructure drift are impactful but require production semantics and
  safety guarantees that were difficult to establish in the remaining hackathon time.
- Several claims in the response were not backed by directly reproducible evidence.
- ContractFix had a clear workflow but depended on a reviewer possessing a suitable old/new API
  migration scenario.
- The chosen project needed a judge-controlled ground truth rather than trusting a fabricated success
  story.

## Decision influenced by the research

The team selected AgentProof: a local verifier where the same known patch can be run through a normal
green-test baseline and an independent evidence workflow. The research therefore improved the
selection criteria even though its top-ranked project was rejected.

No Gemini-generated code or verdict is part of AgentProof's runtime.
