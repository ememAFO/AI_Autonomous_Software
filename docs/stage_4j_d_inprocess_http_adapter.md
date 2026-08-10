# Stage 4J-D — In-Process HTTP Adapter Design v0.1

## Purpose

Stage 4J-D is the first request-handler integration stage, but it remains
strictly network-off.

It connects the already-reviewed layers:

1. Stage 4J-C request-envelope/security controls;
2. Stage 4J-A trusted request normalization;
3. Stage 4J-B separated synthetic storage.

No web framework or bound port is introduced.

## Why in-process first

A real framework would add routing, proxy, TLS, host/origin, deployment,
observability and secret-management decisions at the same time.

The in-process adapter lets the factory test the behavioural HTTP contract
before those infrastructure choices exist.

## Conceptual routes

- `POST /research`
- `POST /contact`

These are route semantics only. They are not public URLs and are not listening
on a socket.

## Idempotency

The adapter requires an opaque idempotency key.

For the synthetic design:

- keys are hashed before cache storage;
- same key + same body returns a cached 200 replay;
- same key + changed body returns 409;
- cache entries expire after a bounded synthetic TTL.

This is not production replay protection. A shared/distributed idempotency
backend and final retry semantics remain required before live deployment.

## Rate limiting

The adapter composes Stage 4J-C's in-memory synthetic rate limiter.

No raw network identifier is persisted by the limiter. Production deployment
still requires an edge/distributed rate limiter and a reviewed key derivation
strategy.

## Research response

A successful research response may return the newly created participant token
because the participant needs it for the separate optional contact step.

The token:

- is returned only in the JSON response body;
- is never placed in a URL;
- is not echoed into logs by this adapter;
- does not authorize validation evidence or participant contact.

## Contact response

Successful contact capture does not echo:

- contact value;
- contact name.

It also explicitly states that participant contact and Stage 4G handoff remain
unauthorized.

## Error mapping

Internal exceptions are converted into generic public responses. Stack traces,
database details, validation internals and secrets are not returned.

## Security headers

Every modeled response, success or failure, carries the Stage 4J-C response
header contract, including `Cache-Control: no-store`.

## Still unresolved before live

Stage 4J-D does not solve or approve:

- actual origin allow-list;
- real CORS/proxy behavior;
- TLS termination;
- distributed rate limiting;
- distributed idempotency/replay cache;
- authentication/authorization for contact-data administration;
- production persistence;
- production retention/deletion schedule;
- deployment secrets;
- hosting provider/framework;
- live privacy-notice review;
- public launch approval.

## Protected actions

All remain false.
