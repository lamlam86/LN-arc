---
name: traffic-analysis
description: Use when summarizing captured proxy traffic (traffic_search, traffic_get, traffic_blob) into an endpoint, parameter and auth inventory without replaying requests or using captured credentials.
---

# Traffic Analysis (detailed)

## Objective

Convert captured traffic into a clean, deduplicated inventory of hosts, endpoints,
parameters and observed auth schemes — analysis only.

## Inputs

- Traffic capture enabled for the in-scope host.
- `traffic_search` / `traffic_get` / `traffic_blob` tools.
- Existing endpoint inventory to deduplicate.

## Step 1 — Search and page

- `traffic_search` with the in-scope host; filter by method, status, path or
  content-type where supported.
- Page through results; do not dump the entire capture at once.
- Note the capture time window.

## Step 2 — Inspect exchanges

For each interesting exchange, `traffic_get`:
- method, scheme/host/path, status, content-type, sizes, timing;
- request headers (record auth **scheme** only), response headers;
- `traffic_blob` only when the body shape is needed, reading the minimum and
  redacting values immediately.

## Step 3 — Normalize

- Path template: replace numeric/UUID/hash segments with `:id`.
- Parameters: query keys, body keys, form fields, header-based inputs.
- Deduplicate by method + host + template.
- Group by auth requirement observed: anonymous / session cookie / bearer / basic.

## Step 4 — Analyze (report only)

| Signal | Meaning |
|---|---|
| Undocumented endpoints | not linked from the UI |
| Object IDs in paths/queries | IDOR/BOLA candidate |
| Redirect/fetch parameters | SSRF/open-redirect candidate |
| File paths/names | traversal/upload surface |
| Verbose errors | stack/path disclosure |
| Duplicate APIs | old/new versions, shadow endpoints |
| Third-party hosts | integrations and data flows |

Do not replay requests, including idempotent ones, unless the engagement explicitly
allows it. Never use captured cookies/tokens.

## Step 5 — Register

- `insert_assets` for verified endpoints/services.
- Feed `api-recon`, `exposure-assessment` and `recon-report` (parameters section).

## Evidence table

| Method | Host | Path template | Params | Auth observed | Status | Content-Type | Ref |
|---|---|---|---|---|---|---|---|

Reference = request ID or hash; no bodies.

## Pitfalls

- Replaying POST/PUT/DELETE.
- Copying tokens, cookies or personal data.
- Treating 4xx responses as absent endpoints.
- Losing the host→endpoint mapping.
- Confusing third-party analytics calls with target APIs.

## Output

- Endpoint inventory with parameter names.
- Auth-surface summary (schemes seen, protected endpoints).
- List of anomalies and potential risk classes, clearly unverified.

## Checklist

- [ ] No replay; no credential use.
- [ ] Paths templated; values redacted.
- [ ] Endpoints registered with provenance.
- [ ] Bodies minimized, personal data excluded.
- [ ] Confirmed vs potential labelled.
