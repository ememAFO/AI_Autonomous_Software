# Agent Zero + Hermes Integration Plan

## Agent Zero role

Agent Zero will be used for:

- controlled code generation
- local project edits
- running tests through the sandbox runner
- preparing pull requests or patch summaries
- generating implementation reports

Agent Zero must call the policy engine before any file change or deployment-related action.

## Hermes role

Hermes will be used for:

- research memory
- opportunity discovery
- Reddit/forum/review analysis
- trend analysis
- repeated pain point extraction
- market intelligence reports

Hermes must not modify code, deployment settings, billing, auth, or governance files.

## Boundary

Agent Zero executes engineering tasks.
Hermes researches and summarizes business intelligence.
The policy engine controls both.
