---
name: js-endpoint-recon
description: Use when extracting API endpoints, parameters, base URLs and secret locations from an authorized site's JavaScript bundles and source maps via static analysis, without executing untrusted code or using discovered secrets.
---

# JavaScript Endpoint Recon (detailed)

## Objective

Recover the API surface and parameter names that the frontend knows about, from
in-scope JS bundles and source maps.

## Inputs

- In-scope page URLs and their `<script src>` lists.
- Permission to download static assets (read-only).
- Existing endpoint inventory to deduplicate.

## Step 1 — Collect bundles

1. Fetch the page HTML; extract `<script src>`, `link[rel=modulepreload]`, and
   inline script blocks.
2. Include chunk manifests (`_next/static/...`, `static/js/...`, `assets/index-*.js`).
3. Check for source maps: append `.map` to bundle URLs; also look for
   `//# sourceMappingURL=` comments.
4. Respect size limits; skip huge media/vendor bundles unless needed.

## Step 2 — Extract candidates (static)

Search each bundle for:

| Target | Pattern examples |
|---|---|
| API paths | `"/(api|v[0-9]+|rest|graphql)/..."`, `path:"/..."` |
| Base URLs | `https?://[^"' ]+` filtered to in-scope/known vendors |
| Calls | `fetch(`, `axios.`, `axios(`, `XMLHttpRequest`, `useQuery(` |
| GraphQL | `/graphql`, `query {`, `mutation {`, operation names |
| Parameters | query strings, `URLSearchParams`, `params:{...}`, form field names |
| Feature flags | `feature`, `beta`, `debug`, `admin`, `internal` keys |

Normalize paths: strip query strings, replace numeric/UUID segments with `:id`.

## Step 3 — Secret patterns (location only)

Detect and report **type + location**:
`AKIA[0-9A-Z]{16}`, `sk-...`, `oc_sk_...`, `ghp_...`, `eyJ...` (JWT),
`-----BEGIN ... PRIVATE KEY-----`, Firebase config, Google Maps keys, Stripe keys.

Record: bundle path, approximate offset, pattern type. **Redact the value** and
never use it.

## Step 4 — Verify a sample

- `HEAD`/`GET` a small sample of discovered endpoints, in scope only.
- Record status/content-type; do not call state-changing endpoints.
- If an endpoint requires auth, record that and stop.

## Step 5 — Register

- `insert_assets` for verified endpoints.
- Keep a mapping bundle → endpoints for provenance.
- Feed `api-recon` (surface) and `exposure-assessment` (risk).

## Risk signals (report only)

- Hidden/admin/internal endpoints not linked in the UI.
- Debug flags or verbose logging switches.
- Hardcoded keys/tokens (location only).
- Source maps exposing original source.
- Endpoints with object IDs and no visible authorization check (assessment only).

## Pitfalls

- Executing site code or running untrusted JS in a privileged context.
- Reporting minified variable names as endpoints.
- Treating every URL string as an API.
- Copying secret values into notes/reports.
- Calling discovered endpoints just because they exist.

## Output table

| Endpoint | Method | Params | Source bundle | Verified | Note |
|---|---|---|---|---|---|

Plus a secret-location table: bundle, type, offset, redacted.

## Checklist

- [ ] Only in-scope bundles/maps downloaded.
- [ ] Static analysis only; no execution.
- [ ] Endpoints normalized and sampled read-only.
- [ ] Secrets reported by location/type only.
- [ ] Verified endpoints registered.
