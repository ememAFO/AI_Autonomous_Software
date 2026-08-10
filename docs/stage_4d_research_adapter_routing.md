# Stage 4D — Research Adapter Routing v0.1

## Decision implemented

- Known, permitted public URLs → governed Hound HTTP-only adapter.
- Reddit URL with supplied public post content → existing local Reddit pipeline,
  then the unapproved routed evidence-candidate queue.
- Reddit URL without supplied post content → human review.
- Hound failure, robots block, policy block or unsupported source → human
  review.
- Quarantined Hound output → candidate queue and human review.
- No successful route writes to the approved evidence registry.

## Why Reddit is not fetched automatically

The existing `SafeRedditFetcher` currently returns controlled local/mock data
and explicitly does not perform live Reddit scraping. Stage 4D preserves that
boundary. Hound browser extras remain prohibited.

## Added files

- `src/adapters/reddit_local_evidence_adapter.py`
- `src/research/research_adapter_router.py`
- `src/research/routed_evidence_candidate_queue.py`
- `src/research/research_routing_review_queue.py`
- `scripts/run_routed_source_intake.py`
- `config/stage4d_routed_source_manifest.example.json`
- Three test modules under `tests/research/`

No existing file is replaced by this patch.

## Validate

```bash
pytest \
  tests/research/test_reddit_local_evidence_adapter.py \
  tests/research/test_research_adapter_router.py \
  tests/research/test_routing_queues.py

pytest
pip check
```

## Run against EOP-0001

```bash
python scripts/run_routed_source_intake.py \
  --registry data/eop/EOP-0001_Evidence_Registry_v1.0.json \
  --industry "home services" \
  --profile config/hound_pilot_safety_profile.json \
  --output reports/research/eop-0001-stage4d-routing.json \
  --hound-command ./.venv-hound/bin/hound
```

Expected routing pattern, subject to live page and robots availability:

- Non-Reddit permitted URLs are attempted through Hound.
- `EV-0014` and `EV-0015` are routed to human review unless their public post
  content is supplied through an approved manifest.

## Outputs

- `data/research/evidence_candidates/<workflow-id>.jsonl`
- `data/research/routing_review/<workflow-id>.jsonl`
- `reports/research/eop-0001-stage4d-routing.json`
- Append-only events in `logs/audit.log`

## Human gate

Candidate records remain unapproved. Existing evidence validation and human
review must run before anything enters an approved evidence registry or is used
for publication.
