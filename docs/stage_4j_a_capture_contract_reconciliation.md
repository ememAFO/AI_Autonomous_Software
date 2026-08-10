# Stage 4J-A — Capture Contract Reconciliation v0.1

## Purpose

Stage 4J-A reconciles the visually approved Stage 4I v0.2 form with the existing
Stage 4G first-party validation policy before any network service is introduced.

This stage is additive and network-off.

## Trust boundary

Participant requests may provide only answers and explicit consent. The trusted
normalizer derives campaign/provenance/governance fields.

Client requests have no authority over:

- validation support or evidence strength;
- evidence type or review mode;
- taxonomy/trust classification;
- validation-log import;
- launch/deployment state;
- synthetic/live eligibility;
- protected actions.

## Research/contact separation

Research records contain no direct contact identifiers. A separate optional
contact request may contain contact information and is linked only by the
participant token. Contact records are never submitted to Stage 4G research
capture.

## Stage 4G reconciliation

The detailed Stage 4I role is retained in the canonical research record while a
coarse role is derived for the Stage 4G policy:

- electrical_business_owner -> electrician_owner
- self_employed_electrician -> electrician_owner
- estimator_or_surveyor -> electrical_contractor_staff
- quotation_administrator -> electrical_contractor_staff
- operations_or_contracts_manager -> electrical_contractor_staff
- other_electrical_trade_role -> electrical_contractor_staff
- not_target_market -> rejected

The Stage 4G-compatible public-form record is normalized to:

- capture_method: public_form
- evidence_kind: structured_response
- attestation_basis: direct_response
- review_mode: hold_only
- supports_validation: false

## Versions

- Question set: EOP-0001-QS-0.2
- Consent: EOP-0001-CONSENT-0.2
- Stage 4G policy: EOP-0001-STAGE4G-0.2
- Stage 4J-A contract: EOP-0001-STAGE4J-A-CAPTURE-CONTRACT-0.1

Legacy Stage 4G/4H artifacts are preserved for audit history.

## Non-authorizations

Stage 4J-A does not:

- open a network listener;
- enable server-side storage;
- collect live contact data;
- post publicly;
- contact participants;
- change validation state;
- import evidence into the validation log.

All protected actions remain false until later explicit human gates.
