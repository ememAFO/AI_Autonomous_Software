# Stage 4E — Routed Evidence Review and Promotion Gate

## Purpose

Stage 4E reviews candidates created by Stage 4D and allows an explicit human
decision to move eligible records into a **verified evidence intake queue**.

It does not write to:

- the original EOP evidence registry;
- `reports/intelligence/validation_evidence_log.json`;
- theme state registries;
- human-review theme packets;
- public content;
- outreach or messaging systems.

The verified-intake queue is still a staging boundary. A later, separately
controlled mapping step must decide whether an approved record can enter the
factory's validation evidence model.

## Gate checks

Before a candidate becomes reviewable, Stage 4E checks:

- required provenance fields;
- workflow identity;
- candidate status and `content_ok`;
- HTTP-only or supplied-public-Reddit fetcher;
- no cached content;
- public URL structure;
- non-empty content;
- SHA-256 content integrity;
- prompt-injection/quarantine warnings;
- duplicate source IDs;
- duplicate canonical URLs;
- duplicate content hashes.

The first valid record in a duplicate group remains eligible. Later duplicates
are blocked and reference the primary review ID.

## Human decisions

Every eligible candidate must receive exactly one decision:

- `APPROVE`
- `REJECT`
- `HOLD`

`APPROVE` additionally requires:

- a human-written evidence summary;
- one evidence classification;
- signal strength;
- explicit `supports_validation: true` or `false`.

Allowed classifications:

- `source-verified`
- `triangulated`
- `observed`
- `inferred`
- `illustrative`
- `contested`
- `rejected`

`rejected` is available only for a rejection decision.

## Prepare the EOP-0001 review packet

```bash
python scripts/prepare_routed_evidence_review.py \
  --routing-report reports/research/eop-0001-stage4d-routing.json
```

This generates:

```text
reports/research/evidence_review_packets/<workflow>.json
reports/research/evidence_review_packets/<workflow>.md
reports/research/evidence_review_packets/<workflow>-decision-template.json
```

The template is intentionally incomplete and cannot be resolved until a human
fills every eligible decision.

## Resolve after human review

```bash
python scripts/resolve_routed_evidence_review.py \
  --packet reports/research/evidence_review_packets/<workflow>.json \
  --decisions reports/research/evidence_review_packets/<workflow>-decision-template.json \
  --output reports/research/evidence_review_resolutions/<workflow>.json
```

Approved records are written to:

```text
data/research/verified_evidence_intake/<workflow>.jsonl
```

All decisions are appended to:

```text
data/research/evidence_review_decisions/<workflow>.jsonl
```

## Fail-closed conditions

Resolution is blocked when:

- the candidate queue changed after packet creation;
- the packet hash changed;
- the packet is not registered;
- an eligible candidate has no decision;
- a decision references a blocked candidate;
- an approval lacks classification or review metadata;
- the packet was already resolved;
- a duplicate verified record would be promoted.

## Governance note

A reviewer reference is an audit identifier. This local mechanism does not
authenticate identity or confer organisational authority.
