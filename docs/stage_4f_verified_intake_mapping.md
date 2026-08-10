# Stage 4F — Verified Intake Mapping

## Purpose

Stage 4F maps human-approved Stage 4E verified intake into the factory's
existing validation evidence model without changing that model's trust,
evidence-type or gate-counting rules.

The process has two separate commands:

1. prepare a read-only mapping packet;
2. apply a separately approved mapping with an explicit `--apply` flag.

Preparation does not modify the validation evidence log.

## Existing taxonomy preserved

The current validation evidence model permits:

- `public_dataset` with `manual_research` or `risk_finding`;
- `public_competitor` with `competitor_check` or `risk_finding`;
- `human_attested_first_party` only for direct primary evidence or a direct
  risk finding.

Stage 4F cannot label public web evidence as
`human_attested_first_party`. It contributes zero primary entries.

For EOP-0001:

- Citizens Advice, Which? and the bounded IET forum observation map to
  `public_dataset` + `manual_research`;
- ICO compliance guidance maps to `public_dataset` + `risk_finding`;
- Fergus, ServiceM8, Powered Now, Jobber and Xero documentation map to
  `public_competitor` + `competitor_check`.

The existing name `public_dataset` is used as the model's available
non-competitor public-research bucket. Stage 4F does not claim every source is
literally a dataset.

## Prepare EOP-0001 mapping

```bash
python scripts/prepare_verified_intake_mapping.py \
  --intake data/research/verified_evidence_intake/EOP-0001-STAGE4D-20260804T230931Z.jsonl \
  --resolution reports/research/evidence_review_resolutions/EOP-0001-STAGE4D-20260804T230931Z.json \
  --policy config/eop_0001_verified_intake_mapping_policy.json \
  --output reports/research/verified_intake_mappings/EOP-0001-STAGE4D-20260804T230931Z.json \
  --approval-template reports/research/verified_intake_mappings/EOP-0001-STAGE4D-20260804T230931Z-approval-template.json
```

Expected proposed mapping:

```text
eligible: 9
blocked: 0
proposed_primary_entries: 0
proposed_secondary_entries: 8
proposed_risk_entries: 1
```

The approval template is incomplete and non-executable until every eligible
mapping receives `APPROVE`, `HOLD` or `REJECT` and an audit reference.

## Apply after separate approval

```bash
python scripts/apply_verified_intake_mapping.py \
  --packet reports/research/verified_intake_mappings/EOP-0001-STAGE4D-20260804T230931Z.json \
  --approval reports/research/verified_intake_mappings/EOP-0001-STAGE4D-20260804T230931Z-approved.json \
  --output reports/research/validation_evidence_imports/EOP-0001-STAGE4D-20260804T230931Z.json \
  --apply
```

Application performs a dry-run against a temporary validation evidence log,
checks for duplicate source references, and restores the original target log
if any append fails.

## Governance boundary

Stage 4F may append approved mapped summaries to:

```text
reports/intelligence/validation_evidence_log.json
```

It does not:

- modify the Stage 4E verified intake;
- modify the original EOP evidence registry;
- create first-party evidence;
- change theme state;
- approve an MVP or build;
- publish content;
- contact anyone.

Even after import, public evidence alone cannot satisfy the factory's
first-party validation threshold.
