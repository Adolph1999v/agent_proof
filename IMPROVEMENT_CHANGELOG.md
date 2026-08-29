# Improvement Changelog

This document connects every meaningful experiment to evidence and the next engineering decision. Results will use the same cases and resources for the baseline and final workflow unless a difference is explicitly documented.

| Stage | What we tried and why | Evidence | Decision / learning |
| --- | --- | --- | --- |
| Problem selection | Compared API migration, accessibility repair, bug reproduction, and independent patch verification against user value, reproducibility, and hackathon fit. | Public reports show coding agents can weaken tests or overstate validation; AgentProof also supports authentic public patch benchmarks. | Selected independent verification and retained ContractFix as a separate project. |
| Phase 1 | Created a minimal local web application with isolated dependencies and automated quality gates. | Ruff and TypeScript checks passed; 3 backend and 2 frontend tests passed; the production build and live frontend-to-backend proxy check succeeded. | Establish a clean, reproducible base before implementing verification behavior. |
| Phase 2 | Added deterministic patch intake for clean pytest repositories: disposable cloning, protected test/config snapshots, patch preflight, bounded baseline execution, and local JSON reports. | Automated verifier cases cover a valid source-only patch, modified tests, an invalid patch, a failing baseline, a dirty source checkout, and API report retrieval. | Existing tests can establish regression evidence, but a passing baseline remains `INCONCLUSIVE` until independent challenge tests exist. |
| Baseline | Defined as existing tests run against the candidate patch without AgentProof's frozen-test comparison or preserved evidence. | To be measured on authentic public cases in Phase 5. | Freeze the same repository, patch, and test budget for baseline and AgentProof evaluation. |
