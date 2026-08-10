# EOP-0001 Form Staging v0.1

This is a local-only visual and payload-generation implementation of the
EOP-0001 public research form and separate optional contact form.

It is not a live collection service.

## Boundaries

- Binds only to `127.0.0.1`.
- Does not accept POST, PUT, PATCH, or DELETE.
- Does not call `fetch`, XMLHttpRequest, WebSocket, sendBeacon, or external APIs.
- Does not use cookies, localStorage, or sessionStorage.
- Does not persist responses on the server.
- Research and contact payloads are generated as separate local downloads.
- Contact details never enter the research payload.
- No public deployment is approved.
- No participant contact is approved.
- No Stage 4G evidence import occurs.

## Preview

From the repository root:

```bash
python scripts/preview_eop_0001_form_staging.py
```

Open:

- `http://127.0.0.1:8765/index.html`
- `http://127.0.0.1:8765/contact.html`

Use `Ctrl+C` to stop the preview server.

## Review purpose

The staging implementation supports:

- visual review;
- wording review;
- accessibility review;
- consent-flow review;
- response-token review;
- direct-identifier blocking checks;
- research/contact separation checks;
- generation of non-live test payloads.

Any generated JSON is a staging artefact. It must not be treated as live
evidence.
