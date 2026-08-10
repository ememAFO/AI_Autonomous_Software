# Stage 4J-E — Deployment Architecture & Production-Control Selection v0.1

## Purpose

This stage makes a deployment architecture decision before any real server,
framework, cloud resource or production datastore is created.

Stage 4J-E is deliberately **network-off**.

## Recommendation

The current recommended architecture is:

1. one public same-origin domain;
2. Google global external Application Load Balancer;
3. Cloud Armor at the edge;
4. Cloud Run application service in `europe-west2` (London);
5. Cloud SQL for PostgreSQL in `europe-west2`;
6. Secret Manager for production secrets.

The recommendation is recorded, not approved.

## Why this topology fits the pilot

The existing factory is Python-first and already has:

- a trusted capture contract;
- a governed synthetic storage boundary;
- a security-envelope contract;
- an in-process HTTP adapter.

A managed container runtime therefore preserves the current architecture better
than rewriting the pilot around a provider-specific function runtime.

Keeping the form and API on one origin also preserves the Stage 4J-C
same-origin security position and avoids inventing a CORS requirement.

## First public scope — later, only if separately approved

The recommended first live scope is intentionally smaller than the complete
Stage 4J-H campaign:

- serve the public research form;
- accept `POST /research`.

The separate contact form remains deferred until production contact-data
authorization, access logging, retention, deletion and human-contact operations
have their own evidence.

This reduces the initial production PII surface.

## Default endpoint bypass

If Cloud Run is selected, the eventual public architecture must not permit
users to bypass the load balancer / edge controls by calling an unrestricted
default service URL.

The planned control is:

- Cloud Run ingress restricted to internal + load-balancing traffic;
- disable the default service URL after the load-balancer path is verified.

This requirement must be proved in deployment tests, not assumed.

## Data location

The preferred region is London (`europe-west2`) for both application runtime
and PostgreSQL.

Region choice is an architecture control, not a legal conclusion. UK GDPR
obligations still require the project's privacy and retention decisions.

## Database

Production JSONL is not recommended.

The selected production persistence target is managed PostgreSQL with:

- explicit schema;
- migrations;
- separate research/contact tables or equivalent access boundaries;
- uniqueness constraints for server IDs and replay/idempotency controls;
- encrypted transport;
- managed backups;
- point-in-time recovery;
- restore testing.

The Stage 4J-B JSONL adapter remains the local/synthetic reference behaviour.

## Contact data

No public `POST /contact` in the first production slice.

Before contact capture is enabled, require:

- production retention period;
- deletion process;
- authorized human access path;
- access logging;
- no anonymous/browser readback;
- no automatic messaging;
- reviewed privacy notice.

## Idempotency and rate limiting

The Stage 4J-D in-memory idempotency cache and Stage 4J-C synthetic limiter are
not production mechanisms.

Production requires:

- shared/distributed replay/idempotency state;
- edge/distributed rate limiting;
- expiry semantics;
- client-key minimisation;
- operational monitoring.

## Secrets

No production secret may be committed to Git.

The application identity should receive only the minimum secret access required
for the specific resources it uses.

## Candidate comparison

### Google Cloud managed container — recommended

Strengths:

- container-native path from the existing Python factory;
- managed HTTPS;
- explicit ingress restrictions;
- load-balancer integration;
- Cloud Armor;
- London region for app and database;
- managed PostgreSQL recovery;
- least-privilege secret access.

Trade-off:

- more infrastructure pieces than an all-in-one PaaS;
- requires deliberate configuration and cost control.

### Azure managed container — viable runner-up

Strengths:

- managed ingress/TLS;
- managed PostgreSQL with backups/PITR;
- enterprise-grade security controls.

Trade-off:

- adds an Azure operating model to a project that currently has no Azure
  deployment dependency.

### Render — fastest low-ops option

Strengths:

- simple Python deployment;
- managed TLS;
- managed PostgreSQL;
- simple secret/environment configuration.

Trade-off:

- fewer explicit edge/governance controls in the proposed topology than the
  recommended hyperscaler design.

## Not approved by this stage

This stage does not authorize:

- creating any cloud account/resource;
- adding FastAPI or another framework;
- adding a Dockerfile;
- opening a port;
- changing DNS;
- provisioning PostgreSQL;
- creating production secrets;
- enabling public form submissions;
- collecting live contact information;
- contacting participants;
- changing validation state;
- importing into the validation log.

## Evidence basis

Architecture recommendation reviewed against current official documentation on
2026-08-11 for:

- Google Cloud Run service HTTPS, regions, ingress and custom-domain/load-balancer design;
- Google Cloud Armor rate limiting and Cloud Run protection;
- Google Cloud SQL PostgreSQL regional placement, backups and PITR;
- Google Secret Manager IAM / least privilege;
- Azure Container Apps ingress/TLS;
- Azure Database for PostgreSQL backups/PITR/encryption;
- Render web services, TLS, Postgres backups and environment/secrets.

These facts should be re-verified at the point of actual provisioning because
cloud capabilities and pricing can change.
