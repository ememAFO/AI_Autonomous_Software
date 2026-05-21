# AI Autonomous Software Factory

A controlled AI-assisted software factory for research, opportunity discovery, MVP generation, testing, reporting, and guarded deployment.

This is not uncontrolled AGI and not an autonomous production deployment system.

## Core Rule

The system must follow this order:

RESEARCH → VALIDATION → PLANNING → BUILDING → TESTING → SECURITY_REVIEW → POLICY_REVIEW → WAITING_APPROVAL → DEPLOYMENT

If unsure, stop.

## First Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
python -m src.main
```

## Security Commands

```bash
ruff check .
mypy src
bandit -r src
pip-audit
semgrep scan
```

## Deployment Policy

Production deployment is blocked by default. The system may prepare staging deployment proposals only after tests, security checks, dependency scans, policy checks, and human approval.
