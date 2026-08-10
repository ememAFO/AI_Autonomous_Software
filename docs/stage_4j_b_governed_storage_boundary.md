# Stage 4J-B — Governed Storage Boundary v0.1

## Scope

Stage 4J-B adds a local, synthetic-test-only persistence boundary after the
approved Stage 4J-A request contract.

It does **not** approve production persistence or public deployment.

## Reused factory mechanisms

The implementation extends the existing Stage 4G `ControlledJsonlStore`, which
already constrains stores to project-relative roots and provides JSONL
append/snapshot/restore operations.

Research and contact data are deliberately placed under different controlled
roots:

- `data/research/live_research_responses/`
- `data/research/live_contact_opt_ins/`
- `data/research/live_capture_batches/` for identifier-minimised write metadata

These runtime directories are not intended as tracked portfolio artifacts.

## Research boundary

The research store:

- accepts only data that passed the Stage 4J-A trusted normalizer;
- rejects direct identifier keys;
- retains the detailed structured response;
- records `live_evidence_eligible=false`;
- records `stage4g_handoff_allowed=false`;
- records `validation_log_import_allowed=false`;
- does not write directly to Stage 4G candidate storage.

Structured public responses remain hold-only.

## Contact boundary

The contact store is physically separate from research storage.

A contact record:

- requires a participant token already present in the synthetic research store;
- may contain contact name/value;
- uses the participant token as the only join key;
- is never submitted to Stage 4G research capture;
- cannot authorize participant contact;
- cannot authorize validation-log import.

## Atomicity and duplicates

Each write updates a data store plus an identifier-minimised registry record.
Snapshots are taken first. If the registry or audit step fails, the data and
registry paths are restored to their prior state.

Research duplicate protection covers server-issued submission IDs, participant
tokens, and source references. It intentionally does not deduplicate identical
answer sets because two independent participants may legitimately provide the
same answers.

Contact duplicate protection rejects an exact token/method/value/action
fingerprint.

## Audit minimisation

The existing audit logger redacts token/secret-like keys but is not a general
PII scrubber. Stage 4J-B therefore never passes raw contact values, contact
names, or raw participant tokens to audit details. Only a one-way participant
link hash and non-sensitive capture metadata are logged.

## Retention boundary

Retention metadata is attached to records, but no retention period has been
invented. The policy remains:

- `NOT_APPROVED_FOR_LIVE_USE`
- automated deletion disabled
- deletion requires human review
- a production retention schedule is required before live deployment

This stage therefore tests storage semantics without pretending that the
production privacy/retention decision has been completed.

## Protected actions

All remain false:

- public deployment
- network submission
- live server-side storage
- live contact collection
- participant contact
- public posting
- automatic outreach
- customer messaging
- validation-state change
- validation-log import
