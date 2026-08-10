# Stage 4G — First-Party Validation Capture and Evidence Gate

## Boundary

Stage 4G adds a controlled four-step lane:

1. capture sanitized candidates;
2. prepare a read-only review packet;
3. resolve human decisions into verified first-party intake;
4. explicitly import approved evidence with `--apply`.

No step changes theme state, approves a build, publishes content, sends outreach,
or stores direct participant identifiers.

## Data minimisation

The capture service rejects fields such as names, email addresses, phone
numbers, addresses, postcodes, IP addresses, device identifiers, raw responses,
full transcripts, and recordings. It stores only pseudonymous tokens and
sanitized evidence summaries.

It also blocks self-submissions, synthetic records, duplicates, missing consent,
unsupported participant roles, policy mismatches, and placeholder markers.

## Taxonomy safeguard

The current validation evidence taxonomy supports:

- `customer_interview`;
- `landing_page_result`;
- `waitlist_signup`;
- `willingness_to_pay`;
- `risk_finding`.

A structured public-form response does not silently become a customer
interview. It is marked `hold_only` until the factory deliberately adopts an
appropriate survey-response taxonomy.

## Commands

Capture a real sanitized export:

```bash
python scripts/capture_first_party_validation.py \
  --input data/manual/eop_0001_first_party_submissions.json \
  --policy config/eop_0001_first_party_validation_policy.json \
  --output reports/research/first_party_capture/EOP-0001-FPV-20260805.json
```

Prepare review only after candidates exist:

```bash
python scripts/prepare_first_party_review.py \
  --candidates data/research/first_party_candidates/EOP-0001-FPV-20260805.jsonl \
  --policy config/eop_0001_first_party_validation_policy.json \
  --output reports/research/first_party_review_packets/EOP-0001-FPV-20260805.json \
  --decision-template reports/research/first_party_review_packets/EOP-0001-FPV-20260805-decision-template.json
```

Resolve a completed human decision file:

```bash
python scripts/resolve_first_party_review.py \
  --packet reports/research/first_party_review_packets/EOP-0001-FPV-20260805.json \
  --decisions reports/research/first_party_review_packets/EOP-0001-FPV-20260805-approved.json \
  --output reports/research/first_party_review_resolutions/EOP-0001-FPV-20260805.json
```

Import only after a separate explicit action:

```bash
python scripts/import_first_party_evidence.py \
  --resolution reports/research/first_party_review_resolutions/EOP-0001-FPV-20260805.json \
  --output reports/research/first_party_evidence_imports/EOP-0001-FPV-20260805.json \
  --import-reference emem-stage4g-import-YYYYMMDD \
  --apply
```

Even if evidence-log status becomes `READY_FOR_HUMAN_REVIEW`, Stage 4G does not
transition theme state or approve MVP planning.
