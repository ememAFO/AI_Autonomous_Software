# Stage 4C Hound Factory Wrapper Patch v0.1

## Purpose

This patch adds a provider-neutral research adapter contract and a governed
Hound implementation for the EOP-0001 live benchmark.

It does **not** approve Hound for production use.

## Added files

- `src/adapters/research_adapter.py`
- `src/adapters/hound_policy.py`
- `src/adapters/hound_robots.py`
- `src/adapters/hound_transport.py`
- `src/adapters/hound_adapter.py`
- `src/research/evidence_candidate_queue.py`
- `scripts/run_hound_benchmark.py`
- `config/hound_pilot_safety_profile.json`
- `config/hound_live_benchmark_test_plan.json`
- Four test modules under `tests/research/`

No existing factory file is overwritten by this patch.

## Enforced boundaries

- Search and fetch only
- Core/HTTP-only Hound package
- No browser, stealth, Cloudflare solving, proxies, cookies or actions
- Factory-owned domain allowlist
- Robots fail closed on network/parser uncertainty
- 404/410 robots absence is allowed
- Fresh fetches (`cache_ttl=0`)
- Off-allowlist redirects blocked
- Retrieved text treated as untrusted
- Instruction-like content quarantined
- Append-only candidate queue
- No direct approved-registry writes
- No outreach, publication or customer action

## Installation on the factory VM

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install "hound-mcp==13.1.0"
```

Do **not** install `hound-mcp[all]`. Do not install Playwright or Patchright.

Copy the frozen registry to:

```text
data/eop/EOP-0001_Evidence_Registry_v1.0.json
```

Run all tests first:

```bash
pytest
ruff check .
mypy src
bandit -r src
```

Then run the benchmark:

```bash
python scripts/run_hound_benchmark.py \
  --profile config/hound_pilot_safety_profile.json \
  --plan config/hound_live_benchmark_test_plan.json \
  --registry data/eop/EOP-0001_Evidence_Registry_v1.0.json
```

Outputs:

- `data/hound/evidence_candidates/<run-id>.jsonl`
- `reports/hound/eop-0001-benchmark-run.json`

## Human gate

The benchmark report deliberately leaves precision blank. A human must label
which candidates are relevant and whether their metadata and content are
adequate. Candidate files must never be copied into an approved evidence
registry without the existing validation and human-review process.

## Known limitation

The prompt-injection scanner is a fail-safe heuristic, not a complete semantic
detector. Its primary control is architectural: retrieved content cannot alter
permissions, call tools, change scope or write to the evidence registry.
