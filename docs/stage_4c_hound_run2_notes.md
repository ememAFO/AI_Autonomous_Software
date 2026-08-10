# Stage 4C Hound Run 2 Patch v0.2

## Why this revision exists

The first live benchmark exposed four provider-compatibility defects:

1. Hound 13.1.0 advertises `mcp_smart_search` and `mcp_smart_fetch`.
2. Search filters are nested inside the tool's `options` object.
3. Fetch auto-escalates unless `force_fetcher="http"` is explicit.
4. Hound returns `content` as `list[str]` and uses
   `metadata.canonical`, not only `canonical_url`.

Run 2 corrects those issues and separates discovery performance from
known-URL fetch performance.

## Files replaced

- `src/adapters/hound_adapter.py`
- `scripts/run_hound_benchmark.py`
- `tests/research/test_hound_adapter.py`
- `config/hound_pilot_safety_profile.json`

## New controls

- Search sends `options.site`, `options.max_results`, `options.cache_ttl=0`.
- Search results outside the query's declared domains remain blocked even
  when their domain appears in the factory-wide allowlist.
- Every fetch sends `force_fetcher="http"`.
- Any returned `stealthy` fetch is rejected as a policy violation.
- Any cached fetch is rejected.
- Hound list-shaped content is normalized into plain text.
- `metadata.canonical` is preserved.
- Run 2 measures discovery recall and direct known-URL fetch success
  separately.

## Run

```bash
pytest tests/research/test_hound_adapter.py
pytest

python scripts/run_hound_benchmark.py \
  --profile config/hound_pilot_safety_profile.json \
  --plan config/hound_live_benchmark_test_plan.json \
  --registry data/eop/EOP-0001_Evidence_Registry_v1.0.json \
  --output reports/hound/eop-0001-benchmark-run-2.json \
  --hound-command ./.venv-hound/bin/hound
```

Expected report fields:

- `discovery.recall_exact_url`
- `known_url_fetch.success_rate`
- `known_url_fetch.failed_evidence_ids`

The approved evidence registry remains untouched.
