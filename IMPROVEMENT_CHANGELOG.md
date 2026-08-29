# Improvement Changelog

This document connects every meaningful experiment to evidence and the next engineering decision. Results will use the same cases and resources for the baseline and final workflow unless a difference is explicitly documented.

| Stage | What we tried and why | Evidence | Decision / learning |
| --- | --- | --- | --- |
| Problem selection | Compared API migration, accessibility repair, bug reproduction, and independent patch verification against user value, reproducibility, and hackathon fit. | Public reports show coding agents can weaken tests or overstate validation; AgentProof also supports authentic public patch benchmarks. | Selected independent verification and retained ContractFix as a separate project. |
| Phase 1 | Created a minimal local web application with isolated dependencies and automated quality gates. | Ruff and TypeScript checks passed; 3 backend and 2 frontend tests passed; the production build and live frontend-to-backend proxy check succeeded. | Establish a clean, reproducible base before implementing verification behavior. |
| Baseline | Pending Phase 2. | Not measured yet. | The baseline must be implemented before the agent workflow. |
