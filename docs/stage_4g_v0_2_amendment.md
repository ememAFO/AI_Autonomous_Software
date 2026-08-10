# Stage 4G v0.2 — Operational Measurement Amendment

## Purpose

Stage 4G v0.2 is an additive amendment over the technically clean v0.1
baseline. It creates a separate governed lane for measured pilot outcomes.
It does not alter the existing first-party evidence taxonomy or relabel pilot
telemetry as a customer interview.

## Boundary

The lane is:

1. sanitized operational measurement capture;
2. read-only measurement review packet;
3. explicit human resolution to a verified measurement registry.

There is intentionally no command that imports these records into
`validation_evidence_log.json`.

Every candidate, packet, resolution, and verified record states:

- `taxonomy_status=separate_operational_measurement`;
- `validation_log_import_allowed=false`;
- `claim_boundary=observational_not_causal`.

## Measurement design

Each record requires a baseline period, intervention date, observation period,
sample sizes, comparison method, operational context, known confounders,
outcomes before and after, effect magnitude, effect direction, persistence,
expert interpretation, and the operational decision taken.

The service derives change and effect direction from the metric policy. It
blocks short measurement windows, small samples, invalid period ordering,
unsupported metrics, unsupported confounders, PII, duplicate records,
placeholder content, and synthetic measurements.

## Structured feedback

The policy includes bounded reason codes for system failures and useful
outputs. It also records unintended effects such as alert fatigue, excessive
follow-up, customer confusion, increased workload, and data-entry burden.

## Commands

Capture a real sanitized measurement export:

```bash
python scripts/capture_operational_measurement.py \
  --input data/manual/eop_0001_operational_measurements.json \
  --policy config/eop_0001_operational_measurement_policy.json \
  --output reports/research/operational_measurement_capture/EOP-0001-OM-001.json
```

Prepare a read-only review packet:

```bash
python scripts/prepare_operational_measurement_review.py \
  --candidates data/research/operational_measurement_candidates/EOP-0001-QUOTE-OUTCOME-MEASUREMENT-0-1.jsonl \
  --policy config/eop_0001_operational_measurement_policy.json \
  --output reports/research/operational_measurement_review_packets/EOP-0001-OM-001.json \
  --decision-template reports/research/operational_measurement_review_packets/EOP-0001-OM-001-decision-template.json
```

Resolve a completed human review:

```bash
python scripts/resolve_operational_measurement_review.py \
  --packet reports/research/operational_measurement_review_packets/EOP-0001-OM-001.json \
  --decisions reports/research/operational_measurement_review_packets/EOP-0001-OM-001-approved.json \
  --output reports/research/operational_measurement_review_resolutions/EOP-0001-OM-001.json
```

The exact candidate filename is produced by the capture report. Use that path
rather than guessing it.
