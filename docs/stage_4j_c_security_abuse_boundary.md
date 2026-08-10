# Stage 4J-C — Security, Abuse & Deployment Boundary v0.1

## Purpose

Stage 4J-C defines the security contract a future HTTP adapter must satisfy
before any public request can reach Stage 4J-A normalization or Stage 4J-B
storage.

This stage remains network-off.

## No server yet

Stage 4J-C does not introduce FastAPI, Flask, Django, Starlette, nginx, a cloud
platform, a port, DNS, TLS certificates, or public hosting.

The purpose is to make the security rules testable before selecting deployment
infrastructure.

## Request envelope

The future adapter must accept only:

- POST
- `application/json`
- UTF-8 JSON objects
- no query-string submission
- no participant token in URLs
- bounded research/contact request bodies
- bounded JSON depth, node count, array length and string length

These are pre-normalization controls. Stage 4J-A still owns field-level request
validation and client-governance rejection.

## Origin / CORS / CSRF

The current origin mode is `deny_all_until_origin_approved`.

No production origin has been invented and the allow-list is empty. Therefore
the default security validator fails every origin today.

A future same-origin deployment must use:

- explicit origin validation
- no wildcard CORS
- no credentialed wildcard access
- same-origin JSON POST semantics

If a later architecture requires cross-origin state or cookie credentials, the
CSRF design must be reviewed again rather than silently widening this policy.

## Rate limiting

The in-memory limiter in this stage is a **design-test implementation only**.
It proves:

- separate research/contact thresholds can be expressed;
- a request key can be hashed before retention;
- raw network identifiers need not be persisted;
- requests can fail closed when a threshold is exceeded.

The numerical thresholds are proposed guardrails, not production-approved
limits. A distributed/shared limiter is required before multi-instance
deployment.

## Replay / idempotency

Stage 4J-C does not claim replay protection is solved.

Before live use, the HTTP contract still needs:

- an idempotency-key design;
- bounded replay cache semantics;
- expiration rules;
- behavior for retries after partial failure.

Stage 4J-B duplicate protection remains defense-in-depth but is not a complete
network replay solution.

## Error disclosure

Internal validation reasons, stack traces and raw exceptions are never intended
for public responses. The security adapter maps failures onto a small generic
public error-code vocabulary.

Detailed failures belong only in controlled internal observability, subject to
the existing PII/minimisation rules.

## Contact access

Persisting a contact opt-in does not authorize automatic contact or browser
readback.

Before live use, contact data requires:

- role-based authorization;
- human-authorized access;
- access logging;
- no anonymous/browser contact-store reads;
- a reviewed operational process for participant contact.

## Secrets

Production secrets must not be committed to the repository or exposed to
agents. A managed secret store or environment-injection mechanism plus a
rotation process is required before deployment.

## Privacy and retention

Security approval cannot substitute for privacy approval.

Still required before live deployment:

- final live privacy-notice review;
- production retention schedule;
- deletion process;
- data-access process;
- contact-access policy.

## Future response security headers

The contract specifies future response headers including CSP, no-referrer,
nosniff, no-store, restrictive permissions, cross-origin isolation policies and
HSTS. They are configuration requirements, not evidence that a server is
currently serving them.

## Protected actions

All protected actions remain false, including:

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
